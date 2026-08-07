from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import CreatedAtMixin, TimestampMixin


class ProductCategory(Base):
    __tablename__ = "product_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("product_categories.id", ondelete="SET NULL"), index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    parent: Mapped[Optional["ProductCategory"]] = relationship(
        back_populates="children", remote_side="ProductCategory.id"
    )
    children: Mapped[list["ProductCategory"]] = relationship(back_populates="parent")
    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("product_categories.id", ondelete="SET NULL"), index=True
    )
    material: Mapped[Optional[str]] = mapped_column(String(255))
    dimension_text: Mapped[Optional[str]] = mapped_column(String(255))
    length_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    width_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    height_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    weight_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    unit: Mapped[str] = mapped_column(String(30), nullable=False, default="piece")
    moq: Mapped[Optional[int]] = mapped_column(Integer)
    reference_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    category: Mapped[Optional[ProductCategory]] = relationship(back_populates="products")
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="(ProductImage.is_primary.desc(), ProductImage.sort_order, ProductImage.id)",
    )
    opportunity_items: Mapped[list["OpportunityProduct"]] = relationship(
        back_populates="product"
    )


class ProductImage(CreatedAtMixin, Base):
    __tablename__ = "product_images"
    __table_args__ = (
        Index(
            "uq_product_images_one_primary",
            "product_id",
            unique=True,
            postgresql_where=text("is_primary"),
            sqlite_where=text("is_primary = 1"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    product: Mapped[Product] = relationship(back_populates="images")


class OpportunityProduct(Base):
    __tablename__ = "opportunity_products"

    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), primary_key=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), primary_key=True, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=1)
    target_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))

    opportunity: Mapped["Opportunity"] = relationship(back_populates="product_items")
    product: Mapped[Product] = relationship(back_populates="opportunity_items")
