"""Import the 2025 solid-wood product catalogue into the CRM product table.

The import is idempotent: products whose SKU already exists are skipped so the
operation does not overwrite catalogue data already maintained in the CRM.
Run inside the backend container with:
    python scripts/import_product_catalog.py
"""

from pathlib import Path
import sys

from sqlalchemy import select

# Support both ``python scripts/import_product_catalog.py`` and module-style
# execution from the backend container's /app working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import get_session_factory
from app.models.product import Product, ProductCategory


CATEGORY_NAME = "Solid Wood Furniture"

PRODUCTS = [
    ("SL-F-001", "幼儿椅", "Kids Chair", "Solid Rubber Wood", "23"),
    ("SL-F-002", "月牙桌", "Small Moon Table", "Solid Rubber Wood", "55"),
    ("SL-F-003", "半圆桌", "Semicircle Table", "Solid Rubber Wood", "65"),
    ("SL-F-004", "梯形桌", "Trapezoid Table", "Solid Rubber Wood", "62"),
    ("SL-F-005", "直角拐角柜", "Right Angle Cabinet", "Solid Rubber Wood", "89"),
    ("SL-F-006", "黑白版柜", "Storage Cabinet With Black And White Board", "Solid Pine Wood", "135"),
    ("SL-F-007", "婴儿摇椅", "Baby Rocking Chair", "Solid Birch Plywood", "98"),
    ("SL-F-008", "单人沙发", "Single Sofa", "Solid Rubber Wood", "45"),
    ("SL-F-009", "双人沙发", "Double Sofa", "Solid Rubber Wood", "65"),
    ("SL-F-010", "阅读组合区", "Reading Center", "Solid Rubber Wood", "315"),
    ("SL-F-011", "娃娃婴儿床", "Doll Crib", "Solid Beech Wood", "53"),
    ("SL-F-012", "婴儿推车", "Baby Stroller", "Solid Beech Wood", "66"),
    ("SL-F-013", "书包柜", "Bag Cabinet", "Solid Birch Plywood", "189"),
    ("SL-F-014", "尿布台 1", "Changing Table 1", "Solid Rubber Wood", "349"),
    ("SL-F-015", "尿布台 2", "Changing Table 2", "Solid Rubber Wood", "359"),
    ("SL-F-016", "学步梯", "Learning Stairs", "Solid Rubber Wood", "148"),
    ("SL-F-017", "学步梯+滑梯", "Learning Stairs With Slides", "Solid Rubber Wood", "599"),
    ("SL-F-018", "角落组合柜 1", "Corner Cabinet Combination 1", "Solid Pine Wood", "555"),
    ("SL-F-019", "角落组合柜 2", "Corner Cabinet Combination 2", "Solid Pine Wood", "529"),
    ("SL-F-020", "角落组合柜 3", "Corner Cabinet Combination 3", "Solid Pine Wood", "529"),
    ("SL-F-021", "角落组合柜 4", "Corner Cabinet Combination 4", "Solid Pine Wood", "529"),
    ("SL-F-022", "角落组合柜 5", "Corner Cabinet Combination 5", "Solid Pine Wood", "499"),
    ("SL-F-023", "角落组合柜 6", "Corner Cabinet Combination 6", "Solid Pine Wood", "499"),
    ("SL-F-024", "角落组合柜 7", "Corner Cabinet Combination 7", "Solid Pine Wood", "499"),
    ("SL-F-025", "多功能三面椅", "Multifunctional Three Sided Chair", "Solid Beech Wood", "39"),
    ("SL-F-026", "板条椅", "Slatted Chair", "Solid Beech Wood", "29"),
    ("SL-F-027", "升降扶手椅", "Height Adjustable Chair", "Solid Beech Wood", "39"),
    ("SL-F-028", "小熊椅", "Bear Shape Chair", "Solid Beech Wood", "39"),
    ("SL-F-029", "可堆叠椅", "Stacking Chair", "Solid Beech Wood", "29"),
    ("SL-F-030", "月亮椅", "Moon Shape Chair", "Solid Beech Wood", "49"),
    ("SL-F-031", "云朵椅", "Clouds Shape Chair", "Solid Beech Wood", "49"),
    ("SL-F-032", "售卖台 1", "Selling Store 1", "Solid Beech Wood", "189"),
    ("SL-F-033", "售卖台 2", "Selling Store 2", "Solid Beech Wood", "198"),
    ("SL-F-034", "售卖台 3", "Selling Store 3", "Solid Beech Wood", "227"),
    ("SL-F-035", "售卖台组合", "Sales Area Combination", "Solid Beech Wood", "540"),
    ("SL-F-036", "玩具收纳柜 1", "Toy Storage Cabinet 1", "Solid Beech Wood", "99"),
    ("SL-F-037", "玩具收纳柜 2", "Toy Storage Cabinet 2", "Solid Beech Wood", "99"),
    ("SL-F-038", "玩水桌", "Water Play Table", "Solid Beech Wood", "95"),
    ("SL-F-039", "清洁套装", "Cleaning Set", "Solid Beech Wood", "49"),
    ("SL-F-040", "玩沙桌", "Sand Play Table", "Solid Beech Wood", "127"),
    ("SL-F-041", "长椅", "Bench", "Solid Beech Wood", "78"),
    ("SL-F-042", "攀爬镜", "Climbing Mirror", "Solid Beech Wood", "188"),
    ("SL-F-043", "学步镜", "Walking Mirror", "Solid Beech Wood", "188"),
    ("SL-F-044", "学步桥", "Learning Walking Bridge", "Solid Beech Wood", "211"),
    ("SL-F-045", "墙面学步扶手", "Wall Handrail For Learning Walking", "Solid Beech Wood", "29"),
]


def main() -> None:
    session = get_session_factory()()
    created = 0
    skipped = 0
    try:
        category = session.scalar(
            select(ProductCategory).where(ProductCategory.name == CATEGORY_NAME)
        )
        if category is None:
            category = ProductCategory(name=CATEGORY_NAME, sort_order=0)
            session.add(category)
            session.flush()

        for sku, chinese_name, english_name, material, price in PRODUCTS:
            if session.scalar(select(Product.id).where(Product.sku == sku)) is not None:
                skipped += 1
                continue
            session.add(
                Product(
                    sku=sku,
                    name=english_name,
                    category_id=category.id,
                    material=material,
                    unit="piece",
                    reference_price=price,
                    currency_code="USD",
                    description=(
                        f"Chinese name: {chinese_name}. "
                        "Imported from 2025 StarLink solid wood product list."
                    ),
                    is_active=True,
                )
            )
            created += 1

        session.commit()
        print(f"Product catalogue import complete: created={created}, skipped={skipped}.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
