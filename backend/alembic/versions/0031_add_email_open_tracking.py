"""Add mail-center V2 state, read flags, and self-hosted open tracking.

Revision ID: 0031_add_email_open_tracking
Revises: 0030_add_mail_center
"""

from alembic import op
import sqlalchemy as sa


revision = "0031_add_email_open_tracking"
down_revision = "0030_add_mail_center"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("email_messages", sa.Column("forwarded_from_id", sa.Integer(), nullable=True))
    op.add_column("email_messages", sa.Column("from_name", sa.String(length=500), nullable=True))
    op.add_column("email_messages", sa.Column("to_display", sa.Text(), nullable=False, server_default="[]"))
    op.add_column("email_messages", sa.Column("cc_display", sa.Text(), nullable=False, server_default="[]"))
    op.add_column("email_messages", sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.create_foreign_key("fk_email_messages_forwarded_from_id", "email_messages", "email_messages", ["forwarded_from_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_email_messages_forwarded_from_id", "email_messages", ["forwarded_from_id"])
    op.create_index("ix_email_messages_is_read", "email_messages", ["is_read"])
    op.add_column(
        "email_messages",
        sa.Column("tracking_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("email_messages", sa.Column("tracking_token", sa.String(length=128), nullable=True))
    op.add_column("email_messages", sa.Column("first_opened_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("email_messages", sa.Column("last_opened_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "email_messages", sa.Column("open_count", sa.Integer(), nullable=False, server_default=sa.text("0"))
    )
    op.create_index("ix_email_messages_tracking_token", "email_messages", ["tracking_token"], unique=True)
    op.create_table(
        "email_open_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email_message_id", sa.Integer(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["email_message_id"], ["email_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_open_events_email_message_id", "email_open_events", ["email_message_id"])
    op.create_table(
        "mailbox_sync_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mailbox", sa.String(length=512), nullable=False),
        sa.Column("uid_validity", sa.String(length=128), nullable=True),
        sa.Column("last_synced_uid", sa.BigInteger(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mailbox", name="uq_mailbox_sync_states_mailbox"),
    )


def downgrade() -> None:
    op.drop_table("mailbox_sync_states")
    op.drop_index("ix_email_open_events_email_message_id", table_name="email_open_events")
    op.drop_table("email_open_events")
    op.drop_index("ix_email_messages_tracking_token", table_name="email_messages")
    op.drop_index("ix_email_messages_is_read", table_name="email_messages")
    op.drop_index("ix_email_messages_forwarded_from_id", table_name="email_messages")
    op.drop_constraint("fk_email_messages_forwarded_from_id", "email_messages", type_="foreignkey")
    for column in ("open_count", "last_opened_at", "first_opened_at", "tracking_token", "tracking_enabled", "is_read", "cc_display", "to_display", "from_name", "forwarded_from_id"):
        op.drop_column("email_messages", column)
