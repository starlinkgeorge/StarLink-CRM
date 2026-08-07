"""Add versioned quotations and immutable item snapshots.

Revision ID: 0009_add_quotations
Revises: 0008_add_product_catalog
Create Date: 2026-08-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0009_add_quotations"
down_revision: str | None = "0008_add_product_catalog"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

quotation_status = postgresql.ENUM(
    "Draft",
    "Sent",
    "Accepted",
    "Rejected",
    "Expired",
    name="quotation_status",
    create_type=False,
)


def upgrade() -> None:
    quotation_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "quotations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("quotation_number", sa.String(length=50), nullable=False),
        sa.Column(
            "customer_id",
            sa.BigInteger(),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "opportunity_id",
            sa.BigInteger(),
            sa.ForeignKey("opportunities.id", ondelete="SET NULL"),
        ),
        sa.Column("status", quotation_status, nullable=False, server_default="Draft"),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
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
    op.create_index("uq_quotations_number", "quotations", ["quotation_number"], unique=True)
    op.create_index("ix_quotations_customer_id", "quotations", ["customer_id"])
    op.create_index("ix_quotations_opportunity_id", "quotations", ["opportunity_id"])
    op.create_index("ix_quotations_status", "quotations", ["status"])

    op.create_table(
        "quotation_versions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "quotation_id",
            sa.BigInteger(),
            sa.ForeignKey("quotations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("payment_term", sa.String(length=500), nullable=False),
        sa.Column("delivery_time", sa.String(length=500), nullable=False),
        sa.Column("validity_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("shipping_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("pdf_url", sa.String(length=1000)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("quotation_id", "version_no", name="uq_quotation_version_no"),
    )
    op.create_index("ix_quotation_versions_quotation_id", "quotation_versions", ["quotation_id"])

    op.create_table(
        "quotation_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "quotation_version_id",
            sa.BigInteger(),
            sa.ForeignKey("quotation_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.BigInteger(),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
        ),
        sa.Column("sku_snapshot", sa.String(length=80), nullable=False),
        sa.Column("product_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("picture_snapshot", sa.String(length=1000)),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
    )
    op.create_index("ix_quotation_items_version_id", "quotation_items", ["quotation_version_id"])
    op.create_index("ix_quotation_items_product_id", "quotation_items", ["product_id"])


def downgrade() -> None:
    op.drop_table("quotation_items")
    op.drop_table("quotation_versions")
    op.drop_table("quotations")
    quotation_status.drop(op.get_bind(), checkfirst=True)
