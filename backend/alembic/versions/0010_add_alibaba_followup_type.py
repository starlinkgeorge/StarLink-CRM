"""Add Alibaba as a follow-up channel.

Revision ID: 0010_add_alibaba_followup_type
Revises: 0009_add_quotations
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_add_alibaba_followup_type"
down_revision = "0009_add_quotations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL enum values are additive. IF NOT EXISTS keeps this migration
    # safe when a partially applied deployment already added the value.
    op.execute("ALTER TYPE followup_type ADD VALUE IF NOT EXISTS 'Alibaba'")


def downgrade() -> None:
    bind = op.get_bind()
    has_alibaba_rows = bind.execute(
        sa.text("SELECT 1 FROM followups WHERE type = 'Alibaba' LIMIT 1")
    ).first()
    if has_alibaba_rows:
        raise RuntimeError(
            "Cannot downgrade followup_type while follow-up records use Alibaba."
        )

    # PostgreSQL does not support DROP VALUE directly. Recreate the enum only
    # after confirming there are no rows that would become invalid.
    op.execute("ALTER TYPE followup_type RENAME TO followup_type_old")
    op.execute(
        "CREATE TYPE followup_type AS ENUM ('Email', 'WhatsApp', 'Phone', 'Meeting')"
    )
    op.execute(
        "ALTER TABLE followups ALTER COLUMN type TYPE followup_type "
        "USING type::text::followup_type"
    )
    op.execute("DROP TYPE followup_type_old")
