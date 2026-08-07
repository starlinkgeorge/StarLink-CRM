"""Add product catalog and opportunity product lines.

Revision ID: 0008_add_product_catalog
Revises: 0007_expand_opportunities
Create Date: 2026-08-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0008_add_product_catalog"
down_revision: str | None = "0007_expand_opportunities"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_categories",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "parent_id",
            sa.BigInteger(),
            sa.ForeignKey("product_categories.id", ondelete="SET NULL"),
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_product_categories_parent_id", "product_categories", ["parent_id"])
    op.create_index("ix_product_categories_name", "product_categories", ["name"])

    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("sku", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "category_id",
            sa.BigInteger(),
            sa.ForeignKey("product_categories.id", ondelete="SET NULL"),
        ),
        sa.Column("material", sa.String(length=255)),
        sa.Column("dimension_text", sa.String(length=255)),
        sa.Column("length_mm", sa.Numeric(10, 2)),
        sa.Column("width_mm", sa.Numeric(10, 2)),
        sa.Column("height_mm", sa.Numeric(10, 2)),
        sa.Column("weight_kg", sa.Numeric(10, 3)),
        sa.Column("unit", sa.String(length=30), nullable=False, server_default="piece"),
        sa.Column("moq", sa.Integer()),
        sa.Column("reference_price", sa.Numeric(14, 2)),
        sa.Column("currency_code", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("uq_products_sku", "products", ["sku"], unique=True)
    op.create_index("ix_products_name", "products", ["name"])
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index("ix_products_is_active", "products", ["is_active"])

    op.create_table(
        "product_images",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "product_id",
            sa.BigInteger(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("image_url", sa.String(length=1000), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_product_images_product_id", "product_images", ["product_id"])
    op.create_index(
        "uq_product_images_one_primary",
        "product_images",
        ["product_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )

    op.create_table(
        "opportunity_products",
        sa.Column(
            "opportunity_id",
            sa.BigInteger(),
            sa.ForeignKey("opportunities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "product_id",
            sa.BigInteger(),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False, server_default="1"),
        sa.Column("target_price", sa.Numeric(14, 2)),
    )
    op.create_index("ix_opportunity_products_product_id", "opportunity_products", ["product_id"])


def downgrade() -> None:
    op.drop_table("opportunity_products")
    op.drop_table("product_images")
    op.drop_table("products")
    op.drop_table("product_categories")
