"""Add V8 Alibaba inquiry management and source context.

Revision ID: 0015_v8_alibaba_inquiry_management
Revises: 0014_v7_sales_pipeline
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0015_v8_alibaba_inquiry_management"
down_revision: str | None = "0014_v7_sales_pipeline"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("source_platform", sa.String(length=80)))
    op.add_column("customers", sa.Column("original_inquiry", sa.Text()))
    op.execute(
        """
        UPDATE customers
        SET source_platform = source
        WHERE source_platform IS NULL AND source IS NOT NULL
        """
    )
    op.create_index("ix_customers_source_platform", "customers", ["source_platform"])

    op.create_table(
        "inquiries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("public_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "customer_id",
            sa.BigInteger(),
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "converted_opportunity_id",
            sa.BigInteger(),
            sa.ForeignKey("opportunities.id", ondelete="SET NULL"),
        ),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("contact_name", sa.String(length=120), nullable=False),
        sa.Column("country", sa.String(length=100)),
        sa.Column("email", sa.String(length=320)),
        sa.Column("phone", sa.String(length=50)),
        sa.Column("whatsapp", sa.String(length=50)),
        sa.Column("source", sa.String(length=80), nullable=False, server_default="Alibaba"),
        sa.Column(
            "source_platform", sa.String(length=80), nullable=False, server_default="Alibaba"
        ),
        sa.Column("interested_product", sa.String(length=500)),
        sa.Column("inquiry_content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="New"),
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
        sa.CheckConstraint(
            "status IN ('New', 'Processing', 'Converted', 'Closed')",
            name="ck_inquiries_status",
        ),
        sa.UniqueConstraint("public_id", name="uq_inquiries_public_id"),
        sa.UniqueConstraint(
            "converted_opportunity_id", name="uq_inquiries_converted_opportunity_id"
        ),
    )
    for column_name in (
        "customer_id",
        "company_name",
        "country",
        "email",
        "source",
        "source_platform",
        "status",
        "created_at",
    ):
        op.create_index(f"ix_inquiries_{column_name}", "inquiries", [column_name])
    op.execute(
        "CREATE TRIGGER inquiries_set_updated_at "
        "BEFORE UPDATE ON inquiries FOR EACH ROW "
        "EXECUTE FUNCTION set_updated_at();"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS inquiries_set_updated_at ON inquiries;")
    op.drop_table("inquiries")
    op.drop_index("ix_customers_source_platform", table_name="customers")
    op.drop_column("customers", "original_inquiry")
    op.drop_column("customers", "source_platform")
