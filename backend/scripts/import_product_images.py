"""Attach the extracted 2025 catalogue images to products by SKU.

The image files are served by the frontend's ``public/product-images`` folder.
The script only adds images to products that do not already have any, making it
safe to rerun without replacing maintained catalogue images.

Run inside the backend container with:
    python scripts/import_product_images.py
"""

from os import getenv
from pathlib import Path
import sys

from sqlalchemy import select

# Support direct execution from /app/scripts inside the backend container.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import get_session_factory
from app.models.product import Product, ProductImage


IMAGE_BASE_URL = getenv("PRODUCT_IMAGE_BASE_URL", "/product-images").rstrip("/")
SKUS = [f"SL-F-{number:03d}" for number in range(1, 46)]


def main() -> None:
    session = get_session_factory()()
    created = 0
    skipped = 0
    missing = []
    try:
        for sku in SKUS:
            product = session.scalar(select(Product).where(Product.sku == sku))
            if product is None:
                missing.append(sku)
                continue
            if session.scalar(select(ProductImage.id).where(ProductImage.product_id == product.id)):
                skipped += 1
                continue
            session.add(
                ProductImage(
                    product_id=product.id,
                    image_url=f"{IMAGE_BASE_URL}/{sku}.jpg",
                    is_primary=True,
                    sort_order=0,
                )
            )
            created += 1

        session.commit()
        print(
            "Product image import complete: "
            f"created={created}, skipped={skipped}, missing={len(missing)}."
        )
        if missing:
            print("Missing product SKUs: " + ", ".join(missing))
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
