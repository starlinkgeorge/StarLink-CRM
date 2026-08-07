from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.product import Product, ProductCategory, ProductImage
from app.models.user import User, UserRole
from app.schemas.product import (
    ProductCategoryCreate,
    ProductCategoryUpdate,
    ProductCreate,
    ProductRead,
    ProductUpdate,
)
from app.services.errors import ConflictError, ForbiddenError, NotFoundError


def _ensure_write_access(user: User) -> None:
    if user.role is UserRole.VIEWER:
        raise ForbiddenError("Viewer accounts have read-only access.")


def _validate_category(session: Session, category_id: int | None) -> None:
    if category_id is not None and session.get(ProductCategory, category_id) is None:
        raise NotFoundError("Product category not found.")


def _product_read(product: Product) -> ProductRead:
    return ProductRead.model_validate(
        {
            **product.__dict__,
            "category_name": product.category.name if product.category else None,
            "images": product.images,
        }
    )


def list_categories(session: Session) -> list[ProductCategory]:
    return list(
        session.scalars(
            select(ProductCategory).order_by(
                ProductCategory.sort_order, ProductCategory.name, ProductCategory.id
            )
        )
    )


def create_category(
    session: Session, payload: ProductCategoryCreate, user: User
) -> ProductCategory:
    _ensure_write_access(user)
    _validate_category(session, payload.parent_id)
    data = payload.model_dump()
    data["name"] = payload.name.strip()
    category = ProductCategory(**data)
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


def update_category(
    session: Session, category_id: int, payload: ProductCategoryUpdate, user: User
) -> ProductCategory:
    _ensure_write_access(user)
    category = session.get(ProductCategory, category_id)
    if category is None:
        raise NotFoundError("Product category not found.")
    changes = payload.model_dump(exclude_unset=True)
    parent_id = changes.get("parent_id")
    if parent_id == category_id:
        raise ConflictError("A category cannot be its own parent.")
    if "parent_id" in changes:
        _validate_category(session, parent_id)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    for field, value in changes.items():
        setattr(category, field, value)
    session.commit()
    session.refresh(category)
    return category


def list_products(
    session: Session,
    limit: int,
    offset: int,
    query: str | None = None,
    category_id: int | None = None,
    is_active: bool | None = None,
) -> tuple[list[ProductRead], int]:
    filters = []
    search_term = query.strip() if query else ""
    if search_term:
        term = f"%{search_term}%"
        filters.append(
            or_(Product.sku.ilike(term), Product.name.ilike(term), Product.material.ilike(term))
        )
    if category_id is not None:
        filters.append(Product.category_id == category_id)
    if is_active is not None:
        filters.append(Product.is_active.is_(is_active))
    statement = (
        select(Product)
        .where(*filters)
        .options(joinedload(Product.category), selectinload(Product.images))
        .order_by(Product.name, Product.id)
        .limit(limit)
        .offset(offset)
    )
    total = session.scalar(select(func.count()).select_from(Product).where(*filters)) or 0
    return [_product_read(product) for product in session.scalars(statement)], total


def get_product(session: Session, product_id: int) -> Product:
    product = session.scalar(
        select(Product)
        .where(Product.id == product_id)
        .options(joinedload(Product.category), selectinload(Product.images))
    )
    if product is None:
        raise NotFoundError("Product not found.")
    return product


def get_product_read(session: Session, product_id: int) -> ProductRead:
    return _product_read(get_product(session, product_id))


def _replace_images(product: Product, image_values: list[dict]) -> None:
    primary_count = sum(bool(image["is_primary"]) for image in image_values)
    if primary_count > 1:
        raise ConflictError("A product can only have one primary image.")
    if image_values and primary_count == 0:
        image_values[0]["is_primary"] = True
    product.images = [ProductImage(**image) for image in image_values]


def create_product(session: Session, payload: ProductCreate, user: User) -> ProductRead:
    _ensure_write_access(user)
    _validate_category(session, payload.category_id)
    data = payload.model_dump()
    images = data.pop("images")
    product = Product(**data)
    _replace_images(product, images)
    session.add(product)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ConflictError("A product with this SKU already exists.") from error
    return get_product_read(session, product.id)


def update_product(
    session: Session, product_id: int, payload: ProductUpdate, user: User
) -> ProductRead:
    _ensure_write_access(user)
    product = get_product(session, product_id)
    changes = payload.model_dump(exclude_unset=True)
    images = changes.pop("images", None)
    if "category_id" in changes:
        _validate_category(session, changes["category_id"])
    for field, value in changes.items():
        setattr(product, field, value)
    if images is not None:
        product.images.clear()
        session.flush()
        _replace_images(product, images)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ConflictError("A product with this SKU already exists.") from error
    return get_product_read(session, product.id)
