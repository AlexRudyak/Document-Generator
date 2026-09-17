"""Marshmallow request schemas.

A "block" is the atomic unit of document content. The same shape is used for
template content and document content, and is what gets serialized into
``Template.content`` / ``Document.content``.
"""

import re

from marshmallow import Schema, fields, validate, ValidationError


def _reject_html(value):
    """No angle brackets in user text (defence in depth; PDF also html.escapes)."""
    if value and ("<" in value or ">" in value):
        raise ValidationError("Invalid characters detected. HTML tags (<, >) are not allowed.")


# custom_doc_id is a short *prefix* plugged into "<prefix>-<seq>-<date>"
# (see routes.generate_doc_number), so it's restricted to plain word
# characters - no spaces, hyphens or punctuation that would make the
# resulting document number ambiguous to parse back apart.
_DOC_ID_PREFIX_RE = re.compile(r'^\w{0,12}$', re.UNICODE)


def _validate_doc_id_prefix(value):
    if not _DOC_ID_PREFIX_RE.match(value or ''):
        raise ValidationError(
            "Document ID must be up to 12 letters/digits, no spaces or symbols."
        )


class ContactRowSchema(Schema):
    """One row of the optional first-page header contact block."""
    label = fields.String(required=False, load_default='', validate=_reject_html)
    value = fields.String(required=False, load_default='', validate=_reject_html)


class BlockSchema(Schema):
    type = fields.String(required=True, validate=validate.OneOf(["title", "header", "paragraph", "table", "image", "list_ordered", "list_unordered"]))
    # First line of defence against injection: no angle brackets in any user
    # text (see _reject_html). The PDF engine also html.escapes everything
    # downstream. Length validation removed for image b64 or empty tables.
    text = fields.String(required=True, validate=_reject_html)
    level = fields.Integer(required=False)
    image_name = fields.String(required=False, allow_none=True)

class TemplateSchema(Schema):
    name = fields.String(required=True, validate=[validate.Length(min=1, max=100), _reject_html])
    content = fields.List(fields.Nested(BlockSchema), required=True, validate=validate.Length(min=1))

class DocumentSchema(Schema):
    content = fields.List(fields.Nested(BlockSchema), required=True, validate=validate.Length(min=1))
    parent_document_id = fields.Integer(required=False, allow_none=True)
    # Optional: omit / null / "" -> the document is unclassified (no banners).
    classification = fields.String(required=False, allow_none=True, load_default=None)
    signature_path = fields.String(required=False, allow_none=True)
    signature_text = fields.String(required=False, allow_none=True, load_default=None,
                                   validate=_reject_html)
    logo_left_path = fields.String(required=False, allow_none=True)
    logo_right_path = fields.String(required=False, allow_none=True)
    contact_details = fields.List(fields.Nested(ContactRowSchema), required=False,
                                  allow_none=True, load_default=None)
    watermark = fields.String(required=False, allow_none=True, load_default=None,
                              validate=_reject_html)
    # Whether the auto table of contents / table of figures is included when
    # the document has headings / images to put one together from.
    include_toc = fields.Boolean(required=False, load_default=True)
    include_tof = fields.Boolean(required=False, load_default=True)
    # A short prefix plugged into the auto-generated document number (see
    # routes.generate_doc_number), e.g. "BB" -> "BB-001-15092026" - not the
    # full number itself, so it's restricted to plain word characters.
    custom_doc_id = fields.String(required=False, allow_none=True, validate=_validate_doc_id_prefix)
    # Whether a revision's changed blocks get a yellow diff highlight against
    # the parent; irrelevant (ignored) when there's no parent_document_id.
    highlight_changes = fields.Boolean(required=False, allow_none=True, load_default=True)
