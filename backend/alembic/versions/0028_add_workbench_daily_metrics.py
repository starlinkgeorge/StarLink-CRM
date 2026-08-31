"""Add extensible per-day workbench metrics.

Revision ID: 0028_add_workbench_daily_metrics
Revises: 0027_add_daily_workbench_mvp
"""

from alembic import op
import sqlalchemy as sa


revision = "0028_add_workbench_daily_metrics"
down_revision = "0027_add_daily_workbench_mvp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workbench_daily_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("metric_group", sa.String(length=40), nullable=False),
        sa.Column("metric_key", sa.String(length=80), nullable=False),
        sa.Column("completed_value", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
        sa.Column("target_value", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("completed_value >= 0", name="ck_workbench_daily_metrics_completed_nonnegative"),
        sa.CheckConstraint("target_value >= 0", name="ck_workbench_daily_metrics_target_nonnegative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "work_date", "metric_group", "metric_key", name="uq_workbench_daily_metrics_item"),
    )
    op.create_index("ix_workbench_daily_metrics_user_id", "workbench_daily_metrics", ["user_id"])
    op.create_index("ix_workbench_daily_metrics_work_date", "workbench_daily_metrics", ["work_date"])


def downgrade() -> None:
    op.drop_index("ix_workbench_daily_metrics_work_date", table_name="workbench_daily_metrics")
    op.drop_index("ix_workbench_daily_metrics_user_id", table_name="workbench_daily_metrics")
    op.drop_table("workbench_daily_metrics")
