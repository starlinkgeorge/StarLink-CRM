"""Import the 2025 StarLink Outdoor Playthings catalogue into the CRM.

The customer-supplied catalogue has repeated printed model codes (JT-06,
JT-07, and G3).  A CRM SKU must be unique, so the distinct products use the
unambiguous suffixes shown below while their original model remains in the
description.  The import is idempotent: existing products are not overwritten
and an image is added only when a product currently has no image.

Run inside the rebuilt backend container:
    python scripts/import_outdoor_playthings_catalog.py
"""

from decimal import Decimal, InvalidOperation
from os import getenv
from pathlib import Path
import re
import sys

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import get_session_factory
from app.models.product import Product, ProductCategory, ProductImage


ROOT_CATEGORY_NAME = "2025 Outdoor Playthings"
CATEGORY_ORDER = (
    "Sand & Water Play",
    "Nature & Planting",
    "Outdoor Art & Creative",
    "Outdoor Living",
    "Outdoor Role Play",
    "Outdoor Traffic",
    "Outdoor Custom Products",
)
IMAGE_BASE_URL = getenv(
    "PRODUCT_IMAGE_BASE_URL", "/product-images"
).rstrip("/")
SOURCE_NOTE = "Imported from the 2025 StarLink Outdoor Playthings catalogue."
WOOD_MATERIAL = (
    "Finnish pine with ACQ anti-corrosion treatment and outdoor paint"
)

# category, CRM SKU, product name, USD price, catalogue dimensions, material,
# extracted image filename (or None when the source catalogue has no matching
# product image). Dimensions are kept verbatim in dimension_text.
PRODUCTS = [
    ("Sand & Water Play", "SS-10", "Sand Play Set", "380.00", "3-piece set", WOOD_MATERIAL, "SS-10.jpg"),
    ("Sand & Water Play", "SS-11", "Transport Sand Screening Set", "396.00", "3-piece set", WOOD_MATERIAL, "SS-11.jpg"),
    ("Sand & Water Play", "SS-09", "Sand and Water Play Area Set", "1656.00", "33-piece set", WOOD_MATERIAL, "SS-09.jpg"),
    ("Sand & Water Play", "SS-08", "Sand and Water Set", "2057.00", "18-piece set", "Anticorrosive wood, PP plastic", "SS-08.jpg"),
    ("Sand & Water Play", "SS-01", "Multifunctional Water Wall", "423.00", "123 x 60 x 146 cm", WOOD_MATERIAL, "SS-01.jpg"),
    ("Sand & Water Play", "SS-03", "Spiral Sand Play", "132.00", "60 x 28 x 85 cm", WOOD_MATERIAL, "SS-03.jpg"),
    ("Sand & Water Play", "SS-04", "Ferris Wheel Sand Play", "132.00", "60 x 28 x 85 cm", WOOD_MATERIAL, "SS-04.jpg"),
    ("Sand & Water Play", "SS-05", "Playing Sand Balance", "127.00", "100 x 28 x 93 cm", WOOD_MATERIAL, "SS-05.jpg"),
    ("Sand & Water Play", "SS-06", "Sand Screening Table", "132.00", "65 x 50 x 72 cm", WOOD_MATERIAL, "SS-06.jpg"),
    ("Sand & Water Play", "JT-06-UNICYCLE", "Unicycle", "139.00", "107 x 48 x 32 cm", WOOD_MATERIAL, "JT-06-UNICYCLE.jpg"),
    ("Sand & Water Play", "SS-02", "Sand Dump Truck", "132.00", "60 x 48 x 31 cm", WOOD_MATERIAL, "SS-02.jpg"),
    ("Sand & Water Play", "JT-07-CRANE", "Crane", "370.00", "100 x 86 x 103 cm", WOOD_MATERIAL, "JT-07-CRANE.jpg"),
    ("Sand & Water Play", "SS-07", "Excavator", "423.00", "170 x 54 x 96 cm", WOOD_MATERIAL, "SS-07.jpg"),
    ("Sand & Water Play", "SS-039", "Windmill Water Tank", "206.00", "70 x 40 x 91 cm", "PP plastic and anticorrosive wood", "SS-039.jpg"),
    ("Sand & Water Play", "SS-040", "Sand and Water Conveyor", "529.00", "91 x 39 x 100 cm", "PP, acrylic, nylon, aluminium", "SS-040.jpg"),
    ("Sand & Water Play", "SS-041", "Multifunctional Water Table", "106.00", "58 x 44 x 114 cm", "Wood-grain board, acrylic, plastic", "SS-041.jpg"),
    ("Sand & Water Play", "SS-042", "Sand and Water Play Table", "238.00", "117 x 103 x 52 cm", "Anticorrosive wood and acrylic plastic", "SS-042.jpg"),
    ("Sand & Water Play", "SS-043", "Flat Hourglass", "119.00", "38 x 26 x 63 cm", "Anticorrosive wood and PP plastic", "SS-043.jpg"),
    ("Sand & Water Play", "HTN038-21", "Shovel (Small)", "3.50", "34 x 7 cm", "Stainless steel", "HTN038-21.jpg"),
    ("Sand & Water Play", "HTN038-22", "Shovel (Large)", "6.00", "65 x 14 cm", "Stainless steel", "HTN038-22.jpg"),
    ("Sand & Water Play", "HTN038-26", "Sand Bucket", "11.00", "Diameter 25 cm", "Stainless steel", "HTN038-26.jpg"),
    ("Sand & Water Play", "XTGWG-158", "Sand and Water Suit", "22.50", "M to 3XL", "Fabric and rubber", "XTGWG-158.jpg"),
    ("Nature & Planting", "ZZ-10", "Outdoor Natural Planting Area Set", "3390.00", "73-piece set", "Anticorrosive wood, PP plastic, PVC", "ZZ-10.jpg"),
    ("Nature & Planting", "ZZ-08", "Vine Planting Rack Style A", "159.00", "110 x 40.5 x 108.5 cm", WOOD_MATERIAL, "ZZ-08.jpg"),
    ("Nature & Planting", "ZZ-09", "Vine Planting Rack Style B", "159.00", "110 x 40.5 x 108.5 cm", WOOD_MATERIAL, "ZZ-09.jpg"),
    ("Nature & Planting", "ZZ-01", "Modular Planting Rack", "251.00", "125 x 35 x 86 cm", WOOD_MATERIAL, "ZZ-01.jpg"),
    ("Nature & Planting", "ZZ-02", "Three-sided Planting Rack", "225.00", "56 x 56 x 118 cm", WOOD_MATERIAL, "ZZ-02.jpg"),
    ("Nature & Planting", "ZZ-03", "Box Type Three-dimensional Planting Rack", "132.00", "50 x 38 x 72 cm", WOOD_MATERIAL, "ZZ-03.jpg"),
    ("Nature & Planting", "ZZ-03G", "Pipeline Three-dimensional Planting Rack", "146.00", "50 x 43 x 75 cm", WOOD_MATERIAL, "ZZ-03G.jpg"),
    ("Nature & Planting", "ZZ-04", "Root Observation Box", "370.00", "96 x 48 x 120 cm", WOOD_MATERIAL, "ZZ-04.png"),
    ("Nature & Planting", "ZZ-07", "Plant Observation Hut", "609.00", "108 x 150 x 125 cm", WOOD_MATERIAL, "ZZ-07.jpg"),
    ("Nature & Planting", "XTG066", "Happy Waterwheel", "175.00", "70 x 40 x 61 cm", "Pine wood, PE plastic, metal", "XTG066.jpg"),
    ("Nature & Planting", "ZZ-06M", "Planting Blackboard (Small)", "233.00", "86 x 60 x 100 cm", WOOD_MATERIAL, "ZZ-06M.jpg"),
    ("Nature & Planting", "ZZ-06L", "Planting Blackboard (Large)", "265.00", "106 x 60 x 120 cm", WOOD_MATERIAL, "ZZ-06L.jpg"),
    ("Nature & Planting", "ZZ-05S", "Small Rest Area", "132.00", "110 x 40 x 21 cm", WOOD_MATERIAL, "ZZ-05S.jpg"),
    ("Nature & Planting", "ZZ-05M", "Middle Rest Area", "177.00", "130 x 40 x 36 cm", WOOD_MATERIAL, "ZZ-05M.jpg"),
    ("Nature & Planting", "ZZ-05L", "Large Rest Area", "212.00", "150 x 40 x 52 cm", WOOD_MATERIAL, "ZZ-05L.jpg"),
    ("Nature & Planting", "RF-A063G", "Insect Cage", "6.90", "20 x 15 x 13.5 cm", "Plastic", "RF-A063G.jpg"),
    ("Nature & Planting", "RF-A001-A", "Goldfish Tank Magnifying Glass", "6.90", "15 x 10 x 10 cm", "Plastic", "RF-A001-A.jpg"),
    ("Nature & Planting", "RF-A003-5", "Insect Cup", "3.50", "7 x 7 x 7 cm", "Plastic", "RF-A003-5.jpg"),
    ("Nature & Planting", "RF-A003-6", "Portable Insect Cup", "5.30", "10 x 13 x 8 cm", "Plastic", "RF-A003-6.jpg"),
    ("Nature & Planting", "RF-D0102", "Magnifier (75 mm, 5x)", "3.50", "75 mm", "Plastic", "RF-D0102.jpg"),
    ("Nature & Planting", "RF-A003-6-13", "Insect Net", "3.50", "38 cm", "Plastic", "RF-A003-6-13.jpg"),
    ("Outdoor Art & Creative", "YS-01", "Material Collection Graffiti Table", "225.00", "65 x 36 x 109 cm", WOOD_MATERIAL, "YS-01.jpg"),
    ("Outdoor Art & Creative", "YS-02", "Washing Cabinet", "529.00", "100 x 42 x 148 cm", WOOD_MATERIAL, "YS-02.jpg"),
    ("Outdoor Art & Creative", "YS-04", "Double-sided Drawing Board", "529.00", "100 x 98 x 87 cm", WOOD_MATERIAL, "YS-04.png"),
    ("Outdoor Art & Creative", "YS-05", "Works Display Cabinet (4 Layers)", "529.00", "80 x 30 x 150 cm", WOOD_MATERIAL, "YS-05.jpg"),
    ("Outdoor Living", "HW-12", "Kitchen Worktop Set", "1853.00", "13-piece set", WOOD_MATERIAL, "HW-12.jpg"),
    ("Outdoor Living", "HW-13", "Campfire Game Set", "662.00", "7-piece set", WOOD_MATERIAL, "HW-13.jpg"),
    ("Outdoor Living", "HW-01", "Spliced Benches", "381.00", "95 x 19.7 x 30 cm, 6-piece set", WOOD_MATERIAL, "HW-01.jpg"),
    ("Outdoor Living", "HW-02", "Spliced Dining Table", "999.00", "115 x 35 x 60 cm, 6-piece set", WOOD_MATERIAL, "HW-02.png"),
    ("Outdoor Living", "HW-03", "Kitchen Worktop", "472.00", "120 x 45 x 155 cm", WOOD_MATERIAL, "HW-03.jpg"),
    ("Outdoor Living", "HW-07", "Campfire Game Stand", "280.00", "100 x 65 x 91 cm", WOOD_MATERIAL, "HW-07.jpg"),
    ("Outdoor Living", "HW-04", "Barbecue Grill", "397.00", "130 x 57 x 155 cm", WOOD_MATERIAL, "HW-04.png"),
    ("Outdoor Living", "HW-05", "Outdoor Tent", "794.00", "130 x 100 x 140 cm", WOOD_MATERIAL, "HW-05.jpg"),
    ("Outdoor Living", "HW-06", "Outdoor Trash Can", "212.00", "65 x 32 x 86 cm", WOOD_MATERIAL, "HW-06.jpg"),
    ("Outdoor Living", "HW-10", "Outdoor Dining Table Set", "132.00", "Table 81 x 54 x 47.7 cm; umbrella 120 cm", "Fir wood and rainproof cloth", "HW-10.jpg"),
    ("Outdoor Living", "XTG048", "Mobile Dining Car", "199.00", "120 x 43 x 63 cm", "Fir wood board", "XTG048.jpg"),
    ("Outdoor Role Play", "JS-01", "Restaurant Set", "1130.00", "4-piece set", WOOD_MATERIAL, "JS-01.jpg"),
    ("Outdoor Role Play", "JS-02", "Dessert Shop Set", "1059.00", "4-piece set", WOOD_MATERIAL, "JS-02.jpg"),
    ("Outdoor Role Play", "JS-03", "Fruit Shop Set", "1059.00", "4-piece set", WOOD_MATERIAL, "JS-03.jpg"),
    ("Outdoor Role Play", "JS-04", "Express Station Set", "1474.00", "6-piece set", WOOD_MATERIAL, "JS-04.jpg"),
    ("Outdoor Role Play", "G1", "Short Straight Cabinet", "206.00", "77 x 35 x 60 cm", WOOD_MATERIAL, "G1.jpg"),
    ("Outdoor Role Play", "G3", "Sloped Cabinet", "249.00", "102 x 36 x 60 cm", WOOD_MATERIAL, "G3.jpg"),
    ("Outdoor Role Play", "G3-BLACKBOARD", "Blackboard Long Straight Cabinet", "249.00", "102 x 36 x 60 cm", WOOD_MATERIAL, "G3-BLACKBOARD.jpg"),
    ("Outdoor Role Play", "J2", "Stacking Racks", "180.00", "58 x 58 x 100 cm", WOOD_MATERIAL, "J2.jpg"),
    ("Outdoor Traffic", "JT-07-SET", "Transshipment Terminal Set", "1146.00", "6-piece set", WOOD_MATERIAL, "JT-07-SET.jpg"),
    ("Outdoor Traffic", "JT-06-SET", "Security Gate Set", "630.00", "3-piece set", WOOD_MATERIAL, "JT-06-SET.jpg"),
    ("Outdoor Custom Products", "HWDZ-01", "Colorful House", "529.00", "Top 60 cm; height 120 cm; base 120 x 110 cm", "Anticorrosive wood and acrylic", "HWDZ-01.jpg"),
    ("Outdoor Custom Products", "HWDZ-02", "Outdoor Drawing Board", "238.00", "100 x 60 x 75 cm", "Anticorrosive wood and acrylic", "HWDZ-02.jpg"),
    ("Outdoor Custom Products", "HWDZ-03", "Outdoor Stool", "172.00", "100 x 38 x 70 cm", WOOD_MATERIAL, "HWDZ-03.jpg"),
]


def _decimal(value: str) -> Decimal:
    return Decimal(value)


def _dimensions_mm(value: str) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    match = re.fullmatch(
        r"\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*cm\s*",
        value,
        flags=re.IGNORECASE,
    )
    if not match:
        return None, None, None
    try:
        return tuple(Decimal(part) * Decimal("10") for part in match.groups())
    except InvalidOperation:
        return None, None, None


def _get_or_create_category(
    session, name: str, parent_id: int | None, sort_order: int
) -> ProductCategory:
    category = session.scalar(
        select(ProductCategory).where(
            ProductCategory.name == name,
            ProductCategory.parent_id == parent_id,
        )
    )
    if category is None:
        category = ProductCategory(
            name=name, parent_id=parent_id, sort_order=sort_order
        )
        session.add(category)
        session.flush()
    return category


def _catalogue_model(sku: str) -> str:
    """Return the printed model code where the catalogue reused a SKU."""
    return {
        "JT-06-UNICYCLE": "JT-06",
        "JT-07-CRANE": "JT-07",
        "JT-07-SET": "JT-07",
        "JT-06-SET": "JT-06",
        "G3-BLACKBOARD": "G3",
    }.get(sku, sku)


def main() -> None:
    session = get_session_factory()()
    created = 0
    skipped = 0
    images_added = 0
    try:
        root = _get_or_create_category(session, ROOT_CATEGORY_NAME, None, 30)
        categories = {
            name: _get_or_create_category(session, name, root.id, index + 1)
            for index, name in enumerate(CATEGORY_ORDER)
        }

        for category_name, sku, name, price, dimensions, material, image in PRODUCTS:
            product = session.scalar(select(Product).where(Product.sku == sku))
            if product is None:
                length_mm, width_mm, height_mm = _dimensions_mm(dimensions)
                product = Product(
                    sku=sku,
                    name=name,
                    category_id=categories[category_name].id,
                    material=material,
                    dimension_text=dimensions,
                    length_mm=length_mm,
                    width_mm=width_mm,
                    height_mm=height_mm,
                    unit="piece",
                    reference_price=_decimal(price),
                    currency_code="USD",
                    description=(
                        f"{SOURCE_NOTE} Original catalogue model: "
                        f"{_catalogue_model(sku)}."
                    ),
                    is_active=True,
                )
                session.add(product)
                session.flush()
                created += 1
            else:
                skipped += 1

            if image and not session.scalar(
                select(ProductImage.id).where(ProductImage.product_id == product.id)
            ):
                session.add(
                    ProductImage(
                        product_id=product.id,
                        image_url=f"{IMAGE_BASE_URL}/{image}",
                        is_primary=True,
                        sort_order=0,
                    )
                )
                images_added += 1

        session.commit()
        print(
            "Outdoor playthings import complete: "
            f"created={created}, skipped={skipped}, images_added={images_added}."
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
