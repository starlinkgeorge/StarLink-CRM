from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.customer import CustomerStatus


class CustomerStatusHistory(Base):
    __tablename__ = "customer_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    old_status: Mapped[CustomerStatus | None] = mapped_column(
        Enum(
            CustomerStatus,
            name="customer_status",
            native_enum=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        )
    )
    new_status: Mapped[CustomerStatus] = mapped_column(
        Enum(
            CustomerStatus,
            name="customer_status",
            native_enum=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
    )
    changed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
