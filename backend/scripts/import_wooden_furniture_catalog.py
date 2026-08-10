"""Import the 2025 StarLink Wooden Furniture catalogue into the CRM.

The source catalogue is a 9-page PDF supplied by Dalian StarLink.  The import
is intentionally idempotent: it creates only missing SKUs and only attaches an
image where an existing product has none.  It never replaces product data that
was edited in the CRM.

Run inside the rebuilt backend container:
    python scripts/import_wooden_furniture_catalog.py
"""

from decimal import Decimal, InvalidOperation
from os import getenv
from pathlib import Path
import sys

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import get_session_factory
from app.models.product import Product, ProductCategory, ProductImage


CATEGORY_NAME = "2025 Wooden Furniture"
IMAGE_BASE_URL = getenv(
    "PRODUCT_IMAGE_BASE_URL", "http://localhost:5173/product-images"
).rstrip("/")
SOURCE_NOTE = "Imported from the 2025 StarLink Wooden Furniture catalogue."

# sku, name, USD reference price, length cm, width cm, height cm
# A compound dimension is retained in dimension_text while its individual mm
# field remains empty, so the original catalogue measurement is not distorted.
PRODUCTS = [
    ("K-F-001", "Sleeping Bed", "32.00", "121", "56.5", "16.5"),
    ("K-F-002", "Double Layer Shelf with Backplane", "55.81", "120", "30", "35"),
    ("K-F-003", "Three Layer Shelf with Backplane", "78.10", "120", "30", "65"),
    ("K-F-004", "Four Layer Shelf with Backplane", "95.14", "120", "30", "80"),
    ("K-F-005", "Bookshelf", "70.00", "80", "60", "30"),
    ("K-F-006", "Towel Rack", "41.50", "80", "80", "30"),
    ("K-F-007", "Double Layer Shoes Cabinet", "86.00", "118", "33", "26"),
    ("K-F-008", "Four Layer Shoes Cabinet", "131.00", "118", "66", "26"),
    ("K-F-009", "Cup Cabinet", "89.00", "83", "76", "30"),
    ("K-F-010", "Bag Cabinet", "167.00", "118", "114", "30"),
    ("K-F-011", "Three Layer Corner Cabinet", "44.60", "56", "30", "30"),
    ("K-F-012", "Double Layer Corner Cabinet", "34.30", "35", "30", "30"),
    ("K-F-013", "Carpet Stand", "39.00", "40", "60", "15"),
    ("K-F-014", "Big Corner Cabinet", "63.00", "80", "30", "56"),
    ("K-F-015", "Painting Paper Cabinet", "77.00", "40", "60", "60"),
    ("K-F-016", "Toddler Ladder", "231.00", "120", "75", "45"),
    ("K-F-017", "Selling Store", "97.00", "112", "40", "83"),
    ("K-F-018", "Drawing Board", "74.30", "40", "56", "64"),
    ("K-F-019", "Half Oval Cabinet", "51.00", "80", "60", "30"),
    ("K-F-020", "Oval Cabinet", "66.00", "80", "60", "40"),
    ("K-F-021", "Oval Corner Cabinet", "51.00", "60", "40", "28"),
    ("K-F-022", "Bookshelf for Toddler", "41.50", "80", "29", "80"),
    ("K-F-023", "Table and Chairs Set", "231.00", None, None, None),
    ("K-F-024", "Small Table", "51.00", "40", "60", "39"),
    ("K-F-025", "Bear Chair", "45.00", "40", "40", "45"),
    ("K-F-026", "Bench", "70.00", "35", "30", "75"),
    ("K-F-027", "Cabinet for Towel and Cup", "95.00", "110", "80", "12"),
    ("K-F-028", "Super Moon Table", "191.00", "220", "110", "51/45/48"),
    ("K-F-029", "Rotating Bookshelf", "72.00", "50", "50", "96"),
    ("K-F-030", "Wave Bookshelf", "38.00", "60", "30", "40"),
    ("K-F-031", "Height Adjustable Study Table 1", "132.00", "84", "91.5", "145.5"),
    ("K-F-032", "Height Adjustable Study Table 2", "159.00", "104", "91.5", "145.5"),
    ("K-F-033", "Height Adjustable Study Table 3", "103.00", "84", "91.5", "80"),
    ("K-F-034", "Height Adjustable Study Table 4", "129.00", "104", "91.5", "80"),
    ("K-F-035", "Height Adjustable Study Chair", "38.00", "49", "43", "70"),
    ("K-F-036", "Double Locker", "54.00", "60", "30", "71"),
    ("K-F-037", "Three Compartment Locker", "56.00", "60", "30", "71"),
    ("K-F-038", "Double Glass Locker", "79.00", "60", "30", "71"),
    ("K-F-039", "Double Drawer Locker", "79.00", "60", "30", "71"),
    ("K-F-040", "Six Compartment Locker 1", "79.00", "90", "30", "71"),
    ("K-F-041", "Six Compartment Locker 2", "79.00", "60", "30", "91.5"),
    ("K-F-042", "Rotating Hanger", "43.00", "40", "40", "190"),
    ("K-F-043", "Clothes and Shoes Rack", "55.00", "60", "30", "121"),
    ("K-F-044", "Children's Indoor Playhouse", "57.00", "90", "97", "107.5"),
    ("K-F-045", "Height Adjustable Children's Chair", "22.30", "33", "33", "54"),
    ("K-F-046", "Small Round Table", "32.00", "60", "60", "48"),
    ("K-F-047", "Children's Drawing Tools", "56.00", "83", "24", "81.5"),
    ("K-F-048", "Wooden Horse", "29.00", "78", "50", "30"),
    ("K-F-049", "Height Adjustable Baby Feeding Chair 1", "44.00", "43", "45", "80"),
    ("K-F-050", "Height Adjustable Baby Feeding Chair 2", "44.00", "43", "46", "80"),
    ("K-F-051", "Lego Table", "65.00", "79", "58", "50"),
    ("K-F-052", "Small Round Chair", "12.00", "28", "28", "26"),
    ("K-F-053", "Small Square Chair", "12.00", "28", "26", "26"),
    ("K-F-054", "Small Study Table Set", "89.00", "62.5/33", "61/40", "75/59"),
    ("K-F-055", "Kids Wooden Table Rectangle", "73.86", "120", "60", "45/48/51"),
    ("K-F-056", "Kids Wooden Table Square", "52.90", "60", "60", "45/48/51"),
    ("K-F-057", "Kids Wooden Table Round", "52.90", "60", "60", "45/48/51"),
    ("K-F-058", "Kids Wooden Moon Table (Standard Size)", "93.24", "155", "86", "51"),
    ("K-F-059", "Kids Wooden Moon Table (Big Size)", "113.14", "180", "86", "51"),
    ("K-F-060", "Kids Wooden Chair 1", "21.48", "28", "30", "28/51"),
    ("K-F-061", "Kids Wooden Chair 2", "21.48", "28", "30", "26/48"),
    ("K-F-062", "Kids Wooden Chair 3", "20.43", "24", "23", "20"),
    ("K-F-063", "Double Layer Wooden Shelf for Montessori Material", "50.81", "120", "30", "35"),
    ("K-F-064", "Three Layer Wooden Shelf for Montessori Material", "68.10", "120", "30", "65"),
    ("K-F-065", "Four Layer Wooden Shelf for Montessori Material", "80.14", "120", "30", "80"),
    ("K-F-066", "Corner Cabinet", "52.90", "30", "30", "80"),
    ("K-F-067", "Towel Rack", "43.48", "90", "40", "90"),
    ("K-F-068", "Easel with Cabinet", "188.57", "97", "30", "90"),
    ("K-F-069", "Storage Cabinet 1", "75.43", "120", "30", "80"),
    ("K-F-070", "Storage Cabinet 2", "75.43", "120", "30", "80"),
    ("K-F-071", "Storage Cabinet 3", "81.19", "120", "30", "80"),
    ("K-F-072", "Storage Cabinet 4", "99.52", "120", "30", "110"),
    ("K-F-073", "Storage Cabinet 5", "122.05", "120", "30", "80"),
    ("K-F-074", "Locker Storage Cabinet", "348.33", "108", "40", "95"),
    ("K-F-075", "Bookshelf", "75.43", "80", "40", "90"),
    ("K-F-076", "Cup Cabinet", "110.00", "55", "45", "80"),
    ("K-F-077", "Big Toy Cabinet with Seat", "770.00", "205", "115", "60"),
    ("K-F-078", "Double Layer Toy Cabinet", "680.95", "205", "120", "90"),
    ("K-F-079", "Kids Cloth Cabinet", "188.57", "120", "120", "30"),
    ("K-F-080", "Kids Shoes Cabinet", "41.90", "120", "22", "35"),
    ("K-F-081", "Outdoor Climbing Set", "785.00", None, None, None),
    ("K-F-082", "Indoor Climbing Set", "521.71", None, None, None),
    ("K-F-083", "Toys Storage Cabinet Set", "757.00", "430", "30", "140"),
    ("K-F-084", "Storage Cabinet for Kids", "565.00", "360", "30", "110"),
    ("K-F-085", "Role Play Set", "529.00", "200", "31", "80"),
]


def _mm(value: str | None) -> Decimal | None:
    if not value or "/" in value:
        return None
    try:
        return Decimal(value) * Decimal("10")
    except InvalidOperation:
        return None


def _dimension_text(length: str | None, width: str | None, height: str | None) -> str | None:
    if not any((length, width, height)):
        return None
    return f"{length or '-'} x {width or '-'} x {height or '-'} cm"


def main() -> None:
    session = get_session_factory()()
    created = 0
    skipped = 0
    images_added = 0
    try:
        category = session.scalar(
            select(ProductCategory).where(ProductCategory.name == CATEGORY_NAME)
        )
        if category is None:
            category = ProductCategory(name=CATEGORY_NAME, sort_order=10)
            session.add(category)
            session.flush()

        for sku, name, price, length, width, height in PRODUCTS:
            product = session.scalar(select(Product).where(Product.sku == sku))
            if product is None:
                product = Product(
                    sku=sku,
                    name=name,
                    category_id=category.id,
                    material="Solid Wood",
                    dimension_text=_dimension_text(length, width, height),
                    length_mm=_mm(length),
                    width_mm=_mm(width),
                    height_mm=_mm(height),
                    unit="piece",
                    reference_price=Decimal(price),
                    currency_code="USD",
                    description=SOURCE_NOTE,
                    is_active=True,
                )
                session.add(product)
                session.flush()
                created += 1
            else:
                skipped += 1

            if not session.scalar(
                select(ProductImage.id).where(ProductImage.product_id == product.id)
            ):
                session.add(
                    ProductImage(
                        product_id=product.id,
                        image_url=f"{IMAGE_BASE_URL}/{sku}.jpg",
                        is_primary=True,
                        sort_order=0,
                    )
                )
                images_added += 1

        session.commit()
        print(
            "Wooden furniture import complete: "
            f"created={created}, skipped={skipped}, images_added={images_added}."
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
