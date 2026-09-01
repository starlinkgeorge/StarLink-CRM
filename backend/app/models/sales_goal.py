from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class AnnualSalesTarget(TimestampMixin, Base):
    __tablename__ = "annual_sales_targets"
    __table_args__ = (
        UniqueConstraint("user_id", "target_year", name="uq_annual_sales_targets_user_year"),
        CheckConstraint("target_amount >= 0", name="ck_annual_sales_targets_amount_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    target_year: Mapped[int] = mapped_column(nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)


class OtherSalesAmount(TimestampMixin, Base):
    __tablename__ = "other_sales_amounts"
    __table_args__ = (CheckConstraint("amount >= 0", name="ck_other_sales_amounts_amount_nonnegative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
