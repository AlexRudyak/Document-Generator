"""SQLAlchemy models.

``Template`` – a reusable list of blocks (stored as JSON text).
``Document`` – a generated document plus its revision metadata. Documents that
share a ``unique_identifier`` are revisions of the same logical document,
distinguished by ``revision_number``.
``DocCounter`` – single-row table backing the auto document-number sequence.
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
    # Optional per-document header logos; a blank side leaves that corner empty.
    logo_left_path = db.Column(db.String(255), nullable=True)
    logo_right_path = db.Column(db.String(255), nullable=True)
    # Optional first-page header contact block: JSON [{"label", "value"}, ...].
    contact_details = db.Column(db.Text, nullable=True)
    # Optional diagonal watermark text drawn on every page (e.g. "טיוטה").
    watermark = db.Column(db.String(60), nullable=True)
    content = db.Column(db.Text, nullable=False)  # JSON array of block dicts
    created_date = db.Column(db.DateTime, default=_utcnow)


class DocCounter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    counter = db.Column(db.Integer, default=0)
