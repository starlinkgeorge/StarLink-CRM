"""Add customer categories, tag metadata, and score history.

Revision ID: 0011_v4_customer_classification_scoring
Revises: 0010_add_alibaba_followup_type
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0011_v4_customer_classification_scoring"
down_revision: str | None = "0010_add_alibaba_followup_type"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_categories",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=255)),
        sa.Column("color", sa.String(length=20), nullable=False, server_default="#2563eb"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("name", name="uq_customer_categories_name"),
    )
    op.create_index("ix_customer_categories_is_active", "customer_categories", ["is_active"])
    op.create_index("ix_customer_categories_sort_order", "customer_categories", ["sort_order"])
    op.execute(
        "INSERT INTO customer_categories (name, sort_order) VALUES "
        "('Kindergarten', 10), ('School', 20), ('Distributor', 30), "
        "('Wholesaler', 40), ('Retailer', 50), ('Project Contractor', 60) "
        "ON CONFLICT (name) DO NOTHING"
    )

    op.add_column("tags", sa.Column("description", sa.String(length=255)))
    op.add_column("tags", sa.Column("color", sa.String(length=20), nullable=False, server_default="#2563eb"))
    op.add_column("tags", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index("ix_tags_is_active", "tags", ["is_active"])

    op.add_column(
        "customers",
        sa.Column(
            "category_id",
            sa.BigInteger(),
            sa.ForeignKey("customer_categories.id", ondelete="SET NULL"),
        ),
    )
    op.add_column("customers", sa.Column("customer_score", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("customers", sa.Column("score_updated_at", sa.DateTime(timezone=True)))
    op.create_index("ix_customers_category_id", "customers", ["category_id"])
    op.create_check_constraint(
        "ck_customers_customer_score_range",
        "customers",
        "customer_score >= 0 AND customer_score <= 100",
    )

    # Preserve existing A/B/C grades with a deterministic starting score.
    op.execute(
        "UPDATE customers SET customer_score = CASE level::text "
        "WHEN 'A' THEN 80 WHEN 'B' THEN 60 ELSE 30 END"
    )

    op.create_table(
        "customer_score_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "customer_id",
            sa.BigInteger(),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("old_score", sa.Integer()),
        sa.Column("new_score", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column(
            "changed_by_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_customer_score_history_customer_id", "customer_score_history", ["customer_id"])
    op.create_index("ix_customer_score_history_changed_by_id", "customer_score_history", ["changed_by_id"])


def downgrade() -> None:
    op.drop_index("ix_customer_score_history_changed_by_id", table_name="customer_score_history")
    op.drop_index("ix_customer_score_history_customer_id", table_name="customer_score_history")
    op.drop_table("customer_score_history")
    op.drop_constraint("ck_customers_customer_score_range", "customers", type_="check")
    op.drop_index("ix_customers_category_id", table_name="customers")
    op.drop_column("customers", "score_updated_at")
    op.drop_column("customers", "customer_score")
    op.drop_column("customers", "category_id")
    op.drop_index("ix_tags_is_active", table_name="tags")
    op.drop_column("tags", "is_active")
    op.drop_column("tags", "color")
    op.drop_column("tags", "description")
    op.drop_index("ix_customer_categories_sort_order", table_name="customer_categories")
    op.drop_index("ix_customer_categories_is_active", table_name="customer_categories")
    op.drop_table("customer_categories")
