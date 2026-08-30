from PIL import Image

from app.services.pdf_service import generate_pdf


def test_generate_pdf():
    pdf_bytes = generate_pdf("IT-001", [
        {"type": "header", "text": "Title"},
        {"type": "paragraph", "text": "Content"},
    ])
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
