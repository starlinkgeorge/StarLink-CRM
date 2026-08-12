"""Normalize safely mappable customer follow-up stages.

Revision ID: 0020_normalize_customer_followup_stages
Revises: 0019_customer_archive_fields
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa


revision = "0020_normalize_customer_followup_stages"
down_revision = "0019_customer_archive_fields"
branch_labels = None
depends_on = None


STAGE_RENAMES = {
    "新开发未回复": "新客户未回复",
    "新开发已回复": "沟通中",
    "已采购样品": "已成交样品",
}


def upgrade() -> None:
    bind = op.get_bind()
    # Do not guess a replacement for legacy manual ``冷客户`` rows. They stay
    # intact in the archive column while the app now calculates the automatic
    # cold-customer judgement dynamically from latest_followup_date.
    cold_count = bind.execute(
        sa.text("SELECT count(*) FROM customers WHERE followup_stage = :stage"),
        {"stage": "冷客户"},
    ).scalar_one()
    op.get_context().config.print_stdout(
        f"Preserved {cold_count} historical followup_stage=冷客户 row(s)."
    )
    for previous, replacement in STAGE_RENAMES.items():
        bind.execute(
            sa.text(
                "UPDATE customers SET followup_stage = :replacement "
                "WHERE followup_stage = :previous"
            ),
            {"previous": previous, "replacement": replacement},
        )


def downgrade() -> None:
    # This migration has no schema change.  Reversing the values here would
    # incorrectly rewrite records that were genuinely created with the new
    # stages after the upgrade, so the data normalization is intentionally
    # non-destructive when migrating the Alembic version marker backwards.
    pass
