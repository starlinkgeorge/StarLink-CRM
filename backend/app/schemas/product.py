from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parent_id: int | None = Field(default=None, gt=0)
    sort_order: int = Field(default=0, ge=0)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()


class ProductCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    parent_id: int | None = Field(default=None, gt=0)
    sort_order: int | None = Field(default=None, ge=0)

    @field_validator("name", mode="before")
    @classmethod
    def clean_optional_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class ProductCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    parent_id: int | None
    sort_order: int


class ProductImageInput(BaseModel):
    image_url: str = Field(min_length=1, max_length=1000)
    is_primary: bool = False
    sort_order: int = Field(default=0, ge=0)

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.lower().startswith(("http://", "https://")):
            raise ValueError("Image URL must use http or https.")
        return cleaned


class ProductImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    image_url: str
    is_primary: bool
    sort_order: int
    created_at: datetime


class ProductFields(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    category_id: int | None = Field(default=None, gt=0)
    material: str | None = Field(default=None, max_length=255)
    dimension_text: str | None = Field(default=None, max_length=255)
    length_mm: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    width_mm: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    height_mm: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    weight_kg: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=3)
    unit: str = Field(default="piece", min_length=1, max_length=30)
    moq: int | None = Field(default=None, ge=1)
    reference_price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    currency_code: str = Field(default="USD", min_length=3, max_length=3)
    description: str | None = Field(default=None, max_length=20000)
    is_active: bool = True

    @field_validator("sku", mode="before")
    @classmethod
    def normalize_sku(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("currency_code", mode="before")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class ProductCreate(ProductFields):
    images: list[ProductImageInput] = Field(default_factory=list, max_length=20)


class ProductUpdate(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category_id: int | None = Field(default=None, gt=0)
    material: str | None = Field(default=None, max_length=255)
    dimension_text: str | None = Field(default=None, max_length=255)
    length_mm: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    width_mm: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    height_mm: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    weight_kg: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=3)
    unit: str | None = Field(default=None, min_length=1, max_length=30)
    moq: int | None = Field(default=None, ge=1)
    reference_price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    description: str | None = Field(default=None, max_length=20000)
    is_active: bool | None = None
    images: list[ProductImageInput] | None = Field(default=None, max_length=20)

    @field_validator("sku", mode="before")
    @classmethod
    def normalize_optional_sku(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value

    @field_validator("currency_code", mode="before")
    @classmethod
    def normalize_optional_currency(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    category_id: int | None
    category_name: str | None
    material: str | None
    dimension_text: str | None
    length_mm: Decimal | None
    width_mm: Decimal | None
    height_mm: Decimal | None
    weight_kg: Decimal | None
    unit: str
    moq: int | None
    reference_price: Decimal | None
    currency_code: str
    description: str | None
    is_active: bool
    images: list[ProductImageRead]
    created_at: datetime
    updated_at: datetime


class ProductPage(BaseModel):
    items: list[ProductRead]
    total: int
    limit: int
    offset: int


class OpportunityProductInput(BaseModel):
    product_id: int = Field(gt=0)
    quantity: Decimal = Field(default=1, gt=0, max_digits=12, decimal_places=2)
    target_price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)


class OpportunityProductReplace(BaseModel):
    items: list[OpportunityProductInput] = Field(default_factory=list, max_length=100)


class OpportunityProductRead(BaseModel):
    product_id: int
    sku: str
    name: str
    quantity: Decimal
    target_price: Decimal | None
    reference_price: Decimal | None
    currency_code: str
    image_url: str | None
