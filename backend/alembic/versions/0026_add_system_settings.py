"""Add persistent CRM settings center storage.

Revision ID: 0026_add_system_settings
Revises: 0025_add_customer_cold_status
"""

from alembic import op
import sqlalchemy as sa


revision = "0026_add_system_settings"
down_revision = "0025_add_customer_cold_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
