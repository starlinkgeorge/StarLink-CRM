"""Secure inquiry ownership and prevent customer-history cascade deletes.

Revision ID: 0022_secure_inquiry_ownership_and_customer_deletes
Revises: 0021_remove_legacy_lead_module
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "0022_secure_inquiry_ownership_and_customer_deletes"
down_revision = "0021_remove_legacy_lead_module"
branch_labels = None
depends_on = None


CUSTOMER_HISTORY_TABLES = (
    "contacts",
    "followups",
    "opportunities",
    "customer_status_history",
    "customer_score_history",
)


def _customer_foreign_keys(table_name: str) -> list[dict]:
    return [
        foreign_key
        for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys(table_name)
        if foreign_key.get("referred_table") == "customers"
        and foreign_key.get("constrained_columns") == ["customer_id"]
    ]


def _replace_customer_fk(table_name: str, ondelete: str) -> None:
    foreign_keys = _customer_foreign_keys(table_name)
    if not foreign_keys:
        raise RuntimeError(f"Expected {table_name}.customer_id foreign key was not found.")

    for foreign_key in foreign_keys:
        existing_action = (foreign_key.get("options", {}).get("ondelete") or "").upper()
        if existing_action == ondelete:
            continue
        name = foreign_key.get("name")
        if not name:
            raise RuntimeError(
                f"Cannot safely replace unnamed {table_name}.customer_id foreign key."
            )
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(name, type_="foreignkey")
            batch_op.create_foreign_key(
                f"fk_{table_name}_customer_id_customers_{ondelete.lower()}",
                "customers",
                ["customer_id"],
                ["id"],
                ondelete=ondelete,
            )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "inquiries" in inspector.get_table_names():
        inquiry_columns = {column["name"] for column in inspector.get_columns("inquiries")}
        if "owner_id" not in inquiry_columns:
            with op.batch_alter_table("inquiries") as batch_op:
                # ``users.id`` is a BigInteger in the established schema. Keep
                # the new FK column identical rather than introducing an
                # avoidable type mismatch into the production migration.
                batch_op.add_column(sa.Column("owner_id", sa.BigInteger(), nullable=True))
                batch_op.create_foreign_key(
                    "fk_inquiries_owner_id_users",
                    "users",
                    ["owner_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
                batch_op.create_index("ix_inquiries_owner_id", ["owner_id"])

        # Only derive legacy ownership when an existing, directly related
        # record already establishes it.  Remaining unassigned inquiries stay
        # Admin-only; assigning them to a Sales account by guesswork would be
        # an ownership/data-exposure bug.
        op.execute(
            sa.text(
                """
                UPDATE inquiries
                SET owner_id = COALESCE(
                    (
                        SELECT opportunities.owner_id
                        FROM opportunities
                        WHERE opportunities.id = inquiries.converted_opportunity_id
                    ),
                    (
                        SELECT customers.owner_id
                        FROM customers
                        WHERE customers.id = inquiries.customer_id
                    )
                )
                WHERE owner_id IS NULL
                  AND COALESCE(
                    (
                        SELECT opportunities.owner_id
                        FROM opportunities
                        WHERE opportunities.id = inquiries.converted_opportunity_id
                    ),
                    (
                        SELECT customers.owner_id
                        FROM customers
                        WHERE customers.id = inquiries.customer_id
                    )
                  ) IS NOT NULL
                """
            )
        )

    for table_name in CUSTOMER_HISTORY_TABLES:
        if table_name in inspector.get_table_names():
            _replace_customer_fk(table_name, "RESTRICT")


def downgrade() -> None:
    # This security migration must not silently restore cascade deletes for
    # customer history.  A destructive rollback needs an explicit, audited
    # recovery plan for the live schema, so fail closed rather than recreating
    # the previous dangerous constraints automatically.
    raise RuntimeError(
        "Downgrade of 0022 is intentionally blocked: it would reintroduce "
        "customer-history cascade deletes. Use an explicit audited recovery "
        "migration instead."
    )
