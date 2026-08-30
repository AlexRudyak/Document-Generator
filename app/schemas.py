"""Marshmallow request schemas.

A "block" is the atomic unit of document content. The same shape is used for
template content and document content, and is what gets serialized into
``Template.content`` / ``Document.content``.
"""

from marshmallow import Schema, fields, validate, validates, ValidationError


def _reject_html(value):
    """No angle brackets in user text (defence in depth; PDF also html.escapes)."""
    if value and ("<" in value or ">" in value):
        raise ValidationError("Invalid characters detected. HTML tags (<, >) are not allowed.")


class ContactRowSchema(Schema):
    """One row of the optional first-page header contact block."""
    label = fields.String(required=False, load_default='', validate=_reject_html)
    value = fields.String(required=False, load_default='', validate=_reject_html)


class BlockSchema(Schema):
    type = fields.String(required=True, validate=validate.OneOf(["title", "header", "paragraph", "table", "image", "list_ordered", "list_unordered"]))
    text = fields.String(required=True) # Text length validation removed for image b64 or empty tables
    level = fields.Integer(required=False)
    image_name = fields.String(required=False, allow_none=True)

    @validates("text")
    def reject_html(self, value):
        # First line of defence against injection: no angle brackets in any
        # user text. The PDF engine also html.escapes everything downstream.
        if "<" in value or ">" in value:
            raise ValidationError("Invalid characters detected. HTML tags (<, >) are not allowed.")

class TemplateSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    content = fields.List(fields.Nested(BlockSchema), required=True, validate=validate.Length(min=1))

class DocumentSchema(Schema):
    content = fields.List(fields.Nested(BlockSchema), required=True, validate=validate.Length(min=1))
    parent_document_id = fields.Integer(required=False, allow_none=True)
    # Optional: omit / null / "" -> the document is unclassified (no banners).
    classification = fields.String(required=False, allow_none=True, load_default=None)
    signature_path = fields.String(required=False, allow_none=True)
    logo_left_path = fields.String(required=False, allow_none=True)
    logo_right_path = fields.String(required=False, allow_none=True)
    contact_details = fields.List(fields.Nested(ContactRowSchema), required=False,
                                  allow_none=True, load_default=None)
    custom_doc_id = fields.String(required=False, allow_none=True)
