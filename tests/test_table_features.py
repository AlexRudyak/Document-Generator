"""Table captions, the optional list of tables, and centring."""

import json

import fitz

from app.services.pdf_service import generate_pdf

ROWS = [["a", "b"], ["1", "2"]]


def _table(caption=None, rows=ROWS):
    block = {"type": "table", "text": json.dumps(rows)}
    if caption:
        block["caption"] = caption
    return block


def _text(pdf):
    return ''.join(p.get_text() for p in fitz.open(stream=pdf, filetype='pdf'))


def test_caption_is_rendered_and_numbered():
    pdf = generate_pdf("IT-T", [_table("Sales"), _table("Costs")])
    text = _text(pdf)
    assert "Sales" in text and "Costs" in text


def test_table_without_caption_or_list_has_no_caption_line():
    text = _text(generate_pdf("IT-T", [_table()]))
    assert "1" in text            # cell content still there
    assert "רשימת טבלאות" not in text


def test_list_of_tables_is_added_when_requested():
    pdf = generate_pdf("IT-T", [_table("Sales"), _table()], table_list=True)
    doc = fitz.open(stream=pdf, filetype='pdf')
    first_pages = ''.join(doc[i].get_text() for i in range(min(2, len(doc))))
    assert any(w in first_pages for w in ("רשימת טבלאות", "תואלבט תמישר"))
    assert "Sales" in first_pages                      # entry appears in the list


def test_list_of_tables_entries_link_to_the_tables():
    pdf = generate_pdf("IT-T", [_table("Sales")], table_list=True)
    doc = fitz.open(stream=pdf, filetype='pdf')
    assert any(l.get('kind') == fitz.LINK_GOTO for p in doc for l in p.get_links())


def test_no_list_when_document_has_no_tables():
    pdf = generate_pdf("IT-T", [{"type": "paragraph", "text": "hi"}], table_list=True)
    assert "רשימת טבלאות" not in _text(pdf) and "תואלבט תמישר" not in _text(pdf)


def test_table_is_centred_on_the_page():
    pdf = generate_pdf("IT-T", [_table()])
    doc = fitz.open(stream=pdf, filetype='pdf')
    page = [p for p in doc if '1' in p.get_text() and 'IT-T' in p.get_text()][-1]
    # The table's dark header band is the widest dark-filled rectangle on the page.
    bands = [d['rect'] for d in page.get_drawings()
             if d.get('fill') and d['rect'].height > 10 and d['rect'].width < page.rect.width - 150]
    assert bands, "table header not found"
    band = max(bands, key=lambda r: r.width)
    assert abs((band.x0 + band.x1) / 2 - page.rect.width / 2) < 12


def test_caption_rejects_html(client):
    body = {"content": [{"type": "table", "text": "[[\"a\"]]", "caption": "<b>x</b>"}]}
    assert client.post('/api/documents/generate', json=body).status_code == 400


def test_table_list_setting_is_stored_and_returned(client):
    body = {"content": [_table("Sales")], "table_list": True}
    assert client.post('/api/documents/generate', json=body).status_code == 200
    got = client.get('/api/documents/1').get_json()
    assert got['table_list'] is True and got['content'][0]['caption'] == "Sales"
    # reprint keeps the setting
    reprint = client.get('/api/documents/1/pdf')
    assert reprint.status_code == 200


def test_table_list_defaults_off(client):
    assert client.post('/api/documents/generate', json={"content": [_table()]}).status_code == 200
    assert client.get('/api/documents/1').get_json()['table_list'] is False
