"""Marshmallow request schemas.

A "block" is the atomic unit of document content. The same shape is used for
template content and document content, and is what gets serialized into
``Template.content`` / ``Document.content``.
"""

from marshmallow import Schema, fields, validate, validates_schema, ValidationError

from app.code_languages import CODE_LANGUAGES

# Generous cap for one code block; code is the only block type whose text may
# contain angle brackets, so bound it explicitly.
MAX_CODE_LENGTH = 50000


def _reject_html(value):
    """No angle brackets in user text (defence in depth; PDF also html.escapes)."""
    if value and ("<" in value or ">" in value):
        raise ValidationError("Invalid characters detected. HTML tags (<, >) are not allowed.")


class ContactRowSchema(Schema):
    """One row of the optional first-page header contact block."""
    label = fields.String(required=False, load_default='', validate=_reject_html)
    value = fields.String(required=False, load_default='', validate=_reject_html)


class BlockSchema(Schema):
    type = fields.String(required=True, validate=validate.OneOf(["title", "header", "paragraph", "table", "image", "list_ordered", "list_unordered", "code"]))
    # First line of defence against injection: no angle brackets in any user
    # text (see _reject_html, applied in ``_check_text``). The PDF engine also
    # html.escapes everything downstream. Length validation removed for image
    # b64 or empty tables. ``code`` blocks are exempt from the bracket check
    # (source code is full of ``<`` / ``>``): they are drawn verbatim with
    # ``drawString`` by ``code_service`` and never parsed as Paragraph markup.
    text = fields.String(required=True)
    level = fields.Integer(required=False)
    image_name = fields.String(required=False, allow_none=True)
    # Optional table caption (``table`` blocks only).
    caption = fields.String(required=False, allow_none=True, validate=_reject_html)
    # Only meaningful for ``code`` blocks; a key of ``CODE_LANGUAGES``.
    language = fields.String(required=False, allow_none=True,
                             validate=validate.OneOf(list(CODE_LANGUAGES)))

    @validates_schema
    def _check_text(self, data, **kwargs):
        text = data.get('text')
        if data.get('type') == 'code':
            if text is not None and len(text) > MAX_CODE_LENGTH:
                raise ValidationError(
                    f"Code is too long (max {MAX_CODE_LENGTH} characters).", 'text')
            return
        try:
            _reject_html(text)
        except ValidationError as err:
            raise ValidationError(err.messages, 'text')

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
    # Stored verbatim as Document.document_number and rendered client-side in
    # the history table, so it needs the same HTML guard as every other
    # user-text field, not just the block content.
    custom_doc_id = fields.String(required=False, allow_none=True, validate=_reject_html)
    # Whether a revision's changed blocks get a yellow diff highlight against
    # the parent; irrelevant (ignored) when there's no parent_document_id.
    # Add a "list of tables" page (linked entries) after the contents page.
    table_list = fields.Boolean(required=False, allow_none=True, load_default=None)
    highlight_changes = fields.Boolean(required=False, allow_none=True, load_default=True)
