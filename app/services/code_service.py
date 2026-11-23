"""Syntax-highlighted code blocks for the PDF engine.

``highlight_rows`` lexes source with Pygments (lexer chosen by the block's
``language``) and wraps it into visual rows of coloured segments;
``CodeFlowable`` draws those rows as a boxed, left-to-right block and can split
across pages.

Code is always LTR, even inside the RTL document, and is drawn with
``drawString`` - never through ``Paragraph`` markup - so ``<`` / ``>`` / ``&`` in
source need no escaping. Text outside Latin-1 (e.g. Hebrew in a comment) cannot
be drawn with the built-in Courier, so those runs use the document's Unicode
font instead and are visually reordered with ``get_display``.
"""

from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Flowable

from app.code_languages import CODE_LANGUAGES, DEFAULT_CODE_LANGUAGE

# --- Palette (light theme, kept by name like the rest of the PDF theme) -------
CODE_BG      = colors.HexColor('#F8FAFC')
CODE_BORDER  = colors.HexColor('#E2E8F0')
CODE_LABEL   = colors.HexColor('#64748B')
CODE_PLAIN   = colors.HexColor('#1F2937')
CODE_COMMENT = colors.HexColor('#64748B')
CODE_KEYWORD = colors.HexColor('#7C3AED')
CODE_STRING  = colors.HexColor('#047857')
CODE_NUMBER  = colors.HexColor('#B45309')
CODE_NAME    = colors.HexColor('#1D4ED8')   # functions / classes / tags
CODE_BUILTIN = colors.HexColor('#0E7490')
CODE_ATTR    = colors.HexColor('#BE185D')   # decorators, attributes, escapes
HIGHLIGHT    = colors.HexColor('#FEF08A')   # revision-change highlight

CODE_FONT = 'Courier'
CODE_FONT_BOLD = 'Courier-Bold'
FONT_SIZE = 8.5
LEADING = 11.5
PAD = 8
LABEL_HEIGHT = 13
TAB_SIZE = 4
SPACE_BEFORE = 12          # gap between the preceding heading/text and the box
BLOCK_WIDTH = 458           # matches body paragraphs (see pdf_service)

# Segment: (text, font_name, color). A row is a list of segments.


def _token_style():
    """Token type -> (color, bold); built lazily so Pygments loads only on use."""
    from pygments.token import Token
    return {
        Token.Comment: (CODE_COMMENT, False),
        Token.Keyword: (CODE_KEYWORD, True),
        Token.Keyword.Type: (CODE_BUILTIN, False),
        Token.Operator.Word: (CODE_KEYWORD, True),
        Token.Literal.String: (CODE_STRING, False),
        Token.Literal.String.Escape: (CODE_ATTR, False),
        Token.Literal.Number: (CODE_NUMBER, False),
        Token.Name.Function: (CODE_NAME, True),
        Token.Name.Class: (CODE_NAME, True),
        Token.Name.Namespace: (CODE_NAME, False),
        Token.Name.Tag: (CODE_NAME, True),
        Token.Name.Decorator: (CODE_ATTR, False),
        Token.Name.Attribute: (CODE_ATTR, False),
        Token.Name.Builtin: (CODE_BUILTIN, False),
        Token.Name.Constant: (CODE_NUMBER, False),
        Token.Generic.Heading: (CODE_NAME, True),
        Token.Generic.Deleted: (CODE_ATTR, False),
        Token.Generic.Inserted: (CODE_STRING, False),
    }


def _get_lexer(language):
    from pygments.lexers import get_lexer_by_name
    from pygments.util import ClassNotFound
    if language not in CODE_LANGUAGES or language == DEFAULT_CODE_LANGUAGE:
        return None
    try:
        return get_lexer_by_name(language, stripnl=False, ensurenl=False)
    except ClassNotFound:
        return None


def _lines_of_tokens(code, language):
    """Split ``code`` into logical lines of ``(text, color, bold)`` tokens."""
    code = code.replace('\r\n', '\n').replace('\r', '\n').expandtabs(TAB_SIZE)
    lexer = _get_lexer(language)
    if lexer is None:
        stream = [(None, code)]
    else:
        stream = lexer.get_tokens(code)

    styles = _token_style() if lexer is not None else {}
    cache = {}

    def style_for(ttype):
        if ttype in cache:
            return cache[ttype]
        t = ttype
        found = (CODE_PLAIN, False)
        while t is not None:
            if t in styles:
                found = styles[t]
                break
            t = t.parent
        cache[ttype] = found
        return found

    lines = [[]]
    for ttype, value in stream:
        color, bold = style_for(ttype) if ttype is not None else (CODE_PLAIN, False)
        parts = value.split('\n')
        for i, part in enumerate(parts):
            if i > 0:
                lines.append([])
            if part:
                lines[-1].append((part, color, bold))
    # A trailing newline in the source must not render a phantom empty line.
    while len(lines) > 1 and not lines[-1]:
        lines.pop()
    return lines


def _is_latin1(ch):
    return ord(ch) < 256


def highlight_rows(code, language, fallback_font, max_width):
    """Lex + wrap ``code`` into visual rows no wider than ``max_width`` points.

    ``fallback_font`` draws characters Courier can't (Hebrew etc.). Long lines
    are hard-wrapped by measured width.
    """
    rows = []
    for tokens in _lines_of_tokens(code, language):
        row, width = [], 0.0
        for text, color, bold in tokens:
            for ch in text:
                font = (CODE_FONT_BOLD if bold else CODE_FONT) if _is_latin1(ch) else fallback_font
                w = stringWidth(ch, font, FONT_SIZE)
                if width + w > max_width and row:
                    rows.append(_merge(row, fallback_font))
                    row, width = [], 0.0
                row.append((ch, font, color))
                width += w
        rows.append(_merge(row, fallback_font))
    return rows


def _merge(chars, fallback_font):
    """Merge per-character tuples into runs; reorder non-Latin runs for display."""
    runs = []
    for ch, font, color in chars:
        if runs and runs[-1][1] == font and runs[-1][2] == color:
            runs[-1][0].append(ch)
        else:
            runs.append(([ch], font, color))
    out = []
    for chs, font, color in runs:
        text = ''.join(chs)
        if font == fallback_font:
            text = get_display(text, base_dir='L')
        out.append((text, font, color))
    return out


class CodeFlowable(Flowable):
    """A boxed block of pre-highlighted code rows, splittable across pages."""

    def __init__(self, rows, label, fallback_font, background=None, first=True):
        super().__init__()
        self.rows = rows
        self.label = label
        self.fallback_font = fallback_font
        self.background = background or CODE_BG
        self.first = first
        self.hAlign = 'RIGHT'
        # Breathing room below a heading or paragraph above; ReportLab drops it at
        # the top of a page, and a continuation chunk needs none.
        self.spaceBefore = SPACE_BEFORE if first else 0
        self.width = BLOCK_WIDTH
        self.height = 0

    def _header_h(self):
        return LABEL_HEIGHT if (self.first and self.label) else 0

    def _chrome(self):
        return 2 * PAD + self._header_h()

    def wrap(self, availWidth, availHeight):
        self.width = min(BLOCK_WIDTH, availWidth)
        self.height = self._chrome() + len(self.rows) * LEADING
        return self.width, self.height

    def split(self, availWidth, availHeight):
        fits = int((availHeight - self._chrome()) // LEADING)
        if fits >= len(self.rows):
            return [self]
        if fits < 2:                      # not worth starting here; move to next page
            return []
        head = CodeFlowable(self.rows[:fits], self.label, self.fallback_font,
                            self.background, self.first)
        tail = CodeFlowable(self.rows[fits:], self.label, self.fallback_font,
                            self.background, False)
        return [head, tail]

    def draw(self):
        canv = self.canv
        canv.saveState()
        canv.setFillColor(self.background)
        canv.setStrokeColor(CODE_BORDER)
        canv.setLineWidth(0.75)
        canv.roundRect(0, 0, self.width, self.height, 4, stroke=1, fill=1)
        top = self.height - PAD
        if self._header_h():
            canv.setFont(CODE_FONT, 7)
            canv.setFillColor(CODE_LABEL)
            canv.drawString(PAD, top - 7, self.label)
            top -= LABEL_HEIGHT
        y = top - FONT_SIZE
        for row in self.rows:
            x = PAD
            for text, font, color in row:
                canv.setFont(font, FONT_SIZE)
                canv.setFillColor(color)
                canv.drawString(x, y, text)
                x += stringWidth(text, font, FONT_SIZE)
            y -= LEADING
        canv.restoreState()


def build_code_flowable(code, language, fallback_font, highlighted=False):
    """Entry point used by ``generate_pdf`` for a ``code`` block."""
    language = language if language in CODE_LANGUAGES else DEFAULT_CODE_LANGUAGE
    label = None if language == DEFAULT_CODE_LANGUAGE else CODE_LANGUAGES[language]
    rows = highlight_rows(code, language, fallback_font, BLOCK_WIDTH - 2 * PAD)
    return CodeFlowable(rows, label, fallback_font, HIGHLIGHT if highlighted else None)
