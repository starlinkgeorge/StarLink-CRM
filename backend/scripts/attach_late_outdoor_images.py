"""Attach four late-supplied Outdoor Playthings images by SKU.

This maintenance script is deliberately limited to the supplied product image
mapping. It verifies all four products exist before changing anything and is
safe to rerun: each mapped image becomes the primary image while any existing
additional product images are retained.

Run inside the backend container with:
    python scripts/attach_late_outdoor_images.py
"""

from os import getenv
from pathlib import Path
import sys

from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Support direct execution from /app/scripts inside the backend container.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import get_session_factory
from app.models.product import Product, ProductImage


IMAGE_BASE_URL = getenv("PRODUCT_IMAGE_BASE_URL", "/product-images").rstrip("/")
IMAGE_FILENAMES = {
    "HW-02": "HW-02.png",
    "HW-04": "HW-04.png",
    "YS-04": "YS-04.png",
    "ZZ-04": "ZZ-04.png",
}


def main() -> None:
    session = get_session_factory()()
    try:
        products = list(
            session.scalars(
                select(Product)
                .where(Product.sku.in_(IMAGE_FILENAMES))
                .options(selectinload(Product.images))
            )
        )
        products_by_sku = {product.sku: product for product in products}
        missing = [sku for sku in IMAGE_FILENAMES if sku not in products_by_sku]
        if missing:
            raise SystemExit("Product SKU(s) not found: " + ", ".join(missing))

        updated = 0
        created = 0
        for sku, filename in IMAGE_FILENAMES.items():
            product = products_by_sku[sku]
            expected_url = f"{IMAGE_BASE_URL}/{filename}"

            # Clear the partial unique primary-image index before selecting the
            # supplied picture as primary. Other images remain available.
            for image in product.images:
                image.is_primary = False
            session.flush()

            matched_image = next(
                (image for image in product.images if image.image_url == expected_url),
                None,
            )
            if matched_image is None:
                session.add(
                    ProductImage(
                        product_id=product.id,
                        image_url=expected_url,
                        is_primary=True,
                        sort_order=0,
                    )
                )
                created += 1
            else:
                matched_image.is_primary = True
                matched_image.sort_order = 0
                updated += 1

        session.commit()
        print(
            "Outdoor image attachment complete: "
            f"created={created}, updated={updated}, total={len(IMAGE_FILENAMES)}."
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
