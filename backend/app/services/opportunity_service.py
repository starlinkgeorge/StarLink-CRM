from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.customer import Customer
from app.models.followup import FollowUp
from app.models.opportunity import (
    Opportunity,
    OpportunityDealStage,
    OpportunityDealStageHistory,
    OpportunitySalesStage,
    OpportunitySalesStageHistory,
    OpportunityStage,
    OpportunityStageHistory,
)
from app.models.product import OpportunityProduct, Product
from app.models.quotation import Quotation, QuotationItem
from app.models.user import User, UserRole
from app.schemas.opportunity import (
    OpportunityCreate,
    OpportunityDealPipeline,
    OpportunityDealPipelineColumn,
    OpportunityDetail,
    OpportunityListItem,
    OpportunityPipeline,
    OpportunityPipelineColumn,
    OpportunityUpdate,
)
from app.schemas.product import OpportunityProductRead, OpportunityProductReplace
from app.schemas.quotation import QuotationListItem
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

DEAL_STAGE_TO_SALES_STAGE = {
    OpportunityDealStage.NEW_INQUIRY: OpportunitySalesStage.NEW_LEAD,
    OpportunityDealStage.CONTACTED: OpportunitySalesStage.CONTACTED,
    OpportunityDealStage.QUOTED: OpportunitySalesStage.QUOTATION_SENT,
    OpportunityDealStage.NEGOTIATING: OpportunitySalesStage.NEGOTIATION,
    OpportunityDealStage.WON: OpportunitySalesStage.WON,
    OpportunityDealStage.LOST: OpportunitySalesStage.LOST,
}
SALES_STAGE_TO_DEAL_STAGE = {
    OpportunitySalesStage.NEW_LEAD: OpportunityDealStage.NEW_INQUIRY,
    OpportunitySalesStage.CONTACTED: OpportunityDealStage.CONTACTED,
    # V9 intentionally folds this V7-only internal stage into "已联系".
    OpportunitySalesStage.REQUIREMENT_CONFIRMED: OpportunityDealStage.CONTACTED,
    OpportunitySalesStage.QUOTATION_SENT: OpportunityDealStage.QUOTED,
    OpportunitySalesStage.NEGOTIATION: OpportunityDealStage.NEGOTIATING,
    OpportunitySalesStage.WON: OpportunityDealStage.WON,
    OpportunitySalesStage.LOST: OpportunityDealStage.LOST,
}


def _as_sales_stage(value: OpportunitySalesStage | str) -> OpportunitySalesStage:
    return value if isinstance(value, OpportunitySalesStage) else OpportunitySalesStage(value)


def _as_deal_stage(value: OpportunityDealStage | str) -> OpportunityDealStage:
    return value if isinstance(value, OpportunityDealStage) else OpportunityDealStage(value)


def _prepare_create_data(payload: OpportunityCreate) -> dict:
    """Resolve old and new pipeline fields without changing legacy client behaviour."""
    data = payload.model_dump()
    fields_set = payload.model_fields_set
    requested_deal_stage = data.get("deal_stage")
    requested_sales_stage = data.get("sales_stage")
    requested_legacy_stage = data.get("stage")

    if "deal_stage" in fields_set and requested_deal_stage is not None:
        deal_stage = _as_deal_stage(requested_deal_stage)
        sales_stage = DEAL_STAGE_TO_SALES_STAGE[deal_stage]
        legacy_stage = SALES_STAGE_TO_LEGACY_STAGE[sales_stage]
    elif "sales_stage" in fields_set and requested_sales_stage is not None:
        sales_stage = _as_sales_stage(requested_sales_stage)
        legacy_stage = SALES_STAGE_TO_LEGACY_STAGE[sales_stage]
        deal_stage = SALES_STAGE_TO_DEAL_STAGE[sales_stage]
    elif "stage" in fields_set and requested_legacy_stage is not None:
        legacy_stage = requested_legacy_stage
        sales_stage = LEGACY_STAGE_TO_SALES_STAGE[legacy_stage]
        deal_stage = SALES_STAGE_TO_DEAL_STAGE[sales_stage]
    else:
        sales_stage = OpportunitySalesStage.NEW_LEAD
        legacy_stage = OpportunityStage.LEAD
        deal_stage = OpportunityDealStage.NEW_INQUIRY

    data["sales_stage"] = sales_stage.value
    data["stage"] = legacy_stage
    data["deal_stage"] = deal_stage.value
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


def _ensure_delete_access(user: User) -> None:
    if user.role is not UserRole.ADMIN:
        raise ForbiddenError("Only Admin accounts can delete opportunities.")


def _validate_owner(session: Session, owner_id: int | None) -> None:
    if owner_id is not None and session.get(User, owner_id) is None:
        raise NotFoundError("Opportunity owner not found.")


def _quotation_product_summary(items: Sequence[QuotationItem]) -> str:
    """Return a short, deterministic product description for quotation opportunities."""
    first_name = items[0].product_name_snapshot.strip() if items else "Quotation"
    if len(items) == 1:
        return first_name
    return f"{first_name} + {len(items) - 1} items"


def _quotation_opportunity_name(customer: Customer, items: Sequence[QuotationItem]) -> str:
    """Build a concise name without using fuzzy matching or customer-created text twice."""
    customer_name = (customer.company_name or customer.contact_name or "Customer").strip()
    return f"{customer_name} - {_quotation_product_summary(items)}"[:255]


def _lock_customer_quotation_linking(session: Session, customer_id: int) -> None:
    """Prevent two concurrent customer quotations from creating duplicate exact-match opportunities."""
    if session.get_bind().dialect.name == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(CAST(:lock_key AS bigint))"),
            {"lock_key": 1_000_000_000 + customer_id},
        )


def _is_closed_opportunity(opportunity: Opportunity) -> bool:
    """Recognize all persisted pipeline representations of a closed opportunity."""
    return (
        opportunity.stage in {OpportunityStage.WON, OpportunityStage.LOST}
        or _as_sales_stage(opportunity.sales_stage)
        in {OpportunitySalesStage.WON, OpportunitySalesStage.LOST}
        or _as_deal_stage(opportunity.deal_stage)
        in {OpportunityDealStage.WON, OpportunityDealStage.LOST}
    )


def _find_exact_reusable_quotation_opportunity(
    session: Session,
    *,
    customer_id: int,
    currency: str,
    items: Sequence[QuotationItem],
) -> Opportunity | None:
    """Reuse only one active opportunity with the exact same products and currency.

    This is intentionally stricter than name matching: two projects that merely have
    similar text must never be merged by an automatic quotation workflow.
    """
    quotation_product_ids = {item.product_id for item in items if item.product_id is not None}
    candidates = session.scalars(
        select(Opportunity)
        .where(
            Opportunity.customer_id == customer_id,
            Opportunity.currency == currency,
        )
        .options(selectinload(Opportunity.product_items))
        .order_by(Opportunity.updated_at.desc(), Opportunity.id.desc())
    ).all()
    exact_matches = [
        opportunity
        for opportunity in candidates
        if not _is_closed_opportunity(opportunity)
        and {item.product_id for item in opportunity.product_items} == quotation_product_ids
    ]
    # If two projects meet the mechanical rule, the system cannot safely infer which
    # procurement project the user means. Create a new opportunity instead.
    return exact_matches[0] if len(exact_matches) == 1 else None


def _replace_products_from_quotation(
    session: Session, opportunity: Opportunity, items: Sequence[QuotationItem]
) -> None:
    opportunity.product_items.clear()
    session.flush()
    opportunity.product_items.extend(
        OpportunityProduct(
            product_id=item.product_id,
            quantity=item.quantity,
            target_price=item.unit_price,
        )
        for item in items
        if item.product_id is not None
    )


def _advance_reused_opportunity_to_quoted(
    session: Session, opportunity: Opportunity, editor: User
) -> None:
    """Advance early pipeline stages to quoted, never move a later stage backwards."""
    current_deal_stage = _as_deal_stage(opportunity.deal_stage)
    deal_rank = {
        OpportunityDealStage.NEW_INQUIRY: 0,
        OpportunityDealStage.CONTACTED: 1,
        OpportunityDealStage.QUOTED: 2,
        OpportunityDealStage.NEGOTIATING: 3,
        OpportunityDealStage.WON: 4,
        OpportunityDealStage.LOST: 4,
    }
    if deal_rank[current_deal_stage] >= deal_rank[OpportunityDealStage.QUOTED]:
        return

    previous_sales_stage = _as_sales_stage(opportunity.sales_stage)
    previous_legacy_stage = opportunity.stage
    next_sales_stage = OpportunitySalesStage.QUOTATION_SENT
    next_deal_stage = OpportunityDealStage.QUOTED
    next_legacy_stage = SALES_STAGE_TO_LEGACY_STAGE[next_sales_stage]
    opportunity.sales_stage = next_sales_stage.value
    opportunity.deal_stage = next_deal_stage.value
    opportunity.stage = next_legacy_stage
    opportunity.probability = DEFAULT_PROBABILITY_BY_SALES_STAGE[next_sales_stage]
    session.add(
        OpportunityStageHistory(
            opportunity_id=opportunity.id,
            old_stage=previous_legacy_stage,
            new_stage=next_legacy_stage,
            changed_by_id=editor.id,
        )
    )
    session.add(
        OpportunitySalesStageHistory(
            opportunity_id=opportunity.id,
            old_sales_stage=previous_sales_stage.value,
            new_sales_stage=next_sales_stage.value,
            changed_by_id=editor.id,
        )
    )
    session.add(
        OpportunityDealStageHistory(
            opportunity_id=opportunity.id,
            old_deal_stage=current_deal_stage.value,
            new_deal_stage=next_deal_stage.value,
            changed_by_id=editor.id,
        )
    )


def create_or_link_quotation_opportunity(
    session: Session,
    *,
    customer: Customer,
    items: Sequence[QuotationItem],
    total_amount: Decimal,
    currency: str,
    creator: User,
) -> tuple[Opportunity, bool]:
    """Create or safely reuse an opportunity for a customer-originated quotation.

    The caller owns the transaction and commits the quotation plus this opportunity
    together. The boolean indicates whether a new opportunity was created.
    """
    access_service.ensure_customer_manage_access(creator, customer)
    _lock_customer_quotation_linking(session, customer.id)
    opportunity = _find_exact_reusable_quotation_opportunity(
        session,
        customer_id=customer.id,
        currency=currency,
        items=items,
    )
    now = datetime.now(timezone.utc)
    # A Sales user cannot later manage another owner's opportunity.  In that
    # case a new, correctly owned opportunity is safer than silently creating
    # a quote under a project they cannot access.
    if (
        opportunity is not None
        and creator.role is UserRole.SALES
        and opportunity.owner_id != creator.id
    ):
        opportunity = None

    if opportunity is not None:
        _advance_reused_opportunity_to_quoted(session, opportunity, creator)
        opportunity.amount = total_amount
        opportunity.currency = currency
        opportunity.last_activity_at = now
        _replace_products_from_quotation(session, opportunity, items)
        return opportunity, False

    quoted_sales_stage = OpportunitySalesStage.QUOTATION_SENT
    quoted_deal_stage = OpportunityDealStage.QUOTED
    opportunity = Opportunity(
        customer_id=customer.id,
        owner_id=creator.id,
        name=_quotation_opportunity_name(customer, items),
        interested_product=_quotation_product_summary(items),
        amount=total_amount,
        currency=currency,
        sales_stage=quoted_sales_stage.value,
        deal_stage=quoted_deal_stage.value,
        stage=SALES_STAGE_TO_LEGACY_STAGE[quoted_sales_stage],
        probability=DEFAULT_PROBABILITY_BY_SALES_STAGE[quoted_sales_stage],
        last_activity_at=now,
    )
    session.add(opportunity)
    session.flush()
    _replace_products_from_quotation(session, opportunity, items)
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
    session.add(
        OpportunityDealStageHistory(
            opportunity_id=opportunity.id,
            old_deal_stage=None,
            new_deal_stage=opportunity.deal_stage,
            changed_by_id=creator.id,
        )
    )
    return opportunity, True


def _list_item(opportunity: Opportunity) -> OpportunityListItem:
    item = OpportunityListItem.model_validate(
        {
            **opportunity.__dict__,
            "customer_company": opportunity.customer.company_name,
            "owner_name": opportunity.owner.name if opportunity.owner else None,
            "reminder_status": opportunity.reminder_status,
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


def _quotation_item(
    quotation: Quotation, customer: Customer, opportunity: Opportunity
) -> QuotationListItem:
    current = next(
        (version for version in quotation.versions if version.version_no == quotation.current_version),
        None,
    )
    if current is None:
        raise NotFoundError("Quotation current version not found.")
    return QuotationListItem(
        id=quotation.id,
        quotation_number=quotation.quotation_number,
        customer_id=quotation.customer_id,
        customer_company=customer.company_name,
        opportunity_id=quotation.opportunity_id,
        opportunity_name=opportunity.name,
        status=quotation.status,
        current_version=quotation.current_version,
        currency=current.currency,
        total_amount=current.total_amount,
        created_at=quotation.created_at,
        updated_at=quotation.updated_at,
    )


def list_opportunities(
    session: Session,
    user: User,
    limit: int,
    offset: int,
    query: str | None = None,
    stage: OpportunityStage | None = None,
    sales_stage: OpportunitySalesStage | None = None,
    deal_stage: OpportunityDealStage | None = None,
    customer_id: int | None = None,
) -> tuple[list[OpportunityListItem], int]:
    filters = []
    if user.role is UserRole.SALES:
        filters.append(Opportunity.owner_id == user.id)
    if stage is not None:
        filters.append(Opportunity.stage == stage)
    if sales_stage is not None:
        filters.append(Opportunity.sales_stage == sales_stage.value)
    if deal_stage is not None:
        filters.append(Opportunity.deal_stage == deal_stage.value)
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
            .selectinload(Customer.contacts),
            joinedload(Opportunity.customer)
            .selectinload(Customer.followups)
            .selectinload(FollowUp.attachments),
            selectinload(Opportunity.stage_history),
            selectinload(Opportunity.sales_stage_history),
            selectinload(Opportunity.deal_stage_history),
            selectinload(Opportunity.product_items)
            .joinedload(OpportunityProduct.product)
            .selectinload(Product.images),
            selectinload(Opportunity.quotations).selectinload(Quotation.versions),
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
            "reminder_status": opportunity.reminder_status,
            "customer": opportunity.customer,
            "contacts": opportunity.customer.contacts,
            "stage_history": opportunity.stage_history,
            "sales_stage_history": opportunity.sales_stage_history,
            "deal_stage_history": opportunity.deal_stage_history,
            "followups": [
                followup
                for followup in opportunity.customer.followups
                if followup.opportunity_id in (None, opportunity.id)
            ],
            "products": [_product_item(item) for item in opportunity.product_items],
            "quotations": [
                _quotation_item(quotation, opportunity.customer, opportunity)
                for quotation in opportunity.quotations
            ],
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
    session.add(
        OpportunityDealStageHistory(
            opportunity_id=opportunity.id,
            old_deal_stage=None,
            new_deal_stage=opportunity.deal_stage,
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
    for required_field in ("stage", "sales_stage", "deal_stage", "probability"):
        if changes.get(required_field) is None:
            changes.pop(required_field, None)
    if editor.role is UserRole.SALES and "owner_id" in changes:
        if changes["owner_id"] != editor.id:
            raise ForbiddenError("Sales users may not reassign opportunities.")
    if "owner_id" in changes:
        _validate_owner(session, changes["owner_id"])
    current_sales_stage = _as_sales_stage(opportunity.sales_stage)
    current_deal_stage = _as_deal_stage(opportunity.deal_stage)
    if changes.get("deal_stage") is not None:
        next_deal_stage = _as_deal_stage(changes["deal_stage"])
        next_sales_stage = DEAL_STAGE_TO_SALES_STAGE[next_deal_stage]
        changes["deal_stage"] = next_deal_stage.value
        changes["sales_stage"] = next_sales_stage.value
        changes["stage"] = SALES_STAGE_TO_LEGACY_STAGE[next_sales_stage]
    elif changes.get("sales_stage") is not None:
        next_sales_stage = _as_sales_stage(changes["sales_stage"])
        next_deal_stage = SALES_STAGE_TO_DEAL_STAGE[next_sales_stage]
        changes["sales_stage"] = next_sales_stage.value
        changes["deal_stage"] = next_deal_stage.value
        changes["stage"] = SALES_STAGE_TO_LEGACY_STAGE[next_sales_stage]
    elif changes.get("stage") is not None:
        next_sales_stage = LEGACY_STAGE_TO_SALES_STAGE[changes["stage"]]
        next_deal_stage = SALES_STAGE_TO_DEAL_STAGE[next_sales_stage]
        changes["sales_stage"] = next_sales_stage.value
        changes["deal_stage"] = next_deal_stage.value
    else:
        next_sales_stage = current_sales_stage
        next_deal_stage = current_deal_stage

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
    if next_deal_stage != current_deal_stage:
        session.add(
            OpportunityDealStageHistory(
                opportunity_id=opportunity.id,
                old_deal_stage=current_deal_stage.value,
                new_deal_stage=next_deal_stage.value,
                changed_by_id=editor.id,
            )
        )
    for field, value in changes.items():
        setattr(opportunity, field, value)
    if changes:
        opportunity.last_activity_at = datetime.now(timezone.utc)
    session.commit()
    return get_opportunity_detail(session, opportunity.id, editor)


def delete_opportunity(session: Session, opportunity_id: int, user: User) -> None:
    """Remove an opportunity without deleting the related commercial records.

    The database cascades the opportunity's own product lines and stage histories.
    Foreign keys on quotations, follow-ups, and inquiries use ``SET NULL``, so
    deleting an erroneous sales project keeps those original records available.
    """
    _ensure_delete_access(user)
    opportunity = get_opportunity(session, opportunity_id)
    try:
        session.delete(opportunity)
        session.commit()
    except Exception:
        session.rollback()
        raise


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


def get_deal_pipeline(session: Session, user: User) -> OpportunityDealPipeline:
    """Return the six V9 sales stages without changing the V7 pipeline endpoint."""
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
    grouped: dict[OpportunityDealStage, list[OpportunityListItem]] = {
        deal_stage: [] for deal_stage in OpportunityDealStage
    }
    for opportunity in opportunities:
        grouped[_as_deal_stage(opportunity.deal_stage)].append(_list_item(opportunity))
    return OpportunityDealPipeline(
        columns=[
            OpportunityDealPipelineColumn(
                deal_stage=deal_stage,
                count=len(grouped[deal_stage]),
                opportunities=grouped[deal_stage],
            )
            for deal_stage in OpportunityDealStage
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
    opportunity.last_activity_at = datetime.now(timezone.utc)
    session.commit()
    return get_opportunity_detail(session, opportunity.id, editor)
