"""Tests for the ``code`` block: schema, highlighting, PDF output, editor wiring."""

import fitz  # pymupdf
import pytest

from app.code_languages import CODE_LANGUAGES
from app.services.code_service import highlight_rows, build_code_flowable
from app.services.diff_service import calculate_diff
from app.services.pdf_service import generate_pdf

PY = 'def f(x):\n    if x < 3 and x > 1:\n        return "a<b>"  # note\n'


def _doc(language='python', text=PY):
    return {"content": [{"type": "code", "text": text, "language": language}]}


def test_code_block_accepts_angle_brackets(client):
    res = client.post('/api/documents/generate', json=_doc())
    assert res.status_code == 200
    assert res.data.startswith(b'%PDF-')


def test_other_blocks_still_reject_angle_brackets(client):
    res = client.post('/api/documents/generate', json={
        "content": [{"type": "paragraph", "text": "<b>x</b>", "language": "python"}]})
    assert res.status_code == 400
    assert 'text' in res.get_json()['content']['0']


def test_code_block_rejects_unknown_language(client):
    res = client.post('/api/documents/generate', json=_doc(language='cobol-99'))
    assert res.status_code == 400


def test_code_block_language_is_optional(client):
    res = client.post('/api/documents/generate',
                      json={"content": [{"type": "code", "text": "x = 1"}]})
    assert res.status_code == 200


def test_code_block_length_is_capped(client):
    res = client.post('/api/documents/generate', json=_doc(text='x' * 50001))
    assert res.status_code == 400


def test_template_roundtrip_keeps_language(client):
    body = {"name": "snippet", "content": [{"type": "code", "text": PY, "language": "python"}]}
    assert client.post('/api/templates', json=body).status_code == 201
    got = client.get('/api/templates').get_json()[0]['content'][0]
    assert got['language'] == 'python' and got['text'] == PY


def test_every_listed_language_has_a_working_lexer():
    for key in CODE_LANGUAGES:
        assert highlight_rows('x = 1 < 2\n', key, 'Helvetica', 400), key


def test_python_is_syntax_coloured_and_text_is_not():
    colours = lambda rows: {c for row in rows for _, _, c in row}
    assert len(colours(highlight_rows(PY, 'python', 'Helvetica', 400))) > 2
    assert len(colours(highlight_rows(PY, 'text', 'Helvetica', 400))) == 1


def test_long_lines_wrap_and_tabs_expand():
    rows = highlight_rows('x' * 500, 'text', 'Helvetica', 100)
    assert len(rows) > 1
    assert '\t' not in ''.join(t for r in highlight_rows('\tx', 'text', 'Helvetica', 100) for t, _, _ in r)


def test_trailing_newline_adds_no_blank_row():
    assert len(highlight_rows('a\nb\n', 'text', 'Helvetica', 100)) == 2


def test_code_text_is_in_the_pdf_verbatim():
    pdf = generate_pdf("IT-C1", [{"type": "code", "text": PY, "language": "python"}])
    text = ''.join(pg.get_text() for pg in fitz.open(stream=pdf, filetype='pdf'))
    assert 'return "a<b>"' in text and 'x < 3 and x > 1' in text
    assert 'Python' in text            # language label


def test_hebrew_in_code_comment_does_not_break_the_pdf():
    pdf = generate_pdf("IT-C2", [{"type": "code", "text": "x = 1  # שלום עולם", "language": "python"}])
    assert pdf.startswith(b'%PDF-')


def test_long_code_splits_across_pages():
    code = '\n'.join(f'print({i})' for i in range(200))
    pdf = generate_pdf("IT-C3", [{"type": "code", "text": code, "language": "python"}])
    assert len(fitz.open(stream=pdf, filetype='pdf')) >= 3   # cover + 2+ code pages


def test_changed_language_marks_block_as_changed():
    old = [{"type": "code", "text": "x", "language": "python"}]
    new = [{"type": "code", "text": "x", "language": "ruby"}]
    assert calculate_diff(old, new)[0].get("_highlight") is True


def test_editor_has_add_code_button_next_to_image_button(client):
    html = client.get('/').get_data(as_text=True)
    assert html.index('id="add-image-btn"') < html.index('id="add-code-btn"') < html.index('id="add-image-btn"') + 400
    assert '"python"' in html and 'window.CODE_LANGUAGES' in html


def test_code_block_keeps_a_gap_below_a_heading():
    pdf = generate_pdf("IT-C4", [
        {"type": "header", "text": "Heading", "level": 1},
        {"type": "code", "text": "x = 1", "language": "python"},
    ])
    page = [p for p in fitz.open(stream=pdf, filetype='pdf') if 'Python' in p.get_text()][0]
    heading_bottom = max(r.y1 for r in page.search_for("Heading"))
    # the code box's top border is the first thin drawing below the heading band
    box_top = min(d['rect'].y0 for d in page.get_drawings()
                  if d['rect'].y0 > heading_bottom and d['rect'].height > 20
                  and d['rect'].width > 300 and d.get('fill') and d['fill'] != (0.0, 0.0, 0.0))
    assert box_top - heading_bottom >= 12
