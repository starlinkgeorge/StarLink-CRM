"""Add order management and order-level profit fields.

Revision ID: 0023_add_order_management
Revises: 0022_secure_inquiry_ownership_and_customer_deletes
"""
from alembic import op
import sqlalchemy as sa

revision = "0023_add_order_management"
down_revision = "0022_secure_inquiry_ownership_and_customer_deletes"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_no", sa.String(80), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("opportunity_id", sa.Integer(), sa.ForeignKey("opportunities.id", ondelete="SET NULL")),
        sa.Column("quotation_id", sa.Integer(), sa.ForeignKey("quotations.id", ondelete="SET NULL"), unique=True),
        sa.Column("order_date", sa.Date(), nullable=False), sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("order_amount", sa.Numeric(18,2), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("payment_status", sa.Enum("Unpaid", "Deposit Received", "Paid in Full", name="order_payment_status"), nullable=False, server_default="Unpaid"),
        sa.Column("production_status", sa.Enum("Not Started", "In Production", "Completed", name="order_production_status"), nullable=False, server_default="Not Started"),
        sa.Column("shipping_status", sa.Enum("Pending Shipment", "Shipped", "Delivered", name="order_shipping_status"), nullable=False, server_default="Pending Shipment"),
        sa.Column("expected_delivery_date", sa.Date()), sa.Column("shipped_at", sa.Date()), sa.Column("notes", sa.Text()),
        sa.Column("rmb_received_amount", sa.Numeric(18,2), nullable=False, server_default="0"), sa.Column("purchase_cost", sa.Numeric(18,2), nullable=False, server_default="0"), sa.Column("freight_cost", sa.Numeric(18,2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    for name,column in (("ix_orders_order_no","order_no"),("ix_orders_customer_id","customer_id"),("ix_orders_opportunity_id","opportunity_id"),("ix_orders_quotation_id","quotation_id"),("ix_orders_owner_id","owner_id"),("ix_orders_created_by_id","created_by_id"),("ix_orders_order_date","order_date")):
        op.create_index(name,"orders",[column],unique=name == "ix_orders_order_no")

def downgrade() -> None:
    op.drop_table("orders")
    op.execute("DROP TYPE IF EXISTS order_shipping_status")
    op.execute("DROP TYPE IF EXISTS order_production_status")
    op.execute("DROP TYPE IF EXISTS order_payment_status")
