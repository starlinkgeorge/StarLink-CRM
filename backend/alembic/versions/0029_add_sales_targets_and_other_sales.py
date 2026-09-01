"""Add personal sales targets and manual sales amounts.

Revision ID: 0029_add_sales_targets_and_other_sales
Revises: 0028_add_workbench_daily_metrics
"""

from alembic import op
import sqlalchemy as sa

revision = "0029_add_sales_targets_and_other_sales"
down_revision = "0028_add_workbench_daily_metrics"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("annual_sales_targets", sa.Column("id", sa.Integer(), nullable=False), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("target_year", sa.Integer(), nullable=False), sa.Column("currency", sa.String(length=3), nullable=False), sa.Column("target_amount", sa.Numeric(precision=18, scale=2), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.CheckConstraint("target_amount >= 0", name="ck_annual_sales_targets_amount_nonnegative"), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id", "target_year", name="uq_annual_sales_targets_user_year"))
    op.create_index("ix_annual_sales_targets_user_id", "annual_sales_targets", ["user_id"])
    op.create_index("ix_annual_sales_targets_target_year", "annual_sales_targets", ["target_year"])
    op.create_table("other_sales_amounts", sa.Column("id", sa.Integer(), nullable=False), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("sale_date", sa.Date(), nullable=False), sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False), sa.Column("currency", sa.String(length=3), nullable=False), sa.Column("note", sa.Text(), nullable=False, server_default=""), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.CheckConstraint("amount >= 0", name="ck_other_sales_amounts_amount_nonnegative"), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_other_sales_amounts_user_id", "other_sales_amounts", ["user_id"])
    op.create_index("ix_other_sales_amounts_sale_date", "other_sales_amounts", ["sale_date"])

def downgrade() -> None:
    op.drop_index("ix_other_sales_amounts_sale_date", table_name="other_sales_amounts")
    op.drop_index("ix_other_sales_amounts_user_id", table_name="other_sales_amounts")
    op.drop_table("other_sales_amounts")
    op.drop_index("ix_annual_sales_targets_target_year", table_name="annual_sales_targets")
    op.drop_index("ix_annual_sales_targets_user_id", table_name="annual_sales_targets")
    op.drop_table("annual_sales_targets")
