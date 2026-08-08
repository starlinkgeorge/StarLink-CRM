"""Enhance follow-up records with opportunity links and attachments.

Revision ID: 0013_v5_followup_management
Revises: 0012_expand_alembic_version
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0013_v5_followup_management"
down_revision: str | None = "0012_expand_alembic_version"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "followups",
        sa.Column(
            "opportunity_id",
            sa.BigInteger(),
            sa.ForeignKey("opportunities.id", ondelete="SET NULL"),
        ),
    )
    op.create_index("ix_followups_opportunity_id", "followups", ["opportunity_id"])

    op.add_column("followups", sa.Column("followup_date", sa.Date(), nullable=True))
    op.execute("UPDATE followups SET followup_date = DATE(created_at) WHERE followup_date IS NULL")
    op.alter_column(
        "followups",
        "followup_date",
        existing_type=sa.Date(),
        nullable=False,
        server_default=sa.text("CURRENT_DATE"),
    )

    op.add_column(
        "followups", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute("UPDATE followups SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column(
        "followups",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    op.create_table(
        "followup_attachments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "followup_id",
            sa.BigInteger(),
            sa.ForeignKey("followups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100)),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("stored_name", name="uq_followup_attachments_stored_name"),
    )
    op.create_index(
        "ix_followup_attachments_followup_id", "followup_attachments", ["followup_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_followup_attachments_followup_id", table_name="followup_attachments")
    op.drop_table("followup_attachments")
    op.drop_column("followups", "updated_at")
    op.drop_column("followups", "followup_date")
    op.drop_index("ix_followups_opportunity_id", table_name="followups")
    op.drop_column("followups", "opportunity_id")
