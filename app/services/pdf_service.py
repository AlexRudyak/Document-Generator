"""PDF generation engine.

Renders a list of content blocks (the same JSON structure produced by the
front-end editor and stored in ``Document.content``) into a fully paginated,
right-to-left (Hebrew) PDF.

Key pieces
----------
``NumberedCanvas``
    Custom canvas that defers page-number drawing until ``save()``, when the
    total page count is known. Also paints the per-page furniture: classification
    banners (top/bottom), document number, revision, date, and the two corner
    logos.
``MyDocTemplate``
    ``SimpleDocTemplate`` subclass whose ``afterFlowable`` hook registers a PDF
    bookmark and emits a ``TOCEntry``/``TOFEntry`` notification for every heading
    and image caption, so the table of contents / table of figures can be built
    during the second layout pass.
``RTLTableOfContents`` / ``RTLTableOfFigures``
    ReportLab's ``TableOfContents`` assumes a left-to-right layout. These
    subclasses re-implement the dot-leader row drawing so the page number sits on
    the left, the title on the right, and the whole row is a clickable internal
    link to the bookmarked target page.
``generate_pdf``
    Entry point. Builds the flowable "story" (title page, TOC, TOF, then one
    flowable per content block) and runs a two-pass ``multiBuild`` so that TOC
    page references resolve correctly.

Every user-supplied string is passed through ``html.escape`` (defence in depth;
the schema already rejects ``<``/``>``) and through ``bidi.algorithm.get_display``
to reorder RTL text for ReportLab, which has no native BiDi support.
"""

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from bidi.algorithm import get_display
import os
import io
import json
import html
import tempfile

from PIL import Image as PILImage

from paths import resource_path

# --- Modern visual theme -----------------------------------------------------
# A restrained slate/indigo palette used consistently across the cover page,
# headings, tables, rules and page furniture.
INK          = colors.HexColor('#1F2937')   # body text
MUTED        = colors.HexColor('#64748B')   # captions, metadata
HAIRLINE     = colors.HexColor('#E2E8F0')   # thin rules / table grid
ACCENT       = colors.HexColor('#4F46E5')   # indigo accent
ACCENT_DARK  = colors.HexColor('#3730A3')
H0_BG        = colors.HexColor('#1E293B')   # level-0 heading band
H1_BG        = colors.HexColor('#EEF2FF')   # level-1 heading band (indigo-50)
BAND_BG      = colors.HexColor('#0F172A')   # classification band
ZEBRA        = colors.HexColor('#F8FAFC')   # alternating table row
HIGHLIGHT    = colors.HexColor('#FEF08A')   # revision-change highlight

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        self.doc_number = kwargs.pop('doc_number', 'IT-000-00000000')
        self.font_name = kwargs.pop('font_name', 'Helvetica')
        self.font_bold = kwargs.pop('font_bold', self.font_name)
        self.classification = kwargs.pop('classification', None)
        self.unique_identifier = kwargs.pop('unique_identifier', '')
        self.revision_number = kwargs.pop('revision_number', 1)
        self.logo_left_path = kwargs.pop('logo_left_path', None)
        self.logo_right_path = kwargs.pop('logo_right_path', None)
        self.contact_details = kwargs.pop('contact_details', None) or []
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        # Snapshot each page's state instead of flushing it, so the second pass
        # in save() can stamp "page X of N" once the total N is known.
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        """Paint the per-page furniture: optional classification bands, logos, a
        thin accent rule under the header, the document number, and footer
        metadata."""
        from datetime import datetime

        pw, ph = letter
        margin = inch

        # Full-bleed classification bands, top and bottom - only when the
        # document carries a classification. The reserved strip height stays
        # fixed so the rest of the header does not shift.
        band_h = 16
        if self.classification:
            self.setFillColor(BAND_BG)
            self.rect(0, ph - band_h, pw, band_h, fill=1, stroke=0)
            self.rect(0, 0, pw, band_h, fill=1, stroke=0)
            self.setFillColor(colors.white)
            self.setFont(self.font_bold, 8)
            cls = get_display(self.classification.upper() if self.classification.isascii()
                              else self.classification)
            self.drawCentredString(pw / 2.0, ph - band_h + 4.5, cls)
            self.drawCentredString(pw / 2.0, 4.5, cls)

        # Logos in the top corners (right = RTL-leading corner). Each is drawn
        # only if a per-document image was supplied; otherwise the corner is
        # left empty.
        logo_size = 0.62 * inch
        logo_bottom = ph - band_h - 8 - logo_size
        for p, x in ((self.logo_right_path, pw - margin - logo_size),
                     (self.logo_left_path, margin)):
            if p and os.path.exists(p):
                try:
                    self.drawImage(p, x, logo_bottom, width=logo_size, height=logo_size,
                                   mask='auto', preserveAspectRatio=True)
                except Exception:
                    pass

        # Document number, centred, vertically aligned with the logos.
        self.setFillColor(INK)
        self.setFont(self.font_bold, 10)
        self.drawCentredString(pw / 2.0, logo_bottom + logo_size / 2 - 4,
                               get_display(self.doc_number))

        # Thin accent rule, clear of the logos.
        rule_y = logo_bottom - 7
        self.setStrokeColor(ACCENT)
        self.setLineWidth(1.2)
        self.line(margin, rule_y, pw - margin, rule_y)

        # First-page-only contact block: left-aligned, below the left logo.
        if self.contact_details and self._pageNumber == 1:
            self.setFont(self.font_name, 8)
            self.setFillColor(MUTED)
            cy = rule_y - 12
            for row in self.contact_details:
                label = (row.get('label') or '').strip()
                value = (row.get('value') or '').strip()
                text = f"{label}: {value}" if label and value else (label or value)
                if text:
                    self.drawString(margin, cy, get_display(text))
                    cy -= 10

        # Footer: hairline + metadata (right) and page counter (left, LTR).
        self.setStrokeColor(HAIRLINE)
        self.setLineWidth(0.75)
        self.line(margin, band_h + 26, pw - margin, band_h + 26)
        self.setFillColor(MUTED)
        self.setFont(self.font_name, 8)
        meta = get_display(
            f"מהדורה {self.revision_number}  ·  {datetime.now().strftime('%d/%m/%Y')}"
        )
        self.drawRightString(pw - margin, band_h + 14, meta)
        self.drawString(margin, band_h + 14, f"{self._pageNumber} / {page_count}")

class MyDocTemplate(SimpleDocTemplate):
    def beforeDocument(self):
        self.bookmark_counter = 0
        super(MyDocTemplate, self).beforeDocument()

    def afterFlowable(self, flowable):
        """Called by ReportLab after each flowable is laid out.

        For headings (style ``CustomHeader_<level>``, levels 0-2) and hidden image
        captions (style ``Caption_Hidden``) we drop a named bookmark on the
        current page and notify the TOC/TOF so it can render a linked entry on the
        next layout pass.
        """
        if flowable.__class__.__name__ == 'Paragraph':
            if getattr(flowable, 'style', None) and flowable.style.name.startswith('CustomHeader'):
                level = 0
                parts = flowable.style.name.split('_')
                if len(parts) > 1:
                    level = int(parts[1])
                if level < 3:
                    self.bookmark_counter += 1
                    text = flowable.getPlainText()
                    key = f"BM_{self.bookmark_counter}"
                    self.canv.bookmarkPage(key, fit='XYZ', left=0, top=842, zoom=0)
                    self.notify('TOCEntry', (level, text, self.page, key))
            elif getattr(flowable, 'style', None) and flowable.style.name == 'Caption_Hidden':
                self.bookmark_counter += 1
                text = flowable.getPlainText()
                key = f"BM_{self.bookmark_counter}"
                self.canv.bookmarkPage(key, fit='XYZ', left=0, top=842, zoom=0)
                self.notify('TOFEntry', (0, text, self.page, key))

from reportlab.pdfbase.pdfmetrics import stringWidth




class RTLTableOfContents(TableOfContents):
    """Right-to-left table of contents.

    ReportLab draws TOC rows left-to-right (title left, dots, page number right).
    Here we override ``wrap`` to install a custom ``drawTOCEntryEnd`` callback
    that instead draws: page number at the far left, a run of dot leaders, and a
    full-width clickable ``linkRect`` back to the heading's bookmark. The base
    class is still used for line breaking and vertical placement of the titles
    (which are right-aligned via ``levelStyles``).
    """

    def drawOn(self, canvas, x, y, _sW=0):
        self._toc_draw_index = 0
        super(RTLTableOfContents, self).drawOn(canvas, x, y, _sW)

    def wrap(self, availWidth, availHeight):
        # Preserve original entries with keys
        original_entries = list(self._lastEntries)
        # Strip keys so base class doesn't create broken URI links
        self._lastEntries = [(lvl, txt, pg, None) for lvl, txt, pg, _ in self._lastEntries]
        
        w, h = super(RTLTableOfContents, self).wrap(availWidth, availHeight)
        
        # Restore them for our callback
        self._lastEntries = original_entries
        
        def myDrawTOCEntryEnd(canvas, kind, label):
            idx = getattr(self, '_toc_draw_index', 0)
            entries = self._lastEntries if self._lastEntries else [(0, 'Placeholder', 0, None)]
            if idx < len(entries):
                entry = entries[idx]
                self._toc_draw_index += 1
            else:
                entry = (0, "", 0, None)
            level, text, page, key = entry
            style = self.getLevelStyle(level)
            dot = ' . '
            pagestr = str(page)
            fontSize = style.fontSize
            pagestrw = stringWidth(pagestr, style.fontName, fontSize)
            dotw = stringWidth(dot, style.fontName, fontSize)
            textw = stringWidth(text, style.fontName, fontSize)
            x, y = canvas._curr_tx_info['cur_x'], canvas._curr_tx_info['cur_y']
            # Match the entry's font for the dot leaders and page number.
            canvas.setFont(style.fontName, fontSize)
            canvas.setFillColor(getattr(style, 'textColor', None) or colors.black)
            left_edge_of_text = x - textw
            left_bound = 0
            if left_edge_of_text > left_bound:
                dots_width = left_edge_of_text - left_bound - pagestrw - 10
                num_dots = int(dots_width / dotw)
                if num_dots > 0:
                    dots = dot * num_dots
                    canvas.drawString(left_bound + pagestrw + 5, y, dots)
            canvas.drawString(left_bound, y, pagestr)
            
            if key:
                # Use relative coordinates (x=0, y=-4) for the link rect because 
                # the canvas is translated to the cell's bottom-left origin during this callback
                canvas.linkRect("", key, Rect=(0, -4, availWidth, fontSize + 4), relative=1)
        self.canv.drawTOCEntryEnd = myDrawTOCEntryEnd
        return w, h

class RTLTableOfFigures(RTLTableOfContents):
    def notify(self, kind, stuff):
        if kind == 'TOFEntry':
            self.addEntry(*stuff)

# (regular, bold) TTF candidates that can render Hebrew glyphs, most preferred
# first. ``HEBREW_FONT_PATH`` (env var) wins; then the user's system fonts; then
# the DejaVu Sans copy bundled with the app, which guarantees Hebrew renders even
# on a machine with no suitable system font (important for the frozen build).
# If nothing resolves, ReportLab's Helvetica is used and Hebrew will NOT render.
_FONT_CANDIDATES = [
    (os.environ.get("HEBREW_FONT_PATH"), os.environ.get("HEBREW_FONT_BOLD_PATH")),
    (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/Library/Fonts/Arial Unicode.ttf", None),
    (resource_path("app", "static", "assets", "fonts", "DejaVuSans.ttf"),
     resource_path("app", "static", "assets", "fonts", "DejaVuSans-Bold.ttf")),
]

# Names other modules/tests may reference.
FONT_REGULAR = 'Helvetica'
FONT_BOLD = 'Helvetica-Bold'
_fonts_ready = False


def _resolve_font():
    """Register the first available Hebrew-capable font family.

    Returns the regular font name and sets the module-level ``FONT_REGULAR`` /
    ``FONT_BOLD``. Falls back to a bold-less family (bold == regular) when only a
    regular face is available.
    """
    global _fonts_ready, FONT_REGULAR, FONT_BOLD
    if _fonts_ready:
        return FONT_REGULAR

    for regular, bold in _FONT_CANDIDATES:
        if not regular or not os.path.exists(regular):
            continue
        try:
            pdfmetrics.registerFont(TTFont('HebrewFont', regular))
        except Exception:
            continue
        FONT_REGULAR = FONT_BOLD = 'HebrewFont'
        if bold and os.path.exists(bold):
            try:
                pdfmetrics.registerFont(TTFont('HebrewFont-Bold', bold))
                FONT_BOLD = 'HebrewFont-Bold'
            except Exception:
                pass
        registerFontFamily('HebrewFont', normal='HebrewFont', bold=FONT_BOLD,
                           italic='HebrewFont', boldItalic=FONT_BOLD)
        break

    _fonts_ready = True
    return FONT_REGULAR


# Photos are only ever shown small in the PDF (≤ ~350 pt wide), but ReportLab
# embeds whatever resolution it is handed — a 12 MP phone photo makes the render
# slow and the file huge. ``_fit_image`` downsizes an image to roughly what the
# page needs, once, writing a temp file the caller cleans up afterwards.
_FIT_DPI = 220          # target pixel density inside the draw box
_FIT_SLACK = 1.2        # skip the re-encode unless the source is >20 % oversized


def _fit_image(path, max_w_pt, max_h_pt, cache, tmp_files):
    """Return a path to `path` downscaled to fit (max_w_pt × max_h_pt) at
    `_FIT_DPI`, or `path` unchanged when it is already small enough."""
    if path in cache:
        return cache[path]
    result = path
    try:
        target_w = int(max_w_pt / 72.0 * _FIT_DPI)
        target_h = int(max_h_pt / 72.0 * _FIT_DPI)
        with PILImage.open(path) as im:
            if im.width > target_w * _FIT_SLACK or im.height > target_h * _FIT_SLACK:
                # draft() lets the JPEG decoder emit a smaller image directly —
                # much faster than decoding full-res then resizing.
                im.draft(None, (target_w, target_h))
                im.thumbnail((target_w, target_h), PILImage.LANCZOS)
                has_alpha = im.mode in ('RGBA', 'LA', 'PA') or (
                    im.mode == 'P' and 'transparency' in im.info)
                fd, tmp = tempfile.mkstemp(suffix='.png' if has_alpha else '.jpg')
                os.close(fd)
                if has_alpha:
                    im.convert('RGBA').save(tmp, 'PNG', optimize=True)
                else:
                    im.convert('RGB').save(tmp, 'JPEG', quality=82, optimize=True)
                tmp_files.append(tmp)
                result = tmp
    except Exception:
        result = path
    cache[path] = result
    return result


def _draw_watermark(canv, text, font_name):
    """Big faint diagonal watermark, drawn at page start so content sits on top.

    Uses a light grey fill rather than alpha transparency (which ReportLab does
    not reliably emit), so it renders consistently in every viewer.
    """
    pw, ph = letter
    disp = get_display(text)
    size = 120
    w = pdfmetrics.stringWidth(disp, font_name, size)
    max_w = (pw ** 2 + ph ** 2) ** 0.5 * 0.60
    if w > max_w:
        size *= max_w / w
    canv.saveState()
    canv.setFillColor(colors.HexColor('#DBE0E8'))
    canv.setFont(font_name, size)
    canv.translate(pw / 2.0, ph / 2.0)
    canv.rotate(45)
    canv.drawCentredString(0, -size * 0.34, disp)
    canv.restoreState()


def generate_pdf(document_number, content_blocks, classification=None, unique_identifier='', revision_number=1,
                 signature_path=None, logo_left_path=None, logo_right_path=None, contact_details=None,
                 watermark=None):
    """Render ``content_blocks`` to PDF bytes.

    Parameters mirror the persisted ``Document`` row. ``content_blocks`` is the
    list of ``{"type", "text", "level", ...}`` dicts; blocks carrying a truthy
    ``_highlight`` key (added by :func:`app.services.diff_service.calculate_diff`)
    are rendered with a yellow background to flag revision changes. A falsy
    ``classification`` omits the per-page classification bands entirely.
    """
    font_name = _resolve_font()
    font_bold = FONT_BOLD

    img_cache = {}        # original path -> path actually embedded (maybe downscaled)
    tmp_files = []        # temp downscaled images, deleted after the build

    buffer = io.BytesIO()
    doc = MyDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=108, bottomMargin=90)
    styles = getSampleStyleSheet()

    from datetime import datetime as _dt

    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontName=font_bold,
                                 fontSize=30, leading=36, textColor=INK, spaceAfter=6, alignment=TA_CENTER)
    subtitle_style = ParagraphStyle('CoverSubtitle', fontName=font_name, fontSize=11,
                                    textColor=MUTED, alignment=TA_CENTER, leading=18)
    section_heading_style = ParagraphStyle('SectionHeading', fontName=font_bold, fontSize=15,
                                           textColor=ACCENT_DARK, spaceAfter=4, alignment=TA_RIGHT)

    def section_heading(label):
        """A right-aligned section title with a thin accent rule beneath it."""
        return [
            Paragraph(html.escape(get_display(label)), section_heading_style),
            HRFlowable(width="100%", thickness=1, color=ACCENT, spaceBefore=1,
                       spaceAfter=14, hAlign='RIGHT'),
        ]

    has_headers = any(b.get("type") == "header" for b in content_blocks)
    has_figures = any(b.get("type") == "image" and b.get("text") and os.path.exists(b["text"])
                      for b in content_blocks)

    story = []

    # --- Cover page ---------------------------------------------------------
    title_block = next((b for b in content_blocks if b.get("type") == "title"), None)
    story.append(Spacer(1, 1.7 * inch))
    story.append(HRFlowable(width=64, thickness=3, color=ACCENT, spaceAfter=22, hAlign='CENTER'))
    if title_block:
        story.append(Paragraph(html.escape(get_display(title_block.get("text"))), title_style))
    story.append(Spacer(1, 10))
    # Build the meta line in logical order and reorder once, so the mixed
    # Hebrew / Latin / digit run stays readable.
    cover_meta = "   ·   ".join([p for p in [
        f"מסמך {document_number}",
        f"מהדורה {revision_number}",
        _dt.now().strftime('%d/%m/%Y'),
        classification,
    ] if p])
    story.append(Paragraph(html.escape(get_display(cover_meta)), subtitle_style))
    story.append(PageBreak())

    # --- Table of Contents (only if the document actually has headings) ---
    if has_headers:
        story.extend(section_heading("תוכן עניינים"))
        toc = RTLTableOfContents()
        toc.levelStyles = [ParagraphStyle(fontName=(font_bold if i == 0 else font_name), fontSize=12 - min(i, 2),
                                          name=f'TOCLevel{i}', rightIndent=i*18, spaceBefore=1, spaceAfter=1,
                                          leading=12, textColor=(INK if i == 0 else MUTED), alignment=TA_RIGHT)
                           for i in range(6)]
        story.append(toc)
        story.append(Spacer(1, 0.4 * inch))

    # --- Table of Figures (only if the document contains images) ---------
    if has_figures:
        story.extend(section_heading("רשימת תמונות"))
        tof = RTLTableOfFigures()
        tof.levelStyles = [ParagraphStyle(fontName=font_name, fontSize=11, name='TOFLevel', rightIndent=0,
                                          spaceBefore=1, spaceAfter=1, leading=12, textColor=MUTED,
                                          alignment=TA_RIGHT)]
        story.append(tof)

    if has_headers or has_figures:
        story.append(PageBreak())

    # Heading counters per depth (levels 0-5), running ordered-list index, and a
    # figure counter used for "תמונה N" captions and Table-of-Figures entries.
    counters = [0] * 6
    ordered_list_count = 0
    image_count = 0
    last_type = None

    for block in content_blocks:
        b_type = block.get("type")
        if b_type == "title":
            last_type = b_type
            continue
            
        text = block.get("text")
        level = min(int(block.get("level", 0)), 5)
        is_highlighted = block.get("_highlight", False)
        bg_color = HIGHLIGHT if is_highlighted else None

        if b_type == "header":
            counters[level] += 1
            if level == 0 and counters[0] > 1:
                story.append(PageBreak())
            for i in range(level + 1, 6): counters[i] = 0
            numbering = ".".join(str(c) for c in counters[:level+1]) + ("." if level == 0 else "")
            # Headings at every depth start at the same margin (no progressive
            # indent) so 1 / 1.1 / 1.1.1 line up. Hierarchy is shown by the
            # number, weight, colour and — for levels 0/1 — a filled band.
            style = ParagraphStyle(
                f'CustomHeader_{level}', fontName=font_bold,
                fontSize=17 - (level * 2), leading=(17 - level * 2) + 4,
                alignment=TA_RIGHT, rightIndent=0, spaceAfter=6,
            )
            if level == 0:
                style.backColor = HIGHLIGHT if is_highlighted else H0_BG
                style.textColor = INK if is_highlighted else colors.white
                style.borderPadding = (7, 10, 7, 10)
                style.spaceBefore = 22
            elif level == 1:
                style.backColor = HIGHLIGHT if is_highlighted else H1_BG
                style.textColor = ACCENT_DARK
                style.borderColor = ACCENT
                style.borderWidth = 0
                style.leftIndent = 0
                style.borderPadding = (5, 9, 5, 9)
                style.spaceBefore = 16
            else:
                style.textColor = INK
                style.spaceBefore = 12
                if is_highlighted:
                    style.backColor = HIGHLIGHT
                    style.borderPadding = (3, 6, 3, 6)
            head = Paragraph(html.escape(get_display(f"{numbering} {text}")), style)
            if level == 2:
                # Small accent underline for level-2 headings.
                story.append(KeepTogether([
                    head,
                    HRFlowable(width="30%", thickness=1.5, color=ACCENT,
                               spaceBefore=2, spaceAfter=6, hAlign='RIGHT'),
                ]))
            else:
                story.append(head)
        elif b_type == "paragraph":
            # Body text starts at the same right margin as the headings (no
            # per-level indent); the hierarchy is carried by the heading above it.
            story.append(Paragraph(html.escape(get_display(text)), ParagraphStyle(
                f'CustomPara_{level}', fontName=font_name, fontSize=11, spaceAfter=10,
                leading=16.5, alignment=TA_JUSTIFY, wordWrap='RTL', textColor=INK,
                rightIndent=0, backColor=bg_color,
                borderPadding=(2, 3, 2, 3) if bg_color else 0)))
        elif b_type == "list_unordered":
            story.append(Paragraph(html.escape(get_display(f"•  {text}")), ParagraphStyle(
                f'CustomList_{level}', fontName=font_name, fontSize=11, spaceAfter=5,
                leading=16, alignment=TA_RIGHT, textColor=INK,
                rightIndent=0, backColor=bg_color)))
        elif b_type == "list_ordered":
            if last_type != "list_ordered": ordered_list_count = 1
            else: ordered_list_count += 1
            story.append(Paragraph(html.escape(get_display(f"{ordered_list_count}.  {text}")), ParagraphStyle(
                f'CustomListOrd_{level}', fontName=font_name, fontSize=11, spaceAfter=5,
                leading=16, alignment=TA_RIGHT, textColor=INK,
                rightIndent=0, backColor=bg_color)))
        elif b_type == "image" and os.path.exists(text):
            # NOTE: ``text`` holds the uploaded file's path for image blocks.
            image_count += 1
            image_name = (block.get('image_name') or '').strip()
            caption_text = f"תמונה {image_count}"
            if image_name:
                caption_text += f" - {image_name}"
                
            # Images are always centred on the full page width, regardless of the
            # block's indent level.
            total_printable_width = letter[0] - 144

            # Use sensible maximum bounds to prevent excessively huge images
            max_w = min(total_printable_width, 350)
            max_h = letter[1] / 4.0

            img = Image(_fit_image(text, max_w, max_h, img_cache, tmp_files))

            if img.drawWidth > max_w:
                ratio = max_w / float(img.drawWidth)
                img.drawWidth = max_w
                img.drawHeight *= ratio
            if img.drawHeight > max_h:
                ratio = max_h / float(img.drawHeight)
                img.drawHeight = max_h
                img.drawWidth *= ratio
            
            img_table = Table([[img]], colWidths=[img.drawWidth], rowHeights=[img.drawHeight])
            img_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOX', (0,0), (-1,-1), 0.75, HAIRLINE),
                ('TOPPADDING', (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ]))

            caption_p = Paragraph(html.escape(get_display(caption_text)), ParagraphStyle(
                'Caption', fontName=font_name, fontSize=9, textColor=MUTED,
                alignment=TA_CENTER, leading=12, spaceBefore=5))
            
            dummy_caption = Paragraph(html.escape(get_display(caption_text)), ParagraphStyle('Caption_Hidden', fontName=font_name, fontSize=0, leading=0, spaceBefore=0, spaceAfter=0, textColor=colors.white))
            story.append(dummy_caption)
            
            inner_table = Table([[img_table], [caption_p]], colWidths=[img.drawWidth])
            inner_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
                ('TOPPADDING', (0,0), (-1,-1), 2),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ]))
            # hAlign='CENTER' centres the whole figure block within the page frame.
            inner_table.hAlign = 'CENTER'
            story.append(inner_table)
            story.append(Spacer(1, 12))
        elif b_type == "table":
            try:
                table_data = json.loads(text)
                header_cell = ParagraphStyle(name='THd', fontName=font_bold, fontSize=10,
                                             textColor=colors.white, alignment=TA_RIGHT, leading=13)
                body_cell = ParagraphStyle(name='TCl', fontName=font_name, fontSize=10,
                                           textColor=INK, alignment=TA_RIGHT, leading=13)
                display_data = [
                    [Paragraph(html.escape(get_display(str(cell))),
                               header_cell if r == 0 else body_cell)
                     for cell in reversed(row)]
                    for r, row in enumerate(table_data)
                ]
                t = Table(display_data, hAlign='RIGHT')
                ts = TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), ACCENT_DARK),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, ZEBRA]),
                    ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (-1, -1), font_name),
                    ('LINEBELOW', (0, 0), (-1, -1), 0.5, HAIRLINE),
                    ('BOX', (0, 0), (-1, -1), 0.75, HAIRLINE),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('LEFTPADDING', (0, 0), (-1, -1), 9),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 9),
                ])
                if is_highlighted:
                    ts.add('BOX', (0, 0), (-1, -1), 1.2, ACCENT)
                t.setStyle(ts)
                story.append(t)
                story.append(Spacer(1, 14))
            except Exception:
                pass
            
        last_type = b_type

    if signature_path and os.path.exists(signature_path):
        story.append(Spacer(1, 0.8 * inch))
        try:
            sig_src = _fit_image(signature_path, 2 * inch, inch, img_cache, tmp_files)
            block = [
                HRFlowable(width=2.2 * inch, thickness=0.75, color=INK,
                           spaceAfter=4, hAlign='LEFT'),
                Image(sig_src, width=2 * inch, height=1 * inch, hAlign='LEFT'),
                Paragraph(html.escape(get_display("חתימה מאושרת")), ParagraphStyle(
                    name='Sig', fontName=font_bold, fontSize=10, textColor=MUTED,
                    alignment=TA_LEFT, spaceBefore=4)),
            ]
            story.append(KeepTogether(block))
        except Exception:
            pass

    # Cap the header logos too (they render on every page). ~1.4 in box keeps
    # them crisp at the 0.62 in they are actually drawn.
    lp = _fit_image(logo_left_path, 1.4 * inch, 1.4 * inch, img_cache, tmp_files) if logo_left_path else None
    rp = _fit_image(logo_right_path, 1.4 * inch, 1.4 * inch, img_cache, tmp_files) if logo_right_path else None

    wm = (watermark or '').strip()
    on_page = (lambda canv, _doc: _draw_watermark(canv, wm, font_bold)) if wm else (lambda *a: None)

    try:
        doc.multiBuild(story, onFirstPage=on_page, onLaterPages=on_page,
                       canvasmaker=lambda *args, **kwargs: NumberedCanvas(
            *args, doc_number=document_number, font_name=font_name, font_bold=font_bold,
            classification=classification, unique_identifier=unique_identifier, revision_number=revision_number,
            logo_left_path=lp, logo_right_path=rp, contact_details=contact_details,
            **kwargs))
    finally:
        for f in tmp_files:
            try:
                os.remove(f)
            except OSError:
                pass

    buffer.seek(0)
    return buffer.getvalue()
