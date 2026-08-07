"""Expand opportunities with commercial fields and stage history.

Revision ID: 0007_expand_opportunities
Revises: 0006_add_leads_opportunities
Create Date: 2026-08-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0007_expand_opportunities"
down_revision: str | None = "0006_add_leads_opportunities"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

opportunity_stage = postgresql.ENUM(
    "Lead",
    "Qualified",
    "Proposal",
    "Negotiation",
    "Won",
    "Lost",
    name="opportunity_stage",
    create_type=False,
)
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
    opportunity_stage.create(op.get_bind(), checkfirst=True)
    op.execute("ALTER TABLE opportunities ALTER COLUMN stage DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE opportunities
        ALTER COLUMN stage TYPE opportunity_stage
        USING (
            CASE stage::text
                WHEN 'Contacted' THEN 'Qualified'
                WHEN 'Quotation' THEN 'Proposal'
                ELSE stage::text
            END
        )::opportunity_stage
        """
    )
    op.alter_column(
        "opportunities",
        "stage",
        existing_type=opportunity_stage,
        nullable=False,
        server_default="Lead",
    )
    op.add_column("opportunities", sa.Column("amount", sa.Numeric(14, 2)))
    op.add_column(
        "opportunities",
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
    )
    op.add_column("opportunities", sa.Column("expected_close_date", sa.Date()))
    op.add_column("opportunities", sa.Column("inquiry_content", sa.Text()))

    op.create_table(
        "opportunity_stage_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "opportunity_id",
            sa.BigInteger(),
            sa.ForeignKey("opportunities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("old_stage", opportunity_stage),
        sa.Column("new_stage", opportunity_stage, nullable=False),
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
        "ix_opportunity_stage_history_opportunity_created",
        "opportunity_stage_history",
        ["opportunity_id", "created_at"],
    )
    op.create_index(
        "ix_opportunity_stage_history_changed_by_id",
        "opportunity_stage_history",
        ["changed_by_id"],
    )
    op.execute(
        """
        INSERT INTO opportunity_stage_history
            (opportunity_id, old_stage, new_stage, changed_by_id, created_at)
        SELECT id, NULL, stage, owner_id, created_at
        FROM opportunities
        """
    )


def downgrade() -> None:
    op.drop_table("opportunity_stage_history")
    op.drop_column("opportunities", "inquiry_content")
    op.drop_column("opportunities", "expected_close_date")
    op.drop_column("opportunities", "currency")
    op.drop_column("opportunities", "amount")
    op.execute("ALTER TABLE opportunities ALTER COLUMN stage DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE opportunities
        ALTER COLUMN stage TYPE customer_status
        USING (
            CASE stage::text
                WHEN 'Qualified' THEN 'Contacted'
                WHEN 'Proposal' THEN 'Quotation'
                ELSE stage::text
            END
        )::customer_status
        """
    )
    op.alter_column(
        "opportunities",
        "stage",
        existing_type=customer_status,
        nullable=False,
        server_default="Lead",
    )
    opportunity_stage.drop(op.get_bind(), checkfirst=True)
