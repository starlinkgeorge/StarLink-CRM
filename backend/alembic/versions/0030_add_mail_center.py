"""Add CRM mail-center message and attachment storage.

Revision ID: 0030_add_mail_center
Revises: 0029_add_sales_targets_and_other_sales
"""

from alembic import op
import sqlalchemy as sa


revision = "0030_add_mail_center"
down_revision = "0029_add_sales_targets_and_other_sales"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("in_reply_to_id", sa.Integer(), nullable=True),
        sa.Column("folder", sa.String(length=20), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("sync_key", sa.String(length=512), nullable=False),
        sa.Column("message_id", sa.String(length=512), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("from_email", sa.String(length=320), nullable=False),
        sa.Column("to_emails", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("cc_emails", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("body_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("has_attachments", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["in_reply_to_id"], ["email_messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sync_key", name="uq_email_messages_sync_key"),
    )
    for column in ("customer_id", "created_by_id", "in_reply_to_id", "folder", "direction", "message_id", "from_email", "sent_at"):
        op.create_index(f"ix_email_messages_{column}", "email_messages", [column])
    op.create_table(
        "email_attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email_message_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["email_message_id"], ["email_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_attachments_email_message_id", "email_attachments", ["email_message_id"])


def downgrade() -> None:
    op.drop_index("ix_email_attachments_email_message_id", table_name="email_attachments")
    op.drop_table("email_attachments")
    for column in ("sent_at", "from_email", "message_id", "direction", "folder", "in_reply_to_id", "created_by_id", "customer_id"):
        op.drop_index(f"ix_email_messages_{column}", table_name="email_messages")
    op.drop_table("email_messages")
