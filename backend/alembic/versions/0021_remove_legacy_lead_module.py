"""Remove the retired Lead inquiry pool and its opportunity link.

Revision ID: 0021_remove_legacy_lead_module
Revises: 0020_normalize_customer_followup_stages
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0021_remove_legacy_lead_module"
down_revision = "0020_normalize_customer_followup_stages"
branch_labels = None
depends_on = None


def _drop_source_lead_link() -> None:
    """Remove the only foreign-key dependency on the retired leads table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "opportunities" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("opportunities")}
    if "source_lead_id" not in columns:
        return

    foreign_keys = [
        foreign_key["name"]
        for foreign_key in inspector.get_foreign_keys("opportunities")
        if foreign_key["constrained_columns"] == ["source_lead_id"] and foreign_key["name"]
    ]
    unique_constraints = [
        constraint["name"]
        for constraint in inspector.get_unique_constraints("opportunities")
        if constraint["column_names"] == ["source_lead_id"] and constraint["name"]
    ]

    with op.batch_alter_table("opportunities") as batch_op:
        for name in foreign_keys:
            batch_op.drop_constraint(name, type_="foreignkey")
        for name in unique_constraints:
            batch_op.drop_constraint(name, type_="unique")
        batch_op.drop_column("source_lead_id")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "leads" in inspector.get_table_names():
        lead_references = []
        for table_name in inspector.get_table_names():
            for foreign_key in inspector.get_foreign_keys(table_name):
                if foreign_key.get("referred_table") == "leads":
                    lead_references.append(
                        (table_name, tuple(foreign_key.get("constrained_columns", ())))
                    )

        expected_reference = ("opportunities", ("source_lead_id",))
        unexpected_references = [
            reference for reference in lead_references if reference != expected_reference
        ]
        if unexpected_references:
            raise RuntimeError(
                "Refusing to drop the retired leads table because it has unexpected "
                f"foreign-key dependencies: {unexpected_references}"
            )

        lead_count = bind.execute(sa.text("SELECT count(*) FROM leads")).scalar_one()
        op.get_context().config.print_stdout(
            f"Removing retired leads table with {lead_count} record(s)."
        )

    _drop_source_lead_link()

    if "leads" in inspector.get_table_names():
        if bind.dialect.name == "postgresql":
            op.execute("DROP TRIGGER IF EXISTS leads_set_updated_at ON leads")
        op.drop_table("leads")

    if bind.dialect.name == "postgresql":
        postgresql.ENUM(name="lead_status").drop(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    lead_status = postgresql.ENUM(
        "New", "Contacted", "Qualified", "Converted", "Lost", name="lead_status"
    )
    if bind.dialect.name == "postgresql":
        lead_status.create(bind, checkfirst=True)

    op.create_table(
        "leads",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("public_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("contact_name", sa.String(length=120), nullable=False),
        sa.Column("country", sa.String(length=100)),
        sa.Column("email", sa.String(length=320)),
        sa.Column("phone", sa.String(length=50)),
        sa.Column("whatsapp", sa.String(length=50)),
        sa.Column("source", sa.String(length=80)),
        sa.Column("inquiry_content", sa.Text()),
        sa.Column("interested_product", sa.String(length=500)),
        sa.Column("status", lead_status, nullable=False, server_default="New"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("public_id", name="uq_leads_public_id"),
    )
    for column_name in ("company_name", "email", "source", "status", "created_at"):
        op.create_index(f"ix_leads_{column_name}", "leads", [column_name])

    with op.batch_alter_table("opportunities") as batch_op:
        batch_op.add_column(sa.Column("source_lead_id", sa.BigInteger()))
        batch_op.create_foreign_key(
            "fk_opportunities_source_lead_id_leads",
            "leads",
            ["source_lead_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_unique_constraint("uq_opportunities_source_lead_id", ["source_lead_id"])

    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE TRIGGER leads_set_updated_at "
            "BEFORE UPDATE ON leads FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
        )
