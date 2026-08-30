import io
import json


def test_create_template(client):
    res = client.post('/api/templates', json={
        "name": "Invoice",
        "content": [{"type": "header", "text": "Invoice Title"}]
    })
    assert res.status_code == 201


def test_create_template_invalid_type(client):
    res = client.post('/api/templates', json={
        "name": "Invoice",
        "content": [{"type": "invalid", "text": "Invoice Title"}]
    })
    assert res.status_code == 400


def test_create_template_duplicate_name(client):
    body = {"name": "Dup", "content": [{"type": "header", "text": "H"}]}
    assert client.post('/api/templates', json=body).status_code == 201
    assert client.post('/api/templates', json=body).status_code == 400


def test_block_rejects_html_tags(client):
    res = client.post('/api/templates', json={
        "name": "XSS",
        "content": [{"type": "paragraph", "text": "<script>alert(1)</script>"}]
    })
    assert res.status_code == 400


def test_generate_document_returns_pdf(client):
    res = client.post('/api/documents/generate', json={
        "content": [
            {"type": "header", "text": "Hello"},
            {"type": "paragraph", "text": "World"}
        ]
    })
    assert res.status_code == 200
    assert res.headers['Content-Type'] == 'application/pdf'
    assert res.data.startswith(b'%PDF-')


def test_classification_is_optional(client):
    # No classification supplied -> stored as null, PDF still renders.
    res = client.post('/api/documents/generate', json={"content": [{"type": "header", "text": "H"}]})
    assert res.status_code == 200
    doc_id = client.get('/api/documents').get_json()[0]['id']
    assert client.get(f'/api/documents/{doc_id}').get_json()['classification'] is None


def test_classification_is_stored_when_given(client):
    res = client.post('/api/documents/generate', json={
        "content": [{"type": "header", "text": "H"}],
        "classification": "סודי",
    })
    assert res.status_code == 200
    doc_id = client.get('/api/documents').get_json()[0]['id']
    assert client.get(f'/api/documents/{doc_id}').get_json()['classification'] == "סודי"


def test_contact_details_round_trip(client):
    rows = [{"label": "טלפון", "value": "050-1"}, {"label": "מייל", "value": "a@b.c"}]
    res = client.post('/api/documents/generate', json={
        "content": [{"type": "header", "text": "H"}],
        "contact_details": rows,
    })
    assert res.status_code == 200
    doc_id = client.get('/api/documents').get_json()[0]['id']
    assert client.get(f'/api/documents/{doc_id}').get_json()['contact_details'] == rows


def test_contact_details_blank_rows_dropped(client):
    res = client.post('/api/documents/generate', json={
        "content": [{"type": "header", "text": "H"}],
        "contact_details": [{"label": "", "value": ""}, {"label": "x", "value": ""}],
    })
    assert res.status_code == 200
    doc_id = client.get('/api/documents').get_json()[0]['id']
    assert client.get(f'/api/documents/{doc_id}').get_json()['contact_details'] == [{"label": "x", "value": ""}]


def test_watermark_round_trip(client):
    res = client.post('/api/documents/generate', json={
        "content": [{"type": "header", "text": "H"}],
        "watermark": "טיוטה",
    })
    assert res.status_code == 200
    doc_id = client.get('/api/documents').get_json()[0]['id']
    assert client.get(f'/api/documents/{doc_id}').get_json()['watermark'] == "טיוטה"


def test_watermark_omitted_is_null(client):
    client.post('/api/documents/generate', json={"content": [{"type": "header", "text": "H"}]})
    doc_id = client.get('/api/documents').get_json()[0]['id']
    assert client.get(f'/api/documents/{doc_id}').get_json()['watermark'] is None


def test_watermark_rejects_html(client):
    res = client.post('/api/documents/generate', json={
        "content": [{"type": "header", "text": "H"}], "watermark": "<script>x</script>",
    })
    assert res.status_code == 400


def test_contact_details_rejects_html(client):
    res = client.post('/api/documents/generate', json={
        "content": [{"type": "header", "text": "H"}],
        "contact_details": [{"label": "x", "value": "<b>hi</b>"}],
    })
    assert res.status_code == 400


def test_generate_document_creates_revision(client):
    first = client.post('/api/documents/generate', json={
        "content": [{"type": "header", "text": "V1"}],
        "custom_doc_id": "DOC-1",
    })
    assert first.status_code == 200

    listed = client.get('/api/documents').get_json()
    parent_id = listed[0]['id']

    second = client.post('/api/documents/generate', json={
        "content": [{"type": "header", "text": "V2"}],
        "parent_document_id": parent_id,
    })
    assert second.status_code == 200
    assert 'Rev2' in second.headers['Content-Disposition']


def test_documents_search_filter(client):
    client.post('/api/documents/generate', json={
        "content": [{"type": "title", "text": "Findable"}, {"type": "header", "text": "x"}],
    })
    hits = client.get('/api/documents?q=Findable').get_json()
    assert len(hits) == 1
    assert client.get('/api/documents?q=nothing-matches').get_json() == []


def test_generate_document_accepts_custom_logos(client):
    png = b'\x89PNG\r\n\x1a\n'
    up = client.post('/api/upload', data={'file': (io.BytesIO(png), 'l.png')},
                     content_type='multipart/form-data')
    path = up.get_json()['filepath']
    res = client.post('/api/documents/generate', json={
        "content": [{"type": "header", "text": "H"}],
        "logo_left_path": path,
        "logo_right_path": path,
    })
    assert res.status_code == 200
    doc = client.get('/api/documents').get_json()[0]
    detail = client.get(f"/api/documents/{doc['id']}").get_json()
    assert detail['logo_left_path'] == path
    assert detail['logo_right_path'] == path


def test_revision_inherits_logos(client):
    png = b'\x89PNG\r\n\x1a\n'
    path = client.post('/api/upload', data={'file': (io.BytesIO(png), 'l.png')},
                       content_type='multipart/form-data').get_json()['filepath']
    client.post('/api/documents/generate', json={
        "content": [{"type": "header", "text": "V1"}], "logo_left_path": path,
    })
    parent_id = client.get('/api/documents').get_json()[0]['id']
    client.post('/api/documents/generate', json={
        "content": [{"type": "header", "text": "V2"}], "parent_document_id": parent_id,
    })
    newest = client.get(f"/api/documents/{client.get('/api/documents').get_json()[0]['id']}").get_json()
    assert newest['logo_left_path'] == path


def test_upload_rejects_non_image(client):
    data = {'file': (io.BytesIO(b'not an image'), 'payload.exe')}
    res = client.post('/api/upload', data=data, content_type='multipart/form-data')
    assert res.status_code == 400


def test_upload_accepts_png(client, tmp_path):
    data = {'file': (io.BytesIO(b'\x89PNG\r\n\x1a\n'), 'pic.png')}
    res = client.post('/api/upload', data=data, content_type='multipart/form-data')
    assert res.status_code == 201
    assert res.get_json()['filepath'].endswith('.png')
