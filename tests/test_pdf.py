import io

import pytest
from PIL import Image

from app.services.pdf_service import generate_pdf


def test_generate_pdf():
    pdf_bytes = generate_pdf("IT-001", [
        {"type": "header", "text": "Title"},
        {"type": "paragraph", "text": "Content"},
    ])
    assert pdf_bytes.startswith(b'%PDF-')


def test_signature_text_renders_without_an_image():
    # A caption with no signature_path/image should still show up (no image
    # to fade behind it — just the text, same as a normal signature block).
    pdf_bytes = generate_pdf("IT-002", [
        {"type": "header", "text": "Title"},
    ], signature_text="ישראל ישראלי")
    assert pdf_bytes.startswith(b'%PDF-')


def test_large_image_is_downscaled_not_embedded_raw(tmp_path):
    # A ~4000x3000 photo is ~several MB; if embedded raw the PDF balloons.
    big = tmp_path / "big.jpg"
    Image.effect_noise((4000, 3000), 80).convert("RGB").save(big, quality=90)
    assert big.stat().st_size > 1_000_000

    pdf = generate_pdf("IT-1", [
        {"type": "header", "text": "H"},
        {"type": "image", "text": str(big), "image_name": "x"},
    ])
    assert pdf.startswith(b'%PDF-')
    # The single downscaled copy should be well under the source image size.
    assert len(pdf) < 700_000


def test_toc_links_point_to_their_headings_not_page_one():
    fitz = pytest.importorskip("fitz")  # pymupdf; skipped if not installed

    blocks = [{"type": "title", "text": "T"}]
    for i in range(4):
        blocks.append({"type": "header", "text": f"Chapter {i + 1}", "level": 0})
        blocks.append({"type": "paragraph", "text": "body " * 60})

    doc = fitz.open(stream=generate_pdf("IT-1", blocks), filetype="pdf")
    toc_links = [l for l in doc[1].get_links() if l.get("kind") == fitz.LINK_GOTO]
    assert len(toc_links) == 4
    target_pages = {l["page"] for l in toc_links}
    # Each chapter starts on its own page — links must span several pages,
    # not all collapse onto page 1 (the bug this guards against).
    assert target_pages != {0}
    assert len(target_pages) == 4


def test_toc_dot_leaders_survive_a_wrapped_title():
    fitz = pytest.importorskip("fitz")  # pymupdf; skipped if not installed
    import re

    long_title = "מילה " * 40  # forces the TOC entry to wrap onto multiple lines
    blocks = [
        {"type": "title", "text": "T"},
        {"type": "header", "text": "Short", "level": 0},
        {"type": "header", "text": long_title, "level": 0},
    ]
    doc = fitz.open(stream=generate_pdf("IT-1", blocks), filetype="pdf")
    toc_text = doc[1].get_text()
    dot_runs = re.findall(r'(?:\.\s+){5,}', toc_text)
    # One run of dot leaders per TOC entry — the wrapped one used to lose its
    # dots because the leader math measured the whole unwrapped title instead
    # of just its last rendered line.
    assert len(dot_runs) == 2


def test_wrap_hard_breaks_long_unbroken_token():
    from app.services.pdf_service import _wrap_hard
    from reportlab.pdfbase.pdfmetrics import stringWidth

    text = "das" * 40  # a single 120-char "word" with no spaces to wrap on
    lines = _wrap_hard(text, "Helvetica", 11, max_width=136)

    assert "".join(lines) == text
    assert all(stringWidth(line, "Helvetica", 11) <= 136 for line in lines)
    assert len(lines) > 1


def test_rtl_markup_keeps_line_order_and_bidi():
    from app.services.pdf_service import rtl_markup

    # Hard newlines stay separate and in order (not reversed / merged).
    m = rtl_markup("אלכס המלך\nאלכס הקינג")
    parts = m.split("<br/>")
    assert len(parts) == 2
    # Each segment corresponds to its logical line, BiDi-reordered.
    from bidi.algorithm import get_display
    assert parts[0] == get_display("אלכס המלך", base_dir="R")
    assert parts[1] == get_display("אלכס הקינג", base_dir="R")

    # A mixed line is reordered as one visual line (no <br/> inserted).
    assert "<br/>" not in rtl_markup("שלום world שלום")
