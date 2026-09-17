"""SQLAlchemy models.

``Template`` – a reusable list of blocks (stored as JSON text).
``Document`` – a generated document plus its revision metadata. Documents that
share a ``unique_identifier`` are revisions of the same logical document,
distinguished by ``revision_number``.
``DocSequence`` – per (prefix, date) counter backing auto document numbers,
so the sequence resets each day instead of growing forever.
"""

from datetime import datetime, timezone

from app import db


def _utcnow():
    """Timezone-aware UTC now (``datetime.utcnow`` is deprecated in Python 3.12+)."""
    return datetime.now(timezone.utc)


class Template(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False)  # JSON array of block dicts
    created_at = db.Column(db.DateTime, default=_utcnow)


class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_number = db.Column(db.String(50), index=True, nullable=False)
    # Stable ID shared across all revisions of one logical document.
    unique_identifier = db.Column(db.String(36), index=True, nullable=False)
    revision_number = db.Column(db.Integer, default=1, nullable=False)
    classification = db.Column(db.String(50), nullable=True)  # None = unclassified
    signature_path = db.Column(db.String(255), nullable=True)
    # Optional caption drawn over the signature image, which is faded to act
    # as a watermark behind it (e.g. a name / title under a drawn signature).
    signature_text = db.Column(db.String(120), nullable=True)
    # Optional per-document header logos; a blank side leaves that corner empty.
    logo_left_path = db.Column(db.String(255), nullable=True)
    logo_right_path = db.Column(db.String(255), nullable=True)
    # Optional first-page header contact block: JSON [{"label", "value"}, ...].
    contact_details = db.Column(db.Text, nullable=True)
    # Optional diagonal watermark text drawn on every page (e.g. "טיוטה").
    watermark = db.Column(db.String(60), nullable=True)
    # Whether the auto-generated table of contents / table of figures is
    # included when the document has headings / images to put in one.
    # Nullable (like the other lightweight-migration columns below) but
    # effectively always true/false - the migration backfills existing rows
    # to 1 so older documents keep rendering exactly as before.
    include_toc = db.Column(db.Boolean, default=True, nullable=True)
    include_tof = db.Column(db.Boolean, default=True, nullable=True)
    content = db.Column(db.Text, nullable=False)  # JSON array of block dicts
    created_date = db.Column(db.DateTime, default=_utcnow)


class DocSequence(db.Model):
    """Next-sequence counter for one (prefix, date) pair, e.g. ("IT", "15092026").

    ``document_number`` is built as ``<prefix>-<counter:03d>-<date_str>``; a
    fresh row (counter 0) is created the first time a prefix is used on a
    given day, so the sequence naturally restarts every day per prefix
    instead of climbing forever.
    """
    id = db.Column(db.Integer, primary_key=True)
    prefix = db.Column(db.String(12), nullable=False)
    date_str = db.Column(db.String(8), nullable=False)  # DDMMYYYY
    counter = db.Column(db.Integer, default=0, nullable=False)

    __table_args__ = (db.UniqueConstraint('prefix', 'date_str', name='uq_doc_sequence_prefix_date'),)
