"""Add compatible folders, drafts, HTML, flags, and threads to mail center.

Revision ID: 0032_mail_center_productivity
Revises: 0031_add_email_open_tracking
"""

from alembic import op
import sqlalchemy as sa


revision = "0032_mail_center_productivity"
down_revision = "0031_add_email_open_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mail_folders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("bound_addresses", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("name", name="uq_mail_folders_name"),
    )
    op.create_index("ix_mail_folders_customer_id", "mail_folders", ["customer_id"])
    op.create_index("ix_mail_folders_created_by_id", "mail_folders", ["created_by_id"])
    op.add_column("email_messages", sa.Column("mail_folder_id", sa.Integer(), nullable=True))
    op.add_column("email_messages", sa.Column("html_body", sa.Text(), nullable=False, server_default=""))
    op.add_column("email_messages", sa.Column("bcc_emails", sa.Text(), nullable=False, server_default="[]"))
    op.add_column("email_messages", sa.Column("thread_key", sa.String(length=512), nullable=True))
    op.add_column("email_messages", sa.Column("is_starred", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("email_messages", sa.Column("is_draft", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("email_messages", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.create_foreign_key("fk_email_messages_mail_folder_id", "email_messages", "mail_folders", ["mail_folder_id"], ["id"], ondelete="SET NULL")
    for name in ("mail_folder_id", "thread_key", "is_starred", "is_draft", "is_deleted"):
        op.create_index(f"ix_email_messages_{name}", "email_messages", [name])


def downgrade() -> None:
    for name in ("is_deleted", "is_draft", "is_starred", "thread_key", "mail_folder_id"):
        op.drop_index(f"ix_email_messages_{name}", table_name="email_messages")
    op.drop_constraint("fk_email_messages_mail_folder_id", "email_messages", type_="foreignkey")
    for name in ("is_deleted", "is_draft", "is_starred", "thread_key", "bcc_emails", "html_body", "mail_folder_id"):
        op.drop_column("email_messages", name)
    op.drop_index("ix_mail_folders_customer_id", table_name="mail_folders")
    op.drop_index("ix_mail_folders_created_by_id", table_name="mail_folders")
    op.drop_table("mail_folders")
