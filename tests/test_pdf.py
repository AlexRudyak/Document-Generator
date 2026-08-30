from app.services.pdf_service import generate_pdf

def test_generate_pdf():
    pdf_bytes = generate_pdf("IT-001", [
        {"type": "header", "text": "Title"},
        {"type": "paragraph", "text": "Content"}
    ])
    assert pdf_bytes.startswith(b'%PDF-')
