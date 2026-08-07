"""Add Lead inquiries and base opportunities.

Revision ID: 0006_add_leads_opportunities
Revises: 0005_repair_v3_customer_columns
Create Date: 2026-08-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0006_add_leads_opportunities"
down_revision: str | None = "0005_repair_v3_customer_columns"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

lead_status = postgresql.ENUM(
    "New",
    "Contacted",
    "Qualified",
    "Converted",
    "Lost",
    name="lead_status",
    create_type=False,
)
customer_status = postgresql.ENUM(
    "Lead",
    "Contacted",
    "Quotation",
    "Negotiation",
    "Won",
    "Lost",
    name="customer_status",
    create_type=False,
)


def upgrade() -> None:
    lead_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "leads",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("public_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("contact_name", sa.String(length=120), nullable=False),
        sa.Column("country", sa.String(length=100)),
        sa.Column("email", sa.String(length=320)),
        sa.Column("phone", sa.String(length=50)),
        sa.Column("whatsapp", sa.String(length=50)),
        sa.Column("source", sa.String(length=80)),
        sa.Column("inquiry_content", sa.Text()),
        sa.Column("interested_product", sa.String(length=500)),
        sa.Column("status", lead_status, nullable=False, server_default="New"),
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
        sa.UniqueConstraint("public_id", name="uq_leads_public_id"),
    )
    for column_name in ("company_name", "email", "source", "status", "created_at"):
        op.create_index(f"ix_leads_{column_name}", "leads", [column_name])

    op.create_table(
        "opportunities",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("public_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "customer_id",
            sa.BigInteger(),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_lead_id",
            sa.BigInteger(),
            sa.ForeignKey("leads.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "owner_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("interested_product", sa.String(length=500)),
        sa.Column("stage", customer_status, nullable=False, server_default="Lead"),
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
        sa.UniqueConstraint("public_id", name="uq_opportunities_public_id"),
        sa.UniqueConstraint("source_lead_id", name="uq_opportunities_source_lead_id"),
    )
    for column_name in ("customer_id", "owner_id", "stage"):
        op.create_index(
            f"ix_opportunities_{column_name}", "opportunities", [column_name]
        )

    for table_name in ("leads", "opportunities"):
        op.execute(
            f"CREATE TRIGGER {table_name}_set_updated_at "
            f"BEFORE UPDATE ON {table_name} FOR EACH ROW "
            "EXECUTE FUNCTION set_updated_at();"
        )


def downgrade() -> None:
    for table_name in ("opportunities", "leads"):
        op.execute(f"DROP TRIGGER IF EXISTS {table_name}_set_updated_at ON {table_name};")
    op.drop_table("opportunities")
    op.drop_table("leads")
    lead_status.drop(op.get_bind(), checkfirst=True)
