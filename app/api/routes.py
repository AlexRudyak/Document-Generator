"""REST API blueprint (mounted at ``/api``).

Endpoints
---------
``GET  /templates``            list reusable block templates
``POST /templates``            create a template
``GET  /documents``            list documents (optional ``?q=`` full-text-ish filter)
``GET  /documents/<id>``       fetch a single document's blocks
``POST /documents/generate``   validate + persist + render a PDF (returns the file)
``POST /upload``               store an image, return its server path

Document content is stored as a JSON array of "blocks" in ``Document.content``.
Revisions: passing ``parent_document_id`` to ``/documents/generate`` creates a new
row that shares the parent's ``unique_identifier``, bumps ``revision_number``, and
highlights changed blocks via :func:`app.services.diff_service.calculate_diff`.
"""

import json
import os
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, current_app
from werkzeug.utils import secure_filename
from marshmallow import ValidationError
from app import db
from app.models import Template, Document, DocCounter
from app.schemas import TemplateSchema, DocumentSchema
from app.services.pdf_service import generate_pdf
from app.services.diff_service import calculate_diff
from paths import uploads_dir
import io

api_bp = Blueprint('api', __name__)

# Uploads are restricted to image types because they are only ever embedded in
# the generated PDF (figures and signature blocks).
ALLOWED_UPLOAD_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg'}

@api_bp.route('/templates', methods=['GET'])
def get_templates():
    templates = Template.query.all()
    return jsonify([
        {"id": t.id, "name": t.name, "content": json.loads(t.content)}
        for t in templates
    ])

@api_bp.route('/templates', methods=['POST'])
def create_template():
    schema = TemplateSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(err.messages), 400
        
    if Template.query.filter_by(name=data['name']).first():
        return jsonify({"error": "Template name already exists"}), 400
        
    template = Template(name=data['name'], content=json.dumps(data['content'], ensure_ascii=False))
    db.session.add(template)
    db.session.commit()
    
    return jsonify({"message": "Template created", "id": template.id}), 201

@api_bp.route('/documents', methods=['GET'])
def get_documents():
    q = request.args.get('q', '')
    query = Document.query
    if q:
        # For documents saved prior to ensure_ascii=False, Hebrew is saved as unicode escapes (e.g. \u05e7)
        escaped_q = json.dumps(q).strip('"')
        query = query.filter(db.or_(
            Document.document_number.ilike(f"%{q}%"),
            Document.unique_identifier.ilike(f"%{q}%"),
            Document.content.ilike(f"%{q}%"),
            Document.content.ilike(f"%{escaped_q}%") if escaped_q != q else db.false()
        ))
    docs = query.order_by(Document.created_date.desc()).all()
    
    # Extract title from content JSON for display
    results = []
    for d in docs:
        try:
            content_list = json.loads(d.content)
            title = next((block['text'] for block in content_list if block.get('type') == 'title'), 'ללא כותרת')
        except:
            title = 'ללא כותרת'
            
        results.append({
            "id": d.id, 
            "document_number": d.document_number,
            "unique_identifier": d.unique_identifier,
            "title": title,
            "classification": d.classification,
            "created_date": d.created_date.isoformat(), 
            "revision_number": d.revision_number
        })
    return jsonify(results)

@api_bp.route('/documents/<int:doc_id>', methods=['GET'])
def get_document(doc_id):
    d = Document.query.get_or_404(doc_id)
    return jsonify({
        "id": d.id, 
        "document_number": d.document_number, 
        "content": json.loads(d.content),
        "created_date": d.created_date.isoformat(),
        "revision_number": d.revision_number,
        "classification": d.classification,
        "unique_identifier": d.unique_identifier,
        "signature_path": d.signature_path,
        "logo_left_path": d.logo_left_path,
        "logo_right_path": d.logo_right_path,
        "contact_details": json.loads(d.contact_details) if d.contact_details else None,
        # Browser URLs for editor previews (None if not web-served).
        "signature_url": upload_url(os.path.basename(d.signature_path)) if d.signature_path else None,
        "logo_left_url": upload_url(os.path.basename(d.logo_left_path)) if d.logo_left_path else None,
        "logo_right_url": upload_url(os.path.basename(d.logo_right_path)) if d.logo_right_path else None,
    })

def generate_doc_number():
    """Return the next auto document number, formatted ``IT-<seq:03d>-<DDMMYYYY>``.

    The sequence lives in the single-row ``DocCounter`` table and is incremented
    with an atomic UPDATE to keep concurrent requests from colliding.
    """
    counter = DocCounter.query.first()
    if not counter:
        counter = DocCounter(counter=0)
        db.session.add(counter)
        db.session.commit()
        
    DocCounter.query.filter_by(id=counter.id).update({'counter': DocCounter.counter + 1})
    db.session.commit()
    db.session.refresh(counter)
    
    date_str = datetime.now().strftime("%d%m%Y")
    return f"IT-{counter.counter:03d}-{date_str}"

@api_bp.route('/documents/generate', methods=['POST'])
def generate_document():
    schema = DocumentSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(err.messages), 400
        
    content_list = data['content']
    parent_id = data.get('parent_document_id')
    classification = (data.get('classification') or '').strip() or None
    signature_path = data.get('signature_path') or None
    logo_left_path = data.get('logo_left_path') or None
    logo_right_path = data.get('logo_right_path') or None
    # Drop contact rows that are entirely blank.
    contact_details = [r for r in (data.get('contact_details') or [])
                       if (r.get('label') or '').strip() or (r.get('value') or '').strip()] or None
    # Trim to the unique_identifier column width (VARCHAR(36)) to avoid silent
    # truncation / driver errors on very long custom IDs.
    custom_doc_id = (data.get('custom_doc_id') or '').strip()[:36] or None

    revision_number = 1
    doc_num = custom_doc_id if custom_doc_id else generate_doc_number()
    unique_identifier = doc_num

    if parent_id:
        parent_doc = db.session.get(Document, parent_id)
        if parent_doc:
            unique_identifier = parent_doc.unique_identifier
            revision_number = parent_doc.revision_number + 1
            doc_num = parent_doc.document_number
            old_content = json.loads(parent_doc.content)
            content_list = calculate_diff(old_content, content_list)
            # Inherit header logos from the parent unless this revision overrides.
            logo_left_path = logo_left_path or parent_doc.logo_left_path
            logo_right_path = logo_right_path or parent_doc.logo_right_path

    doc = Document(
        document_number=doc_num,
        unique_identifier=unique_identifier,
        revision_number=revision_number,
        classification=classification,
        signature_path=signature_path,
        logo_left_path=logo_left_path,
        logo_right_path=logo_right_path,
        contact_details=json.dumps(contact_details, ensure_ascii=False) if contact_details else None,
        content=json.dumps(content_list, ensure_ascii=False)
    )
    db.session.add(doc)
    db.session.commit()

    pdf_bytes = generate_pdf(doc_num, content_list, classification, unique_identifier, revision_number,
                             signature_path, logo_left_path=logo_left_path, logo_right_path=logo_right_path,
                             contact_details=contact_details)
    
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"{doc_num}_Rev{revision_number}.pdf"
    )

@api_bp.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: .{ext}"}), 400

    upload_folder = current_app.config.get('UPLOAD_FOLDER') or uploads_dir()
    os.makedirs(upload_folder, exist_ok=True)

    # secure_filename strips path separators / traversal sequences; the UUID
    # prefix guarantees uniqueness and prevents collisions.
    safe_name = secure_filename(file.filename) or f"upload.{ext}"
    filename = f"{uuid.uuid4()}_{safe_name}"
    filepath = os.path.abspath(os.path.join(upload_folder, filename))
    file.save(filepath)
    _shrink_oversized(filepath)

    # ``filepath`` (absolute) is stored in the DB and read from disk by the PDF
    # engine. ``url`` is the browser-served path, used only for editor previews
    # (valid when uploads live under the static folder, i.e. running from source).
    return jsonify({"filepath": filepath, "url": upload_url(filename)}), 201


_MAX_UPLOAD_EDGE = 2200  # px; uploads are only ever shown small in the PDF


def _shrink_oversized(path):
    """Downscale an uploaded image whose longest edge exceeds _MAX_UPLOAD_EDGE,
    in place. One-time cost that keeps every later render (and preview) fast."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            if max(im.size) <= _MAX_UPLOAD_EDGE:
                return
            im.draft(None, (_MAX_UPLOAD_EDGE, _MAX_UPLOAD_EDGE))
            im.thumbnail((_MAX_UPLOAD_EDGE, _MAX_UPLOAD_EDGE), Image.LANCZOS)
            fmt = im.format or ('PNG' if path.lower().endswith('.png') else 'JPEG')
            if fmt == 'JPEG':
                im = im.convert('RGB')
            im.save(path, fmt)
    except Exception:
        pass  # leave the original in place if anything goes wrong


def upload_url(filename):
    """Browser URL for an uploaded file, or None if it is not web-served."""
    static_uploads = os.path.join('app', 'static', 'uploads')
    folder = current_app.config.get('UPLOAD_FOLDER') or uploads_dir()
    if os.path.abspath(folder) == os.path.abspath(static_uploads):
        return f"/static/uploads/{filename}"
    return None
