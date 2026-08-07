"""Add customer sales-stage history for the activity timeline.

Revision ID: 0004_customer_status_history
Revises: 0003_v3_customer_foundation
Create Date: 2026-08-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0004_customer_status_history"
down_revision: str | None = "0003_v3_customer_foundation"
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
        "customer_status_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "customer_id",
            sa.BigInteger(),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("old_status", customer_status, nullable=True),
        sa.Column("new_status", customer_status, nullable=False),
        sa.Column(
            "changed_by_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_customer_status_history_customer_created",
        "customer_status_history",
        ["customer_id", "created_at"],
    )
    op.create_index(
        "ix_customer_status_history_changed_by_id",
        "customer_status_history",
        ["changed_by_id"],
    )


def downgrade() -> None:
    op.drop_table("customer_status_history")
