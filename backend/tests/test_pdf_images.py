from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

from app.config import get_settings
from app.services.quotation_pdf_service import (
    QUOTATION_GRID_LEFT_OFFSET,
    QUOTATION_GRID_WIDTH,
    STARLINK_LOGO_PATH,
    STARLINK_LOGO_VISIBLE_LEFT_INSET,
    _brand_logo,
    _fetch_public_image,
)


def test_quotation_pdf_uses_packaged_starlink_logo() -> None:
    """Keep the company logo in the backend artifact used by PDF rendering."""
    assert STARLINK_LOGO_PATH.is_file()

    logo = _brand_logo()

    assert logo.drawWidth > 0
    assert logo.drawHeight > 0
    # Align the visible logo artwork (not its transparent source-image margin)
    # with the left edge of the company information below it.
    assert logo._offs_x == -STARLINK_LOGO_VISIBLE_LEFT_INSET


def test_quotation_terms_heading_uses_the_table_grid_offset() -> None:
    frame_width = A4[0] - (36 * mm) - 12
    expected_offset = (frame_width - QUOTATION_GRID_WIDTH) / 2

    assert QUOTATION_GRID_LEFT_OFFSET == expected_offset


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
