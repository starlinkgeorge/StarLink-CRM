from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.customer import Customer
from app.models.followup import FollowUp
from app.models.lead import (
    Opportunity,
    OpportunitySalesStage,
    OpportunitySalesStageHistory,
    OpportunityStage,
    OpportunityStageHistory,
)
from app.models.product import OpportunityProduct, Product
from app.models.user import User, UserRole
from app.schemas.opportunity import (
    OpportunityCreate,
    OpportunityDetail,
    OpportunityListItem,
    OpportunityPipeline,
    OpportunityPipelineColumn,
    OpportunityUpdate,
)
from app.schemas.product import OpportunityProductRead, OpportunityProductReplace
from app.services import access_service
from app.services.errors import ConflictError, ForbiddenError, NotFoundError


# The V3 enum is still persisted for existing clients and quotation workflows.
# V7 adds more granular stages and maps them to the nearest legacy value.
SALES_STAGE_TO_LEGACY_STAGE = {
    OpportunitySalesStage.NEW_LEAD: OpportunityStage.LEAD,
    OpportunitySalesStage.CONTACTED: OpportunityStage.QUALIFIED,
    OpportunitySalesStage.REQUIREMENT_CONFIRMED: OpportunityStage.QUALIFIED,
    OpportunitySalesStage.QUOTATION_SENT: OpportunityStage.PROPOSAL,
    OpportunitySalesStage.NEGOTIATION: OpportunityStage.NEGOTIATION,
    OpportunitySalesStage.WON: OpportunityStage.WON,
    OpportunitySalesStage.LOST: OpportunityStage.LOST,
}
LEGACY_STAGE_TO_SALES_STAGE = {
    OpportunityStage.LEAD: OpportunitySalesStage.NEW_LEAD,
    OpportunityStage.QUALIFIED: OpportunitySalesStage.REQUIREMENT_CONFIRMED,
    OpportunityStage.PROPOSAL: OpportunitySalesStage.QUOTATION_SENT,
    OpportunityStage.NEGOTIATION: OpportunitySalesStage.NEGOTIATION,
    OpportunityStage.WON: OpportunitySalesStage.WON,
    OpportunityStage.LOST: OpportunitySalesStage.LOST,
}
DEFAULT_PROBABILITY_BY_SALES_STAGE = {
    OpportunitySalesStage.NEW_LEAD: 10,
    OpportunitySalesStage.CONTACTED: 20,
    OpportunitySalesStage.REQUIREMENT_CONFIRMED: 40,
    OpportunitySalesStage.QUOTATION_SENT: 60,
    OpportunitySalesStage.NEGOTIATION: 80,
    OpportunitySalesStage.WON: 100,
    OpportunitySalesStage.LOST: 0,
}


def _as_sales_stage(value: OpportunitySalesStage | str) -> OpportunitySalesStage:
    return value if isinstance(value, OpportunitySalesStage) else OpportunitySalesStage(value)


def _prepare_create_data(payload: OpportunityCreate) -> dict:
    """Resolve old and new pipeline fields without changing legacy client behaviour."""
    data = payload.model_dump()
    fields_set = payload.model_fields_set
    requested_sales_stage = data.get("sales_stage")
    requested_legacy_stage = data.get("stage")

    if "sales_stage" in fields_set and requested_sales_stage is not None:
        sales_stage = _as_sales_stage(requested_sales_stage)
        legacy_stage = SALES_STAGE_TO_LEGACY_STAGE[sales_stage]
    elif "stage" in fields_set and requested_legacy_stage is not None:
        legacy_stage = requested_legacy_stage
        sales_stage = LEGACY_STAGE_TO_SALES_STAGE[legacy_stage]
    else:
        sales_stage = OpportunitySalesStage.NEW_LEAD
        legacy_stage = OpportunityStage.LEAD

    data["sales_stage"] = sales_stage.value
    data["stage"] = legacy_stage
    if data.get("probability") is None:
        data["probability"] = DEFAULT_PROBABILITY_BY_SALES_STAGE[sales_stage]
    return data


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
    sales_stage: OpportunitySalesStage | None = None,
    customer_id: int | None = None,
) -> tuple[list[OpportunityListItem], int]:
    filters = []
    if user.role is UserRole.SALES:
        filters.append(Opportunity.owner_id == user.id)
    if stage is not None:
        filters.append(Opportunity.stage == stage)
    if sales_stage is not None:
        filters.append(Opportunity.sales_stage == sales_stage.value)
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
            joinedload(Opportunity.customer)
            .selectinload(Customer.followups)
            .selectinload(FollowUp.attachments),
            selectinload(Opportunity.stage_history),
            selectinload(Opportunity.sales_stage_history),
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
            "sales_stage_history": opportunity.sales_stage_history,
            "followups": [
                followup
                for followup in opportunity.customer.followups
                if followup.opportunity_id in (None, opportunity.id)
            ],
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

    data = _prepare_create_data(payload)
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
    session.add(
        OpportunitySalesStageHistory(
            opportunity_id=opportunity.id,
            old_sales_stage=None,
            new_sales_stage=opportunity.sales_stage,
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
    # These values are non-null database fields. Treat an explicit null from an
    # older partial-update client as "not supplied" instead of emitting a 500.
    for required_field in ("stage", "sales_stage", "probability"):
        if changes.get(required_field) is None:
            changes.pop(required_field, None)
    if editor.role is UserRole.SALES and "owner_id" in changes:
        if changes["owner_id"] != editor.id:
            raise ForbiddenError("Sales users may not reassign opportunities.")
    if "owner_id" in changes:
        _validate_owner(session, changes["owner_id"])
    current_sales_stage = _as_sales_stage(opportunity.sales_stage)
    if changes.get("sales_stage") is not None:
        next_sales_stage = _as_sales_stage(changes["sales_stage"])
        changes["sales_stage"] = next_sales_stage.value
        changes["stage"] = SALES_STAGE_TO_LEGACY_STAGE[next_sales_stage]
    elif changes.get("stage") is not None:
        next_sales_stage = LEGACY_STAGE_TO_SALES_STAGE[changes["stage"]]
        changes["sales_stage"] = next_sales_stage.value
    else:
        next_sales_stage = current_sales_stage

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
    if next_sales_stage != current_sales_stage:
        session.add(
            OpportunitySalesStageHistory(
                opportunity_id=opportunity.id,
                old_sales_stage=current_sales_stage.value,
                new_sales_stage=next_sales_stage.value,
                changed_by_id=editor.id,
            )
        )
    for field, value in changes.items():
        setattr(opportunity, field, value)
    session.commit()
    return get_opportunity_detail(session, opportunity.id, editor)


def get_sales_pipeline(session: Session, user: User) -> OpportunityPipeline:
    """Return all visible opportunities grouped into stable Kanban columns."""
    filters = []
    if user.role is UserRole.SALES:
        filters.append(Opportunity.owner_id == user.id)
    opportunities = list(
        session.scalars(
            select(Opportunity)
            .where(*filters)
            .options(joinedload(Opportunity.customer), joinedload(Opportunity.owner))
            .order_by(
                Opportunity.expected_close_date.is_(None),
                Opportunity.expected_close_date.asc(),
                Opportunity.updated_at.desc(),
            )
        )
    )
    grouped: dict[OpportunitySalesStage, list[OpportunityListItem]] = {
        sales_stage: [] for sales_stage in OpportunitySalesStage
    }
    for opportunity in opportunities:
        grouped[_as_sales_stage(opportunity.sales_stage)].append(_list_item(opportunity))
    return OpportunityPipeline(
        columns=[
            OpportunityPipelineColumn(
                sales_stage=sales_stage,
                count=len(grouped[sales_stage]),
                opportunities=grouped[sales_stage],
            )
            for sales_stage in OpportunitySalesStage
        ]
    )


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
