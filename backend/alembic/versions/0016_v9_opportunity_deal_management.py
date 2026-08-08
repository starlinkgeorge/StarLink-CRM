"""Add the V9 opportunity deal stage while retaining V3 and V7 stages.

Revision ID: 0016_v9_opportunity_deal_management
Revises: 0015_v8_alibaba_inquiry_management
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0016_v9_opportunity_deal_management"
down_revision: str | None = "0015_v8_alibaba_inquiry_management"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Serializes this migration if a deployment attempts two Alembic upgrades at once.
    op.execute("SELECT pg_advisory_xact_lock(916202608);")
    op.add_column("opportunities", sa.Column("deal_stage", sa.String(length=40), nullable=True))
    op.execute(
        """
        UPDATE opportunities
        SET deal_stage = CASE sales_stage
            WHEN 'New Lead' THEN 'New Inquiry'
            WHEN 'Contacted' THEN 'Contacted'
            WHEN 'Requirement Confirmed' THEN 'Contacted'
            WHEN 'Quotation Sent' THEN 'Quoted'
            WHEN 'Negotiation' THEN 'Negotiating'
            WHEN 'Won' THEN 'Won'
            WHEN 'Lost' THEN 'Lost'
            ELSE 'New Inquiry'
        END
        WHERE deal_stage IS NULL
        """
    )
    op.alter_column(
        "opportunities",
        "deal_stage",
        existing_type=sa.String(length=40),
        nullable=False,
        server_default=sa.text("'New Inquiry'"),
    )
    op.create_index("ix_opportunities_deal_stage", "opportunities", ["deal_stage"])
    op.create_check_constraint(
        "ck_opportunities_deal_stage",
        "opportunities",
        "deal_stage IN ('New Inquiry', 'Contacted', 'Quoted', 'Negotiating', 'Won', 'Lost')",
    )

    op.create_table(
        "opportunity_deal_stage_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "opportunity_id",
            sa.BigInteger(),
            sa.ForeignKey("opportunities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("old_deal_stage", sa.String(length=40)),
        sa.Column("new_deal_stage", sa.String(length=40), nullable=False),
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
        "ix_opportunity_deal_stage_history_opportunity_created",
        "opportunity_deal_stage_history",
        ["opportunity_id", "created_at"],
    )
    op.create_index(
        "ix_opportunity_deal_stage_history_changed_by_id",
        "opportunity_deal_stage_history",
        ["changed_by_id"],
    )
    op.execute(
        """
        INSERT INTO opportunity_deal_stage_history
            (opportunity_id, old_deal_stage, new_deal_stage, changed_by_id, created_at)
        SELECT id, NULL, deal_stage, owner_id, created_at
        FROM opportunities
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_opportunity_deal_stage_history_changed_by_id",
        table_name="opportunity_deal_stage_history",
    )
    op.drop_index(
        "ix_opportunity_deal_stage_history_opportunity_created",
        table_name="opportunity_deal_stage_history",
    )
    op.drop_table("opportunity_deal_stage_history")
    op.drop_constraint("ck_opportunities_deal_stage", "opportunities", type_="check")
    op.drop_index("ix_opportunities_deal_stage", table_name="opportunities")
    op.drop_column("opportunities", "deal_stage")
