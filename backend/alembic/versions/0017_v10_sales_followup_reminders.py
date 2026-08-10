"""Add V10 customer and opportunity follow-up reminder summaries.

Revision ID: 0017_v10_sales_followup_reminders
Revises: 0016_v9_opportunity_deal_management
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0017_v10_sales_followup_reminders"
down_revision: str | None = "0016_v9_opportunity_deal_management"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Avoid two concurrent startup/manual upgrades racing on this additive DDL.
    op.execute("SELECT pg_advisory_xact_lock(916202610);")

    op.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS next_followup_date DATE")
    op.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS last_followup_at TIMESTAMP WITH TIME ZONE")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_customers_next_followup_date "
        "ON customers (next_followup_date)"
    )
    # The latest business follow-up is the customer reminder source of truth.
    op.execute(
        """
        UPDATE customers AS customer
        SET next_followup_date = latest.next_followup_date,
            last_followup_at = latest.activity_at
        FROM (
            SELECT DISTINCT ON (customer_id)
                customer_id,
                next_followup_date,
                COALESCE(updated_at, created_at) AS activity_at
            FROM followups
            ORDER BY customer_id, followup_date DESC, created_at DESC, id DESC
        ) AS latest
        WHERE customer.id = latest.customer_id
        """
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
        """
        UPDATE opportunities AS opportunity
        SET last_followup_at = latest.activity_at
        FROM (
            SELECT opportunity_id, MAX(COALESCE(updated_at, created_at)) AS activity_at
            FROM followups
            WHERE opportunity_id IS NOT NULL
            GROUP BY opportunity_id
        ) AS latest
        WHERE opportunity.id = latest.opportunity_id
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
    op.execute("DROP INDEX IF EXISTS ix_opportunities_quote_followup_due_date")
    op.execute("DROP INDEX IF EXISTS ix_opportunities_last_activity_at")
    op.execute("ALTER TABLE opportunities DROP COLUMN IF EXISTS quote_followup_due_date")
    op.execute("ALTER TABLE opportunities DROP COLUMN IF EXISTS quotation_sent_at")
    op.execute("ALTER TABLE opportunities DROP COLUMN IF EXISTS last_followup_at")
    op.execute("ALTER TABLE opportunities DROP COLUMN IF EXISTS last_activity_at")
    op.execute("DROP INDEX IF EXISTS ix_customers_next_followup_date")
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS last_followup_at")
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS next_followup_date")
