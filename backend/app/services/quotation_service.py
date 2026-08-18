from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, joinedload, selectinload

from app.config import get_settings
from app.models.customer import Customer
from app.models.opportunity import Opportunity
from app.models.product import Product
from app.models.quotation import (
    Quotation,
    QuotationItem,
    QuotationStatus,
    QuotationVersion,
)
from app.models.user import User, UserRole
from app.schemas.quotation import (
    QuotationCreate,
    QuotationDetail,
    QuotationItemInput,
    QuotationListItem,
    QuotationUpdate,
    QuotationVersionRead,
    QuotationVersionSummary,
)
from app.services import (
    access_service,
    opportunity_service,
    quotation_excel_service,
    quotation_pdf_service,
)
from app.services.errors import ConflictError, ForbiddenError, NotFoundError


MONEY = Decimal("0.01")
BUSINESS_TIME_ZONE = ZoneInfo("Asia/Shanghai")


def _daily_quotation_prefix(quotation_date: date) -> str:
    return f"SLQ-{quotation_date:%Y%m%d}-"


def _next_daily_sequence(quotation_numbers: Iterable[str], prefix: str) -> int:
    """Use the highest existing numeric suffix so gaps are never reused by count."""
    largest_sequence = 0
    for quotation_number in quotation_numbers:
        suffix = quotation_number.removeprefix(prefix)
        if suffix != quotation_number and suffix.isdecimal():
            largest_sequence = max(largest_sequence, int(suffix))
    return largest_sequence + 1


def _lock_daily_quotation_sequence(session: Session, quotation_date: date) -> None:
    """Serialize daily allocations across serverless PostgreSQL instances."""
    if session.get_bind().dialect.name == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(CAST(:lock_key AS bigint))"),
            {"lock_key": int(quotation_date.strftime("%Y%m%d"))},
        )


def _next_quotation_number(session: Session, quotation_date: date | None = None) -> str:
    """Allocate the next human-readable number for the China business day."""
    allocation_date = quotation_date or datetime.now(BUSINESS_TIME_ZONE).date()
    prefix = _daily_quotation_prefix(allocation_date)
    _lock_daily_quotation_sequence(session, allocation_date)
    existing_numbers = session.scalars(
        select(Quotation.quotation_number).where(Quotation.quotation_number.like(f"{prefix}%"))
    ).all()
    return f"{prefix}{_next_daily_sequence(existing_numbers, prefix)}"


def _ensure_read_access(user: User, quotation: Quotation) -> None:
    if quotation.opportunity is not None:
        if user.role is UserRole.SALES and quotation.opportunity.owner_id != user.id:
            raise ForbiddenError("You may only access quotations for your own opportunities.")
        return
    access_service.ensure_customer_read_access(user, quotation.customer)


def _ensure_write_access(user: User, quotation: Quotation) -> None:
    if user.role is UserRole.VIEWER:
        raise ForbiddenError("Viewer accounts have read-only access.")
    _ensure_read_access(user, quotation)


def _ensure_delete_access(user: User) -> None:
    if user.role is not UserRole.ADMIN:
        raise ForbiddenError("Only Admin accounts can delete quotations.")


def _load_quotation(session: Session, quotation_id: int) -> Quotation:
    quotation = session.scalar(
        select(Quotation)
        .where(Quotation.id == quotation_id)
        .options(
            joinedload(Quotation.customer),
            joinedload(Quotation.opportunity),
            selectinload(Quotation.versions).selectinload(QuotationVersion.items),
        )
    )
    if quotation is None:
        raise NotFoundError("Quotation not found.")
    return quotation


def _version(quotation: Quotation, version_no: int | None = None) -> QuotationVersion:
    selected_no = version_no or quotation.current_version
    selected = next(
        (version for version in quotation.versions if version.version_no == selected_no), None
    )
    if selected is None:
        raise NotFoundError("Quotation version not found.")
    return selected


def _version_summary(version: QuotationVersion) -> QuotationVersionSummary:
    return QuotationVersionSummary.model_validate(version, from_attributes=True)


def _version_read(version: QuotationVersion) -> QuotationVersionRead:
    return QuotationVersionRead.model_validate(version, from_attributes=True)


def _list_item(quotation: Quotation) -> QuotationListItem:
    current = _version(quotation)
    return QuotationListItem(
        id=quotation.id,
        quotation_number=quotation.quotation_number,
        customer_id=quotation.customer_id,
        customer_company=quotation.customer.company_name,
        opportunity_id=quotation.opportunity_id,
        opportunity_name=quotation.opportunity.name if quotation.opportunity else None,
        status=quotation.status,
        current_version=quotation.current_version,
        currency=current.currency,
        total_amount=current.total_amount,
        created_at=quotation.created_at,
        updated_at=quotation.updated_at,
    )


def _detail(quotation: Quotation, version_no: int | None = None) -> QuotationDetail:
    settings = get_settings()
    return QuotationDetail(
        **_list_item(quotation).model_dump(),
        versions=[_version_summary(version) for version in quotation.versions],
        selected_version=_version_read(_version(quotation, version_no)),
        company_contact={
            "name": settings["company_name"],
            "website": settings["company_website"],
            "email": settings["company_email"],
            "whatsapp": settings["company_whatsapp"],
        },
    )


def list_quotations(
    session: Session,
    user: User,
    limit: int,
    offset: int,
    query: str | None = None,
    status: QuotationStatus | None = None,
    customer_id: int | None = None,
) -> tuple[list[QuotationListItem], int]:
    filters = []
    if user.role is UserRole.SALES:
        filters.append(
            or_(Quotation.opportunity_id.is_(None), Opportunity.owner_id == user.id)
        )
    if status is not None:
        filters.append(Quotation.status == status)
    if customer_id is not None:
        filters.append(Quotation.customer_id == customer_id)
    search_term = query.strip() if query else ""
    if search_term:
        term = f"%{search_term}%"
        filters.append(
            or_(Quotation.quotation_number.ilike(term), Customer.company_name.ilike(term))
        )
    base = select(Quotation).join(Customer).outerjoin(Opportunity).where(*filters)
    statement = (
        base.options(
            joinedload(Quotation.customer),
            joinedload(Quotation.opportunity),
            selectinload(Quotation.versions),
        )
        .order_by(Quotation.updated_at.desc(), Quotation.id.desc())
        .limit(limit)
        .offset(offset)
    )
    count_statement = (
        select(func.count()).select_from(Quotation).join(Customer).outerjoin(Opportunity).where(*filters)
    )
    total = session.scalar(count_statement) or 0
    return [_list_item(quotation) for quotation in session.scalars(statement)], total


def get_quotation_detail(
    session: Session, quotation_id: int, user: User, version_no: int | None = None
) -> QuotationDetail:
    quotation = _load_quotation(session, quotation_id)
    _ensure_read_access(user, quotation)
    return _detail(quotation, version_no)


def delete_quotation(session: Session, quotation_id: int, user: User) -> None:
    """Remove one quotation and its immutable snapshots without deleting sales records.

    The database and ORM cascade quotation versions and their item snapshots.
    Its customer and optional opportunity are deliberately retained, including
    the opportunity's product lines, so deleting an erroneous quotation cannot
    erase the underlying customer or sales project.
    """
    _ensure_delete_access(user)
    quotation = _load_quotation(session, quotation_id)
    try:
        session.delete(quotation)
        session.commit()
    except Exception:
        session.rollback()
        raise


def _build_items(
    session: Session, inputs: list[QuotationItemInput]
) -> tuple[list[QuotationItem], Decimal]:
    product_ids = [item.product_id for item in inputs]
    if len(product_ids) != len(set(product_ids)):
        raise ConflictError("Each product may only appear once in a quotation version.")
    products = {
        product.id: product
        for product in session.scalars(
            select(Product)
            .where(Product.id.in_(product_ids))
            .options(selectinload(Product.images))
        )
    }
    if set(product_ids) != set(products):
        raise NotFoundError("One or more quotation products were not found.")
    result = []
    subtotal = Decimal("0.00")
    for entry in inputs:
        product = products[entry.product_id]
        primary = next((image for image in product.images if image.is_primary), None)
        picture = primary or (product.images[0] if product.images else None)
        line_total = (entry.unit_price * entry.quantity).quantize(MONEY)
        subtotal += line_total
        result.append(
            QuotationItem(
                product_id=product.id,
                sku_snapshot=product.sku,
                product_name_snapshot=product.name,
                picture_snapshot=picture.image_url if picture else None,
                unit_price=entry.unit_price.quantize(MONEY),
                quantity=entry.quantity,
                line_total=line_total,
            )
        )
    return result, subtotal.quantize(MONEY)


def _opportunity_inputs(opportunity: Opportunity) -> list[QuotationItemInput]:
    return [
        QuotationItemInput(
            product_id=item.product_id,
            unit_price=item.target_price or item.product.reference_price or Decimal("0.00"),
            quantity=item.quantity,
        )
        for item in opportunity.product_items
    ]


def create_quotation(
    session: Session, payload: QuotationCreate, creator: User
) -> QuotationDetail:
    if creator.role is UserRole.VIEWER:
        raise ForbiddenError("Viewer accounts have read-only access.")
    try:
        if payload.opportunity_id is not None:
            # Keep the existing opportunity-first workflow unchanged. An explicitly
            # supplied relationship is authoritative and must never create a second
            # opportunity.
            opportunity = opportunity_service.get_opportunity(session, payload.opportunity_id)
            if creator.role is UserRole.SALES and opportunity.owner_id != creator.id:
                raise ForbiddenError("You may only quote opportunities assigned to you.")
            customer = opportunity.customer
            item_inputs = payload.items or _opportunity_inputs(opportunity)
            if not item_inputs:
                raise ConflictError("Add products to the opportunity before creating a quotation.")
            items, subtotal = _build_items(session, item_inputs)
        else:
            # Customer-first creation may start as an empty draft. The formal
            # quotation editor owns products and commercial terms, so do not create
            # an empty opportunity before a product line has actually been saved.
            customer = session.get(Customer, payload.customer_id)
            if customer is None:
                raise NotFoundError("Customer not found.")
            access_service.ensure_customer_manage_access(creator, customer)
            item_inputs = payload.items or []
            items, subtotal = _build_items(session, item_inputs)
            opportunity = None
            if items:
                total_amount = (subtotal + payload.shipping_cost).quantize(MONEY)
                opportunity, _created = opportunity_service.create_or_link_quotation_opportunity(
                    session,
                    customer=customer,
                    items=items,
                    total_amount=total_amount,
                    currency=payload.currency,
                    creator=creator,
                )

        quotation = Quotation(
            quotation_number=f"TEMP-{uuid4().hex}",
            customer_id=customer.id,
            opportunity_id=opportunity.id if opportunity is not None else None,
            status=QuotationStatus.DRAFT,
            current_version=1,
        )
        session.add(quotation)
        session.flush()
        quotation.quotation_number = _next_quotation_number(session)
        version = QuotationVersion(
            version_no=1,
            currency=payload.currency,
            payment_term=payload.payment_term,
            delivery_time=payload.delivery_time,
            validity_days=payload.validity_days,
            shipping_cost=payload.shipping_cost,
            subtotal=subtotal,
            total_amount=(subtotal + payload.shipping_cost).quantize(MONEY),
            items=items,
        )
        quotation.versions.append(version)
        # The quotation, its version/items, the opportunity link and its product
        # lines are all committed together. Any exception rolls every part back.
        session.commit()
    except Exception:
        session.rollback()
        raise
    return _detail(_load_quotation(session, quotation.id))


def update_quotation(
    session: Session, quotation_id: int, payload: QuotationUpdate, editor: User
) -> QuotationDetail:
    quotation = _load_quotation(session, quotation_id)
    _ensure_write_access(editor, quotation)
    if quotation.status is not QuotationStatus.DRAFT:
        raise ConflictError("Sent quotation versions are immutable; create a new version.")
    current = _version(quotation)
    item_inputs = payload.items
    changes = payload.model_dump(exclude_unset=True, exclude={"items"})
    for field, value in changes.items():
        if value is None:
            raise ConflictError(f"{field} cannot be null.")
        setattr(current, field, value)
    if item_inputs is not None:
        items, subtotal = _build_items(session, item_inputs)
        current.items = items
        current.subtotal = subtotal
    current.total_amount = (current.subtotal + current.shipping_cost).quantize(MONEY)
    if quotation.opportunity is None and current.items:
        opportunity, _created = opportunity_service.create_or_link_quotation_opportunity(
            session,
            customer=quotation.customer,
            items=current.items,
            total_amount=current.total_amount,
            currency=current.currency,
            creator=editor,
        )
        quotation.opportunity_id = opportunity.id
    elif quotation.opportunity is not None and current.items:
        opportunity_service.sync_quotation_opportunity(
            session,
            opportunity=quotation.opportunity,
            items=current.items,
            total_amount=current.total_amount,
            currency=current.currency,
        )
    current.pdf_url = None
    session.commit()
    return _detail(_load_quotation(session, quotation.id))


def create_version(session: Session, quotation_id: int, editor: User) -> QuotationDetail:
    quotation = _load_quotation(session, quotation_id)
    _ensure_write_access(editor, quotation)
    if quotation.status is QuotationStatus.DRAFT:
        raise ConflictError("Finish or send the current draft before creating a new version.")
    previous = _version(quotation)
    next_no = quotation.current_version + 1
    next_version = QuotationVersion(
        version_no=next_no,
        currency=previous.currency,
        payment_term=previous.payment_term,
        delivery_time=previous.delivery_time,
        validity_days=previous.validity_days,
        shipping_cost=previous.shipping_cost,
        subtotal=previous.subtotal,
        total_amount=previous.total_amount,
        items=[
            QuotationItem(
                product_id=item.product_id,
                sku_snapshot=item.sku_snapshot,
                product_name_snapshot=item.product_name_snapshot,
                picture_snapshot=item.picture_snapshot,
                unit_price=item.unit_price,
                quantity=item.quantity,
                line_total=item.line_total,
            )
            for item in previous.items
        ],
    )
    quotation.versions.append(next_version)
    quotation.current_version = next_no
    quotation.status = QuotationStatus.DRAFT
    session.commit()
    return _detail(_load_quotation(session, quotation.id))


def generate_pdf(
    session: Session, quotation_id: int, editor: User, version_no: int | None = None
) -> QuotationDetail:
    quotation = _load_quotation(session, quotation_id)
    _ensure_write_access(editor, quotation)
    version = _version(quotation, version_no)
    # Validate that a PDF can be produced, without persisting it on the
    # function filesystem. Downloads re-render this immutable version on demand.
    quotation_pdf_service.generate_quotation_pdf_bytes(
        quotation, version, quotation.customer
    )
    version.pdf_url = (
        f"/api/v1/quotations/{quotation.id}/pdf?version_no={version.version_no}"
    )
    session.commit()
    return _detail(_load_quotation(session, quotation.id), version.version_no)


def mark_sent(session: Session, quotation_id: int, editor: User) -> QuotationDetail:
    quotation = _load_quotation(session, quotation_id)
    _ensure_write_access(editor, quotation)
    if quotation.status is not QuotationStatus.DRAFT:
        raise ConflictError("Only a draft quotation can be marked as sent.")
    version = _version(quotation)
    if not version.pdf_url:
        quotation_pdf_service.generate_quotation_pdf_bytes(
            quotation, version, quotation.customer
        )
        version.pdf_url = (
            f"/api/v1/quotations/{quotation.id}/pdf?version_no={version.version_no}"
        )
    quotation.status = QuotationStatus.SENT
    if quotation.opportunity is not None:
        # A sent quotation creates a short, explicit follow-up task.  It is
        # cleared only by a later follow-up linked to this opportunity.
        sent_at = datetime.now(timezone.utc)
        quotation.opportunity.quotation_sent_at = sent_at
        quotation.opportunity.last_activity_at = sent_at
        quotation.opportunity.quote_followup_due_date = (
            date.today() + timedelta(days=3)
        )
    session.commit()
    return _detail(_load_quotation(session, quotation.id))


def get_pdf_bytes(
    session: Session, quotation_id: int, user: User, version_no: int | None = None
) -> tuple[bytes, str]:
    quotation = _load_quotation(session, quotation_id)
    _ensure_read_access(user, quotation)
    version = _version(quotation, version_no)
    if not version.pdf_url:
        raise NotFoundError("Generate this quotation version PDF first.")
    return (
        quotation_pdf_service.generate_quotation_pdf_bytes(
            quotation, version, quotation.customer
        ),
        f"{quotation.quotation_number}.pdf",
    )


def get_excel_bytes(
    session: Session, quotation_id: int, user: User, version_no: int | None = None
) -> tuple[bytes, str]:
    """Export a selected immutable quotation version as an editable workbook."""
    quotation = _load_quotation(session, quotation_id)
    _ensure_read_access(user, quotation)
    version = _version(quotation, version_no)
    return (
        quotation_excel_service.generate_quotation_excel(
            quotation, version, quotation.customer
        ),
        quotation_excel_service.quotation_excel_filename(
            quotation.quotation_number, version.version_no
        ),
    )
