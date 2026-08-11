from pathlib import Path

from app.config import get_settings
from app.services.quotation_pdf_service import (
    STARLINK_LOGO_PATH,
    _brand_logo,
    _fetch_public_image,
)


def test_quotation_pdf_uses_packaged_starlink_logo() -> None:
    """Keep the company logo in the backend artifact used by PDF rendering."""
    assert STARLINK_LOGO_PATH.is_file()

    logo = _brand_logo()

    assert logo.drawWidth > 0
    assert logo.drawHeight > 0


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


def test_relative_catalog_image_url_reads_from_local_directory(
    tmp_path: Path, monkeypatch
) -> None:
    image_path = tmp_path / "SL-F-002.jpg"
    image_path.write_bytes(b"relative-catalog-image")
    monkeypatch.setenv("PRODUCT_IMAGE_DIR", str(tmp_path))
    monkeypatch.delenv("PRODUCT_IMAGE_BASE_URL", raising=False)
    get_settings.cache_clear()

    try:
        assert _fetch_public_image("/product-images/SL-F-002.jpg") == b"relative-catalog-image"
    finally:
        get_settings.cache_clear()
