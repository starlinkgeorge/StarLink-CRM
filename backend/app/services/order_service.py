from decimal import Decimal
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.customer import Customer
from app.models.opportunity import Opportunity
from app.models.order import Order
from app.models.quotation import Quotation, QuotationVersion
from app.models.user import User, UserRole
from app.schemas.order import OrderCreate, OrderRead, OrderUpdate
from app.services import access_service
from app.services.errors import ConflictError, ForbiddenError, NotFoundError

def _visible(user: User):
    if user.role is UserRole.SALES:
        return or_(Order.owner_id == user.id, Customer.owner_id == user.id, Opportunity.owner_id == user.id)
    return None
def _read(session: Session, user: User, order_id: int) -> Order:
    order = session.get(Order, order_id)
    if not order: raise NotFoundError("Order not found.")
    scope = _visible(user)
    if scope is not None:
        allowed = session.scalar(select(Order.id).join(Customer).outerjoin(Opportunity).where(Order.id == order_id, scope))
        if not allowed: raise ForbiddenError("You may only access orders in your business scope.")
    return order
def _serialize(session: Session, order: Order) -> OrderRead:
    customer = session.get(Customer, order.customer_id)
    owner_name = session.get(User, order.owner_id).name if order.owner_id and session.get(User, order.owner_id) else None
    is_accounted = all(value is not None for value in (
        order.rmb_received_amount, order.purchase_cost, order.freight_cost,
    ))
    profit = (
        order.rmb_received_amount - order.purchase_cost - order.freight_cost
        if is_accounted else None
    )
    margin = (
        profit / order.rmb_received_amount * Decimal("100")
        if profit is not None and order.rmb_received_amount else None
    )
    rate = (
        order.rmb_received_amount / order.order_amount
        if order.rmb_received_amount is not None and order.order_amount and order.currency != "CNY"
        else None
    )
    return OrderRead.model_validate({
        **order.__dict__, "customer_company": customer.company_name if customer else "—",
        "owner_name": owner_name, "profit": profit, "profit_margin": margin,
        "realized_exchange_rate": rate,
        "profit_accounting_status": "Accounted" if is_accounted else "Pending",
    })


def serialize_order(session: Session, order: Order) -> OrderRead:
    """Public serialization helper for the Opportunity order workflow."""
    return _serialize(session, order)
def list_orders(session: Session, user: User, limit: int, offset: int, q: str | None = None, customer_id: int | None = None, start=None, end=None, payment_status=None, production_status=None, shipping_status=None):
    filters=[]; scope=_visible(user)
    if scope is not None: filters.append(scope)
    if q and q.strip():
        term=f"%{q.strip()}%"; filters.append(or_(Order.order_no.ilike(term), Customer.company_name.ilike(term), Customer.contact_name.ilike(term)))
    if customer_id:
        filters.append(Order.customer_id == customer_id)
    if start: filters.append(Order.order_date >= start)
    if end: filters.append(Order.order_date <= end)
    for col,value in ((Order.payment_status,payment_status),(Order.production_status,production_status),(Order.shipping_status,shipping_status)):
        if value is not None: filters.append(col==value)
    base=select(Order).join(Customer).outerjoin(Opportunity).where(*filters)
    total=session.scalar(select(func.count(Order.id)).select_from(Order).join(Customer).outerjoin(Opportunity).where(*filters)) or 0
    rows=list(session.scalars(base.order_by(Order.order_date.desc(),Order.id.desc()).limit(limit).offset(offset)))
    return [_serialize(session,row) for row in rows],total
def _validate_links(session: Session, payload, user: User):
    customer=session.get(Customer,payload.customer_id)
    if not customer: raise NotFoundError("Customer not found.")
    access_service.ensure_customer_manage_access(user,customer)
    if payload.opportunity_id:
        opportunity=session.get(Opportunity,payload.opportunity_id)
        if not opportunity or opportunity.customer_id!=customer.id: raise ConflictError("Opportunity must belong to the selected customer.")
        if user.role is UserRole.SALES and opportunity.owner_id != user.id: raise ForbiddenError("You may only use your own opportunity.")
        if session.scalar(select(Order.id).where(Order.opportunity_id == payload.opportunity_id)):
            raise ConflictError("This opportunity already has an order.")
    if payload.quotation_id:
        quotation=session.get(Quotation,payload.quotation_id)
        if not quotation or quotation.customer_id!=customer.id: raise ConflictError("Quotation must belong to the selected customer.")
        # Reuse the established quotation access rule as well as customer scope.
        # A Sales user may own a customer while a different Sales user owns the
        # quotation's opportunity, so customer access alone is not sufficient.
        from app.services.quotation_service import get_quotation_detail
        get_quotation_detail(session, payload.quotation_id, user)
        if payload.opportunity_id and quotation.opportunity_id not in (None,payload.opportunity_id): raise ConflictError("Quotation is linked to another opportunity.")
        if session.scalar(select(Order.id).where(Order.quotation_id==payload.quotation_id)): raise ConflictError("This quotation already has an order.")
    return customer


def get_order_for_opportunity(session: Session, opportunity_id: int) -> Order | None:
    """Return an existing order for an opportunity without creating another."""
    return session.scalar(
        select(Order)
        .where(Order.opportunity_id == opportunity_id)
        .order_by(Order.created_at.asc(), Order.id.asc())
        .limit(1)
    )


def get_order_for_quotation(session: Session, quotation_id: int) -> Order | None:
    return session.scalar(select(Order).where(Order.quotation_id == quotation_id))


def create_order_in_transaction(session: Session, payload: OrderCreate, user: User) -> Order:
    """Create an order using existing validation, leaving commit to the caller."""
    if user.role is UserRole.VIEWER:
        raise ForbiddenError("Viewer accounts have read-only access.")
    _validate_links(session, payload, user)
    if payload.opportunity_id is not None:
        # Serialise order creation for one opportunity.  PostgreSQL releases
        # this row lock on commit/rollback; the second concurrent request then
        # observes the first order and receives a controlled conflict.
        locked_opportunity = session.scalar(
            select(Opportunity)
            .where(Opportunity.id == payload.opportunity_id)
            .with_for_update()
        )
        if locked_opportunity is None:
            raise NotFoundError("Opportunity not found.")
        if session.scalar(select(Order.id).where(Order.opportunity_id == payload.opportunity_id)):
            raise ConflictError("This opportunity already has an order.")
    if session.scalar(select(Order.id).where(Order.order_no == payload.order_no.strip())):
        raise ConflictError("Order number already exists.")
    owner_id = user.id if user.role is UserRole.SALES else (payload.owner_id or user.id)
    if not session.get(User, owner_id):
        raise NotFoundError("Order owner not found.")
    # ``OrderCreate`` deliberately includes caller-supplied order_no and
    # owner_id.  Normalize/override those values in one mapping before
    # constructing the ORM object; passing both ``**payload`` and explicit
    # keyword arguments raises TypeError and previously made every automatic
    # or historical order creation fail before the transaction could commit.
    order_data = payload.model_dump()
    order_data["order_no"] = payload.order_no.strip()
    order_data["owner_id"] = owner_id
    order_data["created_by_id"] = user.id
    order = Order(**order_data)
    session.add(order)
    # Surface unique-constraint failures inside the caller's transaction so the
    # opportunity stage and order can be rolled back together.
    session.flush()
    return order


def create_order(session: Session,payload:OrderCreate,user:User)->OrderRead:
    try:
        order = create_order_in_transaction(session, payload, user)
        session.commit(); session.refresh(order)
    except IntegrityError as error:
        session.rollback()
        raise ConflictError("Order number already exists or this quotation already has an order.") from error
    return _serialize(session,order)
def get_order(session,user,order_id): return _serialize(session,_read(session,user,order_id))
def update_order(session,order_id,payload:OrderUpdate,user):
    if user.role is UserRole.VIEWER: raise ForbiddenError("Viewer accounts have read-only access.")
    order=_read(session,user,order_id); changes=payload.model_dump(exclude_unset=True)
    if "order_no" in changes:
        changes["order_no"]=changes["order_no"].strip(); existing=session.scalar(select(Order.id).where(Order.order_no==changes["order_no"],Order.id!=order.id));
        if existing: raise ConflictError("Order number already exists.")
    for field,value in changes.items(): setattr(order,field,value)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ConflictError("Order number already exists or this quotation already has an order.") from error
    return _serialize(session,order)
def delete_order(session,order_id,user):
    if user.role is not UserRole.ADMIN: raise ForbiddenError("Only Admin accounts can delete orders.")
    order=_read(session,user,order_id); session.delete(order); session.commit()
def quotation_order(session,user,quotation_id):
    order=session.scalar(select(Order).where(Order.quotation_id==quotation_id))
    return _serialize(session, _read(session, user, order.id)) if order else None
