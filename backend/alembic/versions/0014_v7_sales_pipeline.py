"""Add the V7 sales pipeline fields and history without changing legacy stages.

Revision ID: 0014_v7_sales_pipeline
Revises: 0013_v5_followup_management
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0014_v7_sales_pipeline"
down_revision: str | None = "0013_v5_followup_management"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Keep opportunities.stage and opportunity_stage_history intact. Existing integrations
    # continue to use the old enum while V7 uses the more expressive sales_stage field.
    op.add_column(
        "opportunities", sa.Column("sales_stage", sa.String(length=40), nullable=True)
    )
    op.execute(
        """
        UPDATE opportunities
        SET sales_stage = CASE stage::text
            WHEN 'Lead' THEN 'New Lead'
            WHEN 'Qualified' THEN 'Requirement Confirmed'
            WHEN 'Proposal' THEN 'Quotation Sent'
            WHEN 'Negotiation' THEN 'Negotiation'
            WHEN 'Won' THEN 'Won'
            WHEN 'Lost' THEN 'Lost'
            ELSE 'New Lead'
        END
        WHERE sales_stage IS NULL
        """
    )
    op.alter_column(
        "opportunities",
        "sales_stage",
        existing_type=sa.String(length=40),
        nullable=False,
        server_default=sa.text("'New Lead'"),
    )
    op.create_index("ix_opportunities_sales_stage", "opportunities", ["sales_stage"])
    op.create_check_constraint(
        "ck_opportunities_sales_stage",
        "opportunities",
        "sales_stage IN ('New Lead', 'Contacted', 'Requirement Confirmed', "
        "'Quotation Sent', 'Negotiation', 'Won', 'Lost')",
    )

    op.add_column("opportunities", sa.Column("probability", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE opportunities
        SET probability = CASE sales_stage
            WHEN 'New Lead' THEN 10
            WHEN 'Contacted' THEN 20
            WHEN 'Requirement Confirmed' THEN 40
            WHEN 'Quotation Sent' THEN 60
            WHEN 'Negotiation' THEN 80
            WHEN 'Won' THEN 100
            WHEN 'Lost' THEN 0
            ELSE 10
        END
        WHERE probability IS NULL
        """
    )
    op.alter_column(
        "opportunities",
        "probability",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=sa.text("10"),
    )
    op.create_check_constraint(
        "ck_opportunities_probability_range",
        "opportunities",
        "probability >= 0 AND probability <= 100",
    )
    op.add_column("opportunities", sa.Column("next_action", sa.String(length=500)))

    op.create_table(
        "opportunity_sales_stage_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "opportunity_id",
            sa.BigInteger(),
            sa.ForeignKey("opportunities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("old_sales_stage", sa.String(length=40)),
        sa.Column("new_sales_stage", sa.String(length=40), nullable=False),
        sa.Column(
            "changed_by_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_opportunity_sales_stage_history_opportunity_created",
        "opportunity_sales_stage_history",
        ["opportunity_id", "created_at"],
    )
    op.create_index(
        "ix_opportunity_sales_stage_history_changed_by_id",
        "opportunity_sales_stage_history",
        ["changed_by_id"],
    )
    op.execute(
        """
        INSERT INTO opportunity_sales_stage_history
            (opportunity_id, old_sales_stage, new_sales_stage, changed_by_id, created_at)
        SELECT id, NULL, sales_stage, owner_id, created_at
        FROM opportunities
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_opportunity_sales_stage_history_changed_by_id",
        table_name="opportunity_sales_stage_history",
    )
    op.drop_index(
        "ix_opportunity_sales_stage_history_opportunity_created",
        table_name="opportunity_sales_stage_history",
    )
    op.drop_table("opportunity_sales_stage_history")
    op.drop_column("opportunities", "next_action")
    op.drop_constraint(
        "ck_opportunities_probability_range", "opportunities", type_="check"
    )
    op.drop_column("opportunities", "probability")
    op.drop_constraint("ck_opportunities_sales_stage", "opportunities", type_="check")
    op.drop_index("ix_opportunities_sales_stage", table_name="opportunities")
    op.drop_column("opportunities", "sales_stage")
