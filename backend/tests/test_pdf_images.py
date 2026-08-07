from pathlib import Path

from app.services.quotation_pdf_service import _fetch_public_image


def test_catalog_image_url_reads_from_local_product_image_directory(tmp_path: Path, monkeypatch) -> None:
    image_path = tmp_path / "SL-F-001.jpg"
    image_path.write_bytes(b"catalog-image")
    monkeypatch.setenv("PRODUCT_IMAGE_DIR", str(tmp_path))

    assert _fetch_public_image("http://localhost:5173/product-images/SL-F-001.jpg") == (
        b"catalog-image"
    )


def test_catalog_image_path_does_not_escape_local_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PRODUCT_IMAGE_DIR", str(tmp_path))

    assert _fetch_public_image("http://localhost:5173/product-images/../secret.jpg") is None
