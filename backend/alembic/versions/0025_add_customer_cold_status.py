"""Store a customer cold-status snapshot without altering customer history.

Revision ID: 0025_add_customer_cold_status
Revises: 0024_order_profit_pending_accounting
"""

from alembic import op
import sqlalchemy as sa


revision = "0025_add_customer_cold_status"
down_revision = "0024_order_profit_pending_accounting"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column(
            "is_cold_customer",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index("ix_customers_is_cold_customer", "customers", ["is_cold_customer"])
    # Intentionally do not backfill or mutate historical customer rows.  Read
    # paths calculate the effective status safely from date + manual stage.


def downgrade() -> None:
    op.drop_index("ix_customers_is_cold_customer", table_name="customers")
    op.drop_column("customers", "is_cold_customer")
