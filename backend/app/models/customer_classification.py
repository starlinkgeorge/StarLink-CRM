from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import CreatedAtMixin, TimestampMixin


class CustomerCategory(TimestampMixin, Base):
    """Configurable business category used to segment customers."""

    __tablename__ = "customer_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    color: Mapped[str] = mapped_column(String(20), nullable=False, server_default="#2563eb")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")

    customers: Mapped[list["Customer"]] = relationship(back_populates="category")


class CustomerScoreHistory(CreatedAtMixin, Base):
    """Audit trail for customer score changes."""

    __tablename__ = "customer_score_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    old_score: Mapped[Optional[int]] = mapped_column(Integer)
    new_score: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    changed_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    customer: Mapped["Customer"] = relationship(back_populates="score_history")
    changed_by: Mapped[Optional["User"]] = relationship()
