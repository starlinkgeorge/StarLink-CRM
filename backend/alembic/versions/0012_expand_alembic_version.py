"""Expand Alembic's version identifier column.

Revision ID: 0012_expand_alembic_version
Revises: 0011_v4_customer_classification_scoring
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0012_expand_alembic_version"
down_revision: str | None = "0011_v4_customer_classification_scoring"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=32),
        type_=sa.String(length=100),
        existing_nullable=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    too_long = bind.execute(
        sa.text(
            "SELECT 1 FROM alembic_version "
            "WHERE length(version_num) > 32 LIMIT 1"
        )
    ).first()
    if too_long:
        raise RuntimeError("Cannot shrink alembic_version.version_num while a revision exceeds 32 characters.")
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=100),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
