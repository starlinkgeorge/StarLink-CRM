"""Repair missing V3 customer compatibility columns.

Revision ID: 0005_repair_v3_customer_columns
Revises: 0004_customer_status_history
Create Date: 2026-08-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0005_repair_v3_customer_columns"
down_revision: str | None = "0004_customer_status_history"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_REPAIR_COMMENT = "Added by 0005_repair_v3_customer_columns"

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


def _customer_columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns("customers")}


def _mark_repair_column(column_name: str) -> None:
    op.execute(
        f"COMMENT ON COLUMN customers.{column_name} IS '{_REPAIR_COMMENT}'"
    )


def _was_added_by_repair(column_name: str) -> bool:
    comment = op.get_bind().scalar(
        sa.text(
            """
            SELECT col_description(table_record.oid, attribute.attnum)
            FROM pg_class AS table_record
            JOIN pg_namespace AS namespace
              ON namespace.oid = table_record.relnamespace
            JOIN pg_attribute AS attribute
              ON attribute.attrelid = table_record.oid
            WHERE namespace.nspname = current_schema()
              AND table_record.relname = 'customers'
              AND attribute.attname = :column_name
              AND attribute.attnum > 0
              AND NOT attribute.attisdropped
            """
        ),
        {"column_name": column_name},
    )
    return comment == _REPAIR_COMMENT


def upgrade() -> None:
    columns = _customer_columns()

    if "customer_type" not in columns:
        op.add_column(
            "customers",
            sa.Column("customer_type", sa.String(length=80), nullable=True),
        )
        _mark_repair_column("customer_type")

    if "interested_product" not in columns:
        op.add_column(
            "customers",
            sa.Column("interested_product", sa.String(length=500), nullable=True),
        )
        _mark_repair_column("interested_product")

    if "sales_stage" not in columns:
        op.add_column(
            "customers",
            sa.Column("sales_stage", customer_status, nullable=True),
        )
        _mark_repair_column("sales_stage")
        op.execute(
            "UPDATE customers SET sales_stage = status WHERE sales_stage IS NULL"
        )
        op.alter_column(
            "customers",
            "sales_stage",
            existing_type=customer_status,
            nullable=False,
            server_default="Lead",
        )


def downgrade() -> None:
    columns = _customer_columns()
    for column_name in ("sales_stage", "interested_product", "customer_type"):
        if column_name in columns and _was_added_by_repair(column_name):
            op.drop_column("customers", column_name)
