"""Allow orders to remain pending until all profit inputs are recorded.

Revision ID: 0024_order_profit_pending_accounting
Revises: 0023_add_order_management
"""

from alembic import op
import sqlalchemy as sa


revision = "0024_order_profit_pending_accounting"
down_revision = "0023_add_order_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing zero values are intentionally preserved.  Only future omitted
    # inputs become NULL and are reported as "Pending" by the application.
    for column_name in ("rmb_received_amount", "purchase_cost", "freight_cost"):
        op.alter_column(
            "orders",
            column_name,
            existing_type=sa.Numeric(18, 2),
            nullable=True,
            server_default=None,
        )


def downgrade() -> None:
    connection = op.get_bind()
    pending_count = connection.scalar(
        sa.text(
            "SELECT count(*) FROM orders "
            "WHERE rmb_received_amount IS NULL OR purchase_cost IS NULL OR freight_cost IS NULL"
        )
    )
    if pending_count:
        # Converting NULL pending-accounting values into zero would silently
        # change their business meaning.  Only allow rollback while it is safe.
        raise RuntimeError(
            "Cannot downgrade 0024 while orders with pending profit accounting exist."
        )
    for column_name in ("rmb_received_amount", "purchase_cost", "freight_cost"):
        op.alter_column(
            "orders",
            column_name,
            existing_type=sa.Numeric(18, 2),
            nullable=False,
            server_default="0",
        )
