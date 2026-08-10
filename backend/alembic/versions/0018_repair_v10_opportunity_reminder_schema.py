"""Repair V10 reminder columns on databases with a stale Alembic stamp.

Some existing local databases recorded the V10 revision even though a prior
container start stopped after applying only part of its additive DDL. Keep the
historical migration immutable and make the required schema idempotent here.

Revision ID: 0018_repair_v10_opportunity_reminder_schema
Revises: 0017_v10_sales_followup_reminders
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0018_repair_v10_opportunity_reminder_schema"
down_revision: str | None = "0017_v10_sales_followup_reminders"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Ensure all ORM-required V10 reminder fields are present and populated."""
    op.execute("SELECT pg_advisory_xact_lock(916202611);")

    op.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS next_followup_date DATE")
    op.execute(
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS "
        "last_followup_at TIMESTAMP WITH TIME ZONE"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_customers_next_followup_date "
        "ON customers (next_followup_date)"
    )

    op.execute(
        "ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS "
        "last_activity_at TIMESTAMP WITH TIME ZONE"
    )
    op.execute(
        "ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS "
        "last_followup_at TIMESTAMP WITH TIME ZONE"
    )
    op.execute(
        "ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS "
        "quotation_sent_at TIMESTAMP WITH TIME ZONE"
    )
    op.execute(
        "ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS "
        "quote_followup_due_date DATE"
    )
    op.execute(
        """
        UPDATE opportunities
        SET last_activity_at = COALESCE(last_activity_at, updated_at, created_at, now())
        WHERE last_activity_at IS NULL
        """
    )
    op.execute(
        "ALTER TABLE opportunities ALTER COLUMN last_activity_at SET DEFAULT now()"
    )
    op.execute(
        "ALTER TABLE opportunities ALTER COLUMN last_activity_at SET NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_opportunities_last_activity_at "
        "ON opportunities (last_activity_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_opportunities_quote_followup_due_date "
        "ON opportunities (quote_followup_due_date)"
    )


def downgrade() -> None:
    """Do not remove fields that may have existed before this repair migration."""
    pass
