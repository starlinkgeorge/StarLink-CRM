"""Add workbook-aligned customer archive fields without replacing customers.

The customer archive is additive by design: existing customer IDs and all
foreign-key relationships (contacts, opportunities, quotations, inquiries and
follow-ups) remain untouched.

Revision ID: 0019_customer_archive_fields
Revises: 0018_repair_v10_opportunity_reminder_schema
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0019_customer_archive_fields"
down_revision: str | None = "0018_repair_v10_opportunity_reminder_schema"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Add archive fields and backfill only equivalent legacy values."""
    op.add_column("customers", sa.Column("customer_acquired_at", sa.Date(), nullable=True))
    op.add_column("customers", sa.Column("position", sa.String(length=120), nullable=True))
    op.add_column("customers", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("customers", sa.Column("customer_level_value", sa.Integer(), nullable=True))
    op.add_column("customers", sa.Column("customer_size", sa.Integer(), nullable=True))
    op.add_column("customers", sa.Column("customer_total_score", sa.Integer(), nullable=True))
    op.add_column("customers", sa.Column("followup_stage", sa.String(length=120), nullable=True))
    op.add_column(
        "customers", sa.Column("automatic_stage_judgement", sa.String(length=120), nullable=True)
    )
    op.add_column("customers", sa.Column("latest_followup_date", sa.Date(), nullable=True))
    op.add_column("customers", sa.Column("response_status", sa.String(length=80), nullable=True))
    op.add_column("customers", sa.Column("followup_requirement", sa.String(length=80), nullable=True))
    op.add_column("customers", sa.Column("archive_import_key", sa.String(length=160), nullable=True))

    op.create_index("ix_customers_customer_acquired_at", "customers", ["customer_acquired_at"])
    op.create_index("ix_customers_followup_stage", "customers", ["followup_stage"])
    op.create_index("ix_customers_latest_followup_date", "customers", ["latest_followup_date"])
    op.create_index("ix_customers_followup_requirement", "customers", ["followup_requirement"])
    op.create_unique_constraint("uq_customers_archive_import_key", "customers", ["archive_import_key"])

    # Existing CRM sales stages are equivalent to the workbook's follow-up
    # stage. Keep both representations so legacy dashboards/API filters keep
    # their established enum values while the archive UI uses workbook labels.
    # Unicode escapes keep this migration safe even if a Windows terminal uses
    # a legacy non-UTF-8 code page.
    op.execute(
        sa.text(
            """
            UPDATE customers
            SET followup_stage = CASE COALESCE(sales_stage::text, status::text)
                WHEN 'Lead' THEN :lead
                WHEN 'Contacted' THEN :contacted
                WHEN 'Quotation' THEN :quotation
                WHEN 'Negotiation' THEN :negotiation
                WHEN 'Won' THEN :won
                WHEN 'Lost' THEN :lost
                ELSE NULL
            END
            WHERE followup_stage IS NULL
            """
        ).bindparams(
            lead="\u65b0\u5f00\u53d1\u672a\u56de\u590d",
            contacted="\u65b0\u5f00\u53d1\u5df2\u56de\u590d",
            quotation="\u5df2\u62a5\u4ef7",
            negotiation="\u8c08\u5224\u4e2d",
            won="\u5df2\u6210\u4ea4",
            lost="\u5df2\u8f93\u5355",
        )
    )
    op.execute(
        """
        UPDATE customers
        SET latest_followup_date = last_followup_at::date
        WHERE latest_followup_date IS NULL AND last_followup_at IS NOT NULL
        """
    )


def downgrade() -> None:
    """Keep archive columns intact to avoid deleting imported customer data."""
    # This migration deliberately has a data-safe no-op downgrade. Rolling
    # back the Alembic pointer must not discard imported customer information.
    pass
