"""REST API blueprint (mounted at ``/api``).

Endpoints
---------
``GET  /templates``            list reusable block templates
``POST /templates``            create a template
``GET  /documents``            list documents (optional ``?q=`` full-text-ish filter)
``GET  /documents/<id>``       fetch a single document's blocks
``GET  /documents/<id>/pdf``   reprint a stored document's PDF (no new revision); ``?highlight=0`` strips diff markup
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
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import Template, Document, DocSequence
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


@api_bp.route('/templates/export', methods=['GET'])
def export_templates():
    """Download templates as a JSON file. ``?id=`` may repeat to select a
    subset (``?id=1&id=2``); with none given, every template is exported."""
    query = Template.query.order_by(Template.name)
    ids = request.args.getlist('id', type=int)
    if ids:
        query = query.filter(Template.id.in_(ids))
    payload = {
        "kind": "doc-generator/templates",
        "version": 1,
        "templates": [{"name": t.name, "content": json.loads(t.content)} for t in query.all()],
    }
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
    return send_file(io.BytesIO(data), mimetype='application/json', as_attachment=True,
                     download_name='doc-templates.json')


@api_bp.route('/templates/import', methods=['POST'])
def import_templates():
    """Create templates from an uploaded JSON file. Accepts a file this app
    exported, a bare ``[{name, content}, ...]`` list, or a single
    ``{name, content}`` object. Name clashes get a numeric suffix; invalid
    entries are skipped."""
    raw = request.files['file'].read() if 'file' in request.files else request.get_data()
    try:
        data = json.loads(raw)
    except Exception:
        return jsonify({"error": "הקובץ אינו JSON תקין"}), 400

    if isinstance(data, dict) and isinstance(data.get('templates'), list):
        items = data['templates']
    elif isinstance(data, dict) and 'name' in data and 'content' in data:
        items = [data]
    elif isinstance(data, list):
        items = data
    else:
        return jsonify({"error": "מבנה קובץ התבניות לא מזוהה"}), 400

    schema = TemplateSchema()
    taken = {t.name for t in Template.query.all()}
    created, skipped = [], []
    for item in items:
        try:
            loaded = schema.load(item)
        except (ValidationError, TypeError, AttributeError):
            skipped.append(item.get('name') if isinstance(item, dict) else None)
            continue
        name, n = loaded['name'], 2
        while name in taken:
            name = f"{loaded['name'][:90]} ({n})"
            n += 1
        taken.add(name)
        db.session.add(Template(name=name, content=json.dumps(loaded['content'], ensure_ascii=False)))
        created.append(name)
    db.session.commit()
    return jsonify({"created": created, "skipped": [s for s in skipped if s]}), 201


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
            has_highlights = any(b.get('_highlight') for b in content_list)
        except Exception:
            title = 'ללא כותרת'
            has_highlights = False

        results.append({
            "id": d.id,
            "document_number": d.document_number,
            "unique_identifier": d.unique_identifier,
            "title": title,
            "classification": d.classification,
            "created_date": d.created_date.isoformat(),
            "revision_number": d.revision_number,
            # Lets the history page offer a "reprint without the yellow diff
            # markup" action only on revisions that actually carry any.
            "has_highlights": has_highlights,
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
        "signature_text": d.signature_text,
        "logo_left_path": d.logo_left_path,
        "logo_right_path": d.logo_right_path,
        "contact_details": json.loads(d.contact_details) if d.contact_details else None,
        "watermark": d.watermark,
        # Browser URLs for editor previews (None if not web-served).
        "signature_url": upload_url(os.path.basename(d.signature_path)) if d.signature_path else None,
        "logo_left_url": upload_url(os.path.basename(d.logo_left_path)) if d.logo_left_path else None,
        "logo_right_url": upload_url(os.path.basename(d.logo_right_path)) if d.logo_right_path else None,
    })


@api_bp.route('/documents/<int:doc_id>/pdf', methods=['GET'])
def download_document_pdf(doc_id):
    """Re-render a stored document's PDF exactly as saved (a "reprint" —
    unlike /documents/generate this creates no new revision row). Pass
    ``?highlight=0`` to strip any baked-in revision-diff highlighting, e.g.
    to hand out a clean copy of a revision that was generated with it on."""
    d = Document.query.get_or_404(doc_id)
    content_list = json.loads(d.content)
    keep_highlight = request.args.get('highlight', '1') not in ('0', 'false', 'False')
    if not keep_highlight:
        for b in content_list:
            b.pop('_highlight', None)

    pdf_bytes = generate_pdf(
        d.document_number, content_list, d.classification, d.unique_identifier, d.revision_number,
        d.signature_path, signature_text=d.signature_text, logo_left_path=d.logo_left_path,
        logo_right_path=d.logo_right_path,
        contact_details=json.loads(d.contact_details) if d.contact_details else None,
        watermark=d.watermark,
    )
    suffix = '' if keep_highlight else '_clean'
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"{d.document_number}_Rev{d.revision_number}{suffix}.pdf"
    )


@api_bp.route('/documents', methods=['DELETE'])
def delete_documents():
    """Bulk-delete documents: ``DELETE /documents`` with body ``{"ids": [1, 2, ...]}``."""
    ids = (request.json or {}).get('ids') if request.is_json else None
    if not isinstance(ids, list) or not ids or not all(isinstance(i, int) for i in ids):
        return jsonify({"error": "ids must be a non-empty list of integers"}), 400
    deleted = Document.query.filter(Document.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({"deleted": deleted}), 200


#: Prefix used when the user leaves the document-id field empty.
DEFAULT_DOC_ID_PREFIX = "IT"


def generate_doc_number(prefix=DEFAULT_DOC_ID_PREFIX):
    """Return the next document number for ``prefix``, formatted
    ``<prefix>-<seq:03d>-<DDMMYYYY>``.

    The sequence is per (prefix, date) in the ``DocSequence`` table, so it
    resets to 001 every day and for every distinct prefix, rather than
    growing forever. Incremented with an atomic UPDATE to keep concurrent
    requests from colliding; row creation is retried once on a unique-
    constraint race (two requests both using a brand-new prefix/date).
    """
    date_str = datetime.now().strftime("%d%m%Y")

    seq = DocSequence.query.filter_by(prefix=prefix, date_str=date_str).first()
    if not seq:
        seq = DocSequence(prefix=prefix, date_str=date_str, counter=0)
        db.session.add(seq)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            seq = DocSequence.query.filter_by(prefix=prefix, date_str=date_str).first()

    DocSequence.query.filter_by(id=seq.id).update({'counter': DocSequence.counter + 1})
    db.session.commit()
    db.session.refresh(seq)

    return f"{prefix}-{seq.counter:03d}-{date_str}"

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
    signature_text = (data.get('signature_text') or '').strip()[:120] or None
    logo_left_path = data.get('logo_left_path') or None
    logo_right_path = data.get('logo_right_path') or None
    # Drop contact rows that are entirely blank.
    contact_details = [r for r in (data.get('contact_details') or [])
                       if (r.get('label') or '').strip() or (r.get('value') or '').strip()] or None
    watermark = (data.get('watermark') or '').strip()[:60] or None
    # A custom ID is a *prefix* (DocumentSchema/_DOC_ID_PREFIX_RE caps it at
    # 12 word characters) — the rest of the number is still auto-generated,
    # e.g. "BB" -> "BB-001-15092026". Leaving it blank uses the default
    # "IT" prefix.
    custom_prefix = (data.get('custom_doc_id') or '').strip() or None

    revision_number = 1
    doc_num = generate_doc_number(custom_prefix or DEFAULT_DOC_ID_PREFIX)
    unique_identifier = doc_num

    if parent_id:
        parent_doc = db.session.get(Document, parent_id)
        if parent_doc:
            unique_identifier = parent_doc.unique_identifier
            revision_number = parent_doc.revision_number + 1
            doc_num = parent_doc.document_number
            if data.get('highlight_changes', True):
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
        signature_text=signature_text,
        logo_left_path=logo_left_path,
        logo_right_path=logo_right_path,
        contact_details=json.dumps(contact_details, ensure_ascii=False) if contact_details else None,
        watermark=watermark,
        content=json.dumps(content_list, ensure_ascii=False)
    )
    db.session.add(doc)
    db.session.commit()

    pdf_bytes = generate_pdf(doc_num, content_list, classification, unique_identifier, revision_number,
                             signature_path, signature_text=signature_text, logo_left_path=logo_left_path,
                             logo_right_path=logo_right_path, contact_details=contact_details, watermark=watermark)
    
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
