"""Add the non-breaking V3 customer compatibility foundation.

Revision ID: 0003_v3_customer_foundation
Revises: 0002_add_authentication_state
Create Date: 2026-08-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003_v3_customer_foundation"
down_revision: str | None = "0002_add_authentication_state"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

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
    op.create_table(
        "lead_sources",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
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
        sa.UniqueConstraint("code", name="uq_lead_sources_code"),
        sa.UniqueConstraint("name", name="uq_lead_sources_name"),
    )

    lead_sources = sa.table(
        "lead_sources",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("position", sa.Integer()),
    )
    op.bulk_insert(
        lead_sources,
        [
            {"code": "alibaba", "name": "Alibaba", "position": 10},
            {"code": "website", "name": "Website", "position": 20},
            {"code": "facebook", "name": "Facebook", "position": 30},
            {"code": "linkedin", "name": "LinkedIn", "position": 40},
            {"code": "referral", "name": "Referral", "position": 50},
            {"code": "exhibition", "name": "Exhibition", "position": 60},
            {"code": "email", "name": "Email", "position": 70},
            {"code": "other", "name": "Other", "position": 80},
        ],
    )

    op.add_column("customers", sa.Column("public_id", postgresql.UUID(as_uuid=True)))
    op.add_column("customers", sa.Column("display_name", sa.String(length=255)))
    op.add_column("customers", sa.Column("customer_type", sa.String(length=80)))
    op.add_column("customers", sa.Column("country_code", sa.String(length=2)))
    op.add_column("customers", sa.Column("source_id", sa.BigInteger()))
    op.add_column("customers", sa.Column("interested_product", sa.String(length=500)))
    op.add_column("customers", sa.Column("rating", sa.String(length=1)))
    op.add_column("customers", sa.Column("lifecycle_status", sa.String(length=32)))
    op.add_column("customers", sa.Column("sales_stage", customer_status, nullable=True))
    op.execute("UPDATE customers SET sales_stage = status WHERE sales_stage IS NULL")
    op.alter_column(
        "customers",
        "sales_stage",
        existing_type=customer_status,
        nullable=False,
        server_default="Lead",
    )
    # The opportunities table is introduced by a later migration. Keep this
    # column nullable and add its foreign key only after that table exists.
    op.add_column("customers", sa.Column("primary_opportunity_id", sa.BigInteger()))
    op.add_column("customers", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.add_column("customers", sa.Column("version", sa.Integer()))
    op.create_foreign_key(
        "fk_customers_source_id_lead_sources",
        "customers",
        "lead_sources",
        ["source_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("contacts", sa.Column("public_id", postgresql.UUID(as_uuid=True)))
    op.add_column("contacts", sa.Column("is_primary", sa.Boolean()))
    op.add_column("contacts", sa.Column("updated_at", sa.DateTime(timezone=True)))
    op.add_column("contacts", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.add_column("contacts", sa.Column("version", sa.Integer()))


def downgrade() -> None:
    op.drop_column("contacts", "version")
    op.drop_column("contacts", "deleted_at")
    op.drop_column("contacts", "updated_at")
    op.drop_column("contacts", "is_primary")
    op.drop_column("contacts", "public_id")

    op.drop_constraint(
        "fk_customers_source_id_lead_sources", "customers", type_="foreignkey"
    )
    op.drop_column("customers", "version")
    op.drop_column("customers", "deleted_at")
    op.drop_column("customers", "primary_opportunity_id")
    op.drop_column("customers", "sales_stage")
    op.drop_column("customers", "lifecycle_status")
    op.drop_column("customers", "rating")
    op.drop_column("customers", "interested_product")
    op.drop_column("customers", "source_id")
    op.drop_column("customers", "country_code")
    op.drop_column("customers", "customer_type")
    op.drop_column("customers", "display_name")
    op.drop_column("customers", "public_id")

    op.drop_table("lead_sources")
