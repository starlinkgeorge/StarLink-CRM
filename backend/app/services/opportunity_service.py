from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.customer import Customer
from app.models.lead import Opportunity, OpportunityStage, OpportunityStageHistory
from app.models.product import OpportunityProduct, Product
from app.models.user import User, UserRole
from app.schemas.opportunity import (
    OpportunityCreate,
    OpportunityDetail,
    OpportunityListItem,
    OpportunityUpdate,
)
from app.schemas.product import OpportunityProductRead, OpportunityProductReplace
from app.services import access_service
from app.services.errors import ConflictError, ForbiddenError, NotFoundError


def _ensure_read_access(user: User, opportunity: Opportunity) -> None:
    if user.role is UserRole.SALES and opportunity.owner_id != user.id:
        raise ForbiddenError("You may only access opportunities assigned to you.")


def _ensure_manage_access(user: User, opportunity: Opportunity) -> None:
    if user.role is UserRole.VIEWER:
        raise ForbiddenError("Viewer accounts have read-only access.")
    _ensure_read_access(user, opportunity)


def _validate_owner(session: Session, owner_id: int | None) -> None:
    if owner_id is not None and session.get(User, owner_id) is None:
        raise NotFoundError("Opportunity owner not found.")


def _list_item(opportunity: Opportunity) -> OpportunityListItem:
    item = OpportunityListItem.model_validate(
        {
            **opportunity.__dict__,
            "customer_company": opportunity.customer.company_name,
            "owner_name": opportunity.owner.name if opportunity.owner else None,
        }
    )
    return item


def _product_item(item: OpportunityProduct) -> OpportunityProductRead:
    primary_image = next((image for image in item.product.images if image.is_primary), None)
    return OpportunityProductRead(
        product_id=item.product_id,
        sku=item.product.sku,
        name=item.product.name,
        quantity=item.quantity,
        target_price=item.target_price,
        reference_price=item.product.reference_price,
        currency_code=item.product.currency_code,
        image_url=primary_image.image_url if primary_image else None,
    )


def list_opportunities(
    session: Session,
    user: User,
    limit: int,
    offset: int,
    query: str | None = None,
    stage: OpportunityStage | None = None,
    customer_id: int | None = None,
) -> tuple[list[OpportunityListItem], int]:
    filters = []
    if user.role is UserRole.SALES:
        filters.append(Opportunity.owner_id == user.id)
    if stage is not None:
        filters.append(Opportunity.stage == stage)
    if customer_id is not None:
        filters.append(Opportunity.customer_id == customer_id)
    search_term = query.strip() if query else ""
    if search_term:
        term = f"%{search_term}%"
        filters.append(
            or_(
                Opportunity.name.ilike(term),
                Opportunity.interested_product.ilike(term),
                Customer.company_name.ilike(term),
            )
        )

    base = select(Opportunity).join(Customer).where(*filters)
    statement = (
        base.options(joinedload(Opportunity.customer), joinedload(Opportunity.owner))
        .order_by(Opportunity.updated_at.desc(), Opportunity.id.desc())
        .limit(limit)
        .offset(offset)
    )
    total = (
        session.scalar(
            select(func.count()).select_from(Opportunity).join(Customer).where(*filters)
        )
        or 0
    )
    items = [_list_item(opportunity) for opportunity in session.scalars(statement)]
    return items, total


def get_opportunity(session: Session, opportunity_id: int) -> Opportunity:
    statement = (
        select(Opportunity)
        .where(Opportunity.id == opportunity_id)
        .options(
            joinedload(Opportunity.owner),
            joinedload(Opportunity.customer).selectinload(Customer.followups),
            selectinload(Opportunity.stage_history),
            selectinload(Opportunity.product_items)
            .joinedload(OpportunityProduct.product)
            .selectinload(Product.images),
        )
    )
    opportunity = session.scalar(statement)
    if opportunity is None:
        raise NotFoundError("Opportunity not found.")
    return opportunity


def get_opportunity_detail(
    session: Session, opportunity_id: int, user: User
) -> OpportunityDetail:
    opportunity = get_opportunity(session, opportunity_id)
    _ensure_read_access(user, opportunity)
    return OpportunityDetail.model_validate(
        {
            **opportunity.__dict__,
            "customer_company": opportunity.customer.company_name,
            "owner_name": opportunity.owner.name if opportunity.owner else None,
            "customer": opportunity.customer,
            "stage_history": opportunity.stage_history,
            "followups": opportunity.customer.followups,
            "products": [_product_item(item) for item in opportunity.product_items],
        }
    )


def create_opportunity(
    session: Session, payload: OpportunityCreate, creator: User
) -> OpportunityListItem:
    if creator.role is UserRole.VIEWER:
        raise ForbiddenError("Viewer accounts have read-only access.")
    customer = session.get(Customer, payload.customer_id)
    if customer is None:
        raise NotFoundError("Customer not found.")
    access_service.ensure_customer_read_access(creator, customer)

    data = payload.model_dump()
    if creator.role is UserRole.SALES:
        if data["owner_id"] not in (None, creator.id):
            raise ForbiddenError("Sales users may only create their own opportunities.")
        data["owner_id"] = creator.id
    elif data["owner_id"] is None:
        data["owner_id"] = creator.id
    _validate_owner(session, data["owner_id"])

    opportunity = Opportunity(**data)
    session.add(opportunity)
    session.flush()
    session.add(
        OpportunityStageHistory(
            opportunity_id=opportunity.id,
            old_stage=None,
            new_stage=opportunity.stage,
            changed_by_id=creator.id,
        )
    )
    session.commit()
    return _list_item(get_opportunity(session, opportunity.id))


def update_opportunity(
    session: Session,
    opportunity_id: int,
    payload: OpportunityUpdate,
    editor: User,
) -> OpportunityDetail:
    opportunity = get_opportunity(session, opportunity_id)
    _ensure_manage_access(editor, opportunity)
    changes = payload.model_dump(exclude_unset=True)
    if editor.role is UserRole.SALES and "owner_id" in changes:
        if changes["owner_id"] != editor.id:
            raise ForbiddenError("Sales users may not reassign opportunities.")
    if "owner_id" in changes:
        _validate_owner(session, changes["owner_id"])
    next_stage = changes.get("stage", opportunity.stage)
    if next_stage != opportunity.stage:
        session.add(
            OpportunityStageHistory(
                opportunity_id=opportunity.id,
                old_stage=opportunity.stage,
                new_stage=next_stage,
                changed_by_id=editor.id,
            )
        )
    for field, value in changes.items():
        setattr(opportunity, field, value)
    session.commit()
    return get_opportunity_detail(session, opportunity.id, editor)


def replace_opportunity_products(
    session: Session,
    opportunity_id: int,
    payload: OpportunityProductReplace,
    editor: User,
) -> OpportunityDetail:
    opportunity = get_opportunity(session, opportunity_id)
    _ensure_manage_access(editor, opportunity)
    product_ids = [item.product_id for item in payload.items]
    if len(product_ids) != len(set(product_ids)):
        raise ConflictError("Each product may only appear once in an opportunity.")
    if product_ids:
        existing_ids = set(
            session.scalars(select(Product.id).where(Product.id.in_(product_ids)))
        )
        missing_ids = set(product_ids) - existing_ids
        if missing_ids:
            raise NotFoundError("One or more products were not found.")
    opportunity.product_items.clear()
    session.flush()
    opportunity.product_items.extend(
        OpportunityProduct(
            product_id=item.product_id,
            quantity=item.quantity,
            target_price=item.target_price,
        )
        for item in payload.items
    )
    session.commit()
    return get_opportunity_detail(session, opportunity.id, editor)
