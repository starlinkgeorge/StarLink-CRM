from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("priority IN ('high', 'medium', 'low')", name="ck_tasks_priority"),
        CheckConstraint("status IN ('pending', 'completed')", name="ck_tasks_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, server_default="medium")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending", index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class DailyWorkNote(TimestampMixin, Base):
    __tablename__ = "daily_work_notes"
    __table_args__ = (UniqueConstraint("user_id", "work_date", name="uq_daily_work_notes_user_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class WorkbenchDailyMetric(TimestampMixin, Base):
    """A keyed daily metric so channels and work items can grow without schema changes."""

    __tablename__ = "workbench_daily_metrics"
    __table_args__ = (
        UniqueConstraint("user_id", "work_date", "metric_group", "metric_key", name="uq_workbench_daily_metrics_item"),
        CheckConstraint("completed_value >= 0", name="ck_workbench_daily_metrics_completed_nonnegative"),
        CheckConstraint("target_value >= 0", name="ck_workbench_daily_metrics_target_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    metric_group: Mapped[str] = mapped_column(String(40), nullable=False)
    metric_key: Mapped[str] = mapped_column(String(80), nullable=False)
    completed_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    target_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
