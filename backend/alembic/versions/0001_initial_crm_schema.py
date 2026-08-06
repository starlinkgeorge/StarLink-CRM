"""Create the initial CRM schema.

Revision ID: 0001_initial_crm_schema
Revises:
Create Date: 2026-08-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001_initial_crm_schema"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

user_role = postgresql.ENUM("Admin", "Sales", "Viewer", name="user_role", create_type=False)
customer_level = postgresql.ENUM("A", "B", "C", name="customer_level", create_type=False)
customer_status = postgresql.ENUM(
    "Lead", "Contacted", "Quotation", "Negotiation", "Won", "Lost",
    name="customer_status",
    create_type=False,
)
followup_type = postgresql.ENUM(
    "Email", "WhatsApp", "Phone", "Meeting", name="followup_type", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    customer_level.create(bind, checkfirst=True)
    customer_status.create(bind, checkfirst=True)
    followup_type.create(bind, checkfirst=True)
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="Sales"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_table(
        "customers",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("contact_name", sa.String(120)),
        sa.Column("country", sa.String(100)),
        sa.Column("email", sa.String(320)),
        sa.Column("phone", sa.String(50)),
        sa.Column("whatsapp", sa.String(50)),
        sa.Column("website", sa.String(255)),
        sa.Column("source", sa.String(80)),
        sa.Column("level", customer_level, nullable=False, server_default="C"),
        sa.Column("status", customer_status, nullable=False, server_default="Lead"),
        sa.Column("owner_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    for column in ("company_name", "country", "email", "owner_id", "source", "status"):
        op.create_index(f"ix_customers_{column}", "customers", [column])
    op.create_table(
        "tags",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("name", name="uq_tags_name"),
    )
    op.create_table(
        "contacts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("customer_id", sa.BigInteger(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("position", sa.String(120)),
        sa.Column("email", sa.String(320)),
        sa.Column("phone", sa.String(50)),
        sa.Column("whatsapp", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_contacts_customer_id", "contacts", ["customer_id"])
    op.create_table(
        "customer_tags",
        sa.Column("customer_id", sa.BigInteger(), sa.ForeignKey("customers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.BigInteger(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "followups",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("customer_id", sa.BigInteger(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("type", followup_type, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("next_followup_date", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_followups_customer_id", "followups", ["customer_id"])
    op.create_index("ix_followups_user_id", "followups", ["user_id"])
    op.execute("""
        CREATE FUNCTION set_updated_at() RETURNS trigger AS $$
        BEGIN NEW.updated_at = now(); RETURN NEW; END;
        $$ LANGUAGE plpgsql;
    """)
    for table_name in ("users", "customers"):
        op.execute(
            f"CREATE TRIGGER {table_name}_set_updated_at BEFORE UPDATE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
        )


def downgrade() -> None:
    for table_name in ("customers", "users"):
        op.execute(f"DROP TRIGGER IF EXISTS {table_name}_set_updated_at ON {table_name};")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")
    op.drop_table("followups")
    op.drop_table("customer_tags")
    op.drop_table("contacts")
    op.drop_table("tags")
    op.drop_table("customers")
    op.drop_table("users")
    followup_type.drop(op.get_bind(), checkfirst=True)
    customer_status.drop(op.get_bind(), checkfirst=True)
    customer_level.drop(op.get_bind(), checkfirst=True)
    user_role.drop(op.get_bind(), checkfirst=True)
