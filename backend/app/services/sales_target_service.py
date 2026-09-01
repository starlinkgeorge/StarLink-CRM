from calendar import isleap
from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.opportunity import Opportunity, OpportunityDealStage
from app.models.order import Order
from app.models.sales_goal import AnnualSalesTarget, OtherSalesAmount
from app.models.user import User, UserRole
from app.schemas.sales_goal import AnnualSalesTargetRead, AnnualSalesTargetUpdate, OtherSalesAmountInput, OtherSalesAmountRead, SalesCurrencyBreakdown, SalesTargetAnalysis, SalesTargetPeriod, SalesTargetProgress
from app.services.errors import ForbiddenError, NotFoundError
from app.services.followup_reminder_service import shanghai_today
from app.services.system_settings_service import get_quotation_order_defaults

ZERO = Decimal("0.00")

def _ensure_writable(user: User) -> None:
    if user.role is UserRole.VIEWER:
        raise ForbiddenError("Viewer accounts have read-only access.")

def _scope(user: User):
    if user.role is UserRole.SALES:
        return or_(Order.owner_id == user.id, Customer.owner_id == user.id, Opportunity.owner_id == user.id)
    return None

def _periods(today: date) -> list[tuple[str, str, date, date, Decimal]]:
    quarter_month = ((today.month - 1) // 3) * 3 + 1
    half_month = 1 if today.month <= 6 else 7
    return [
        ("month", "本月", today.replace(day=1), today, Decimal("12")),
        ("quarter", "本季度", date(today.year, quarter_month, 1), today, Decimal("4")),
        ("half_year", "本半年", date(today.year, half_month, 1), today, Decimal("2")),
        ("year", "本年度", date(today.year, 1, 1), today, Decimal("1")),
    ]

def _currency_totals(session: Session, user: User, start: date, end: date) -> dict[str, tuple[Decimal, Decimal]]:
    order_filters = [Order.order_date >= start, Order.order_date <= end, or_(Order.opportunity_id.is_(None), Opportunity.deal_stage == OpportunityDealStage.WON.value)]
    scope = _scope(user)
    if scope is not None:
        order_filters.append(scope)
    order_rows = session.execute(select(Order.currency, func.coalesce(func.sum(Order.order_amount), 0)).select_from(Order).join(Customer).outerjoin(Opportunity).where(*order_filters).group_by(Order.currency)).all()
    manual_rows = session.execute(select(OtherSalesAmount.currency, func.coalesce(func.sum(OtherSalesAmount.amount), 0)).where(OtherSalesAmount.user_id == user.id, OtherSalesAmount.sale_date >= start, OtherSalesAmount.sale_date <= end).group_by(OtherSalesAmount.currency)).all()
    values: dict[str, list[Decimal]] = {}
    for currency, amount in order_rows:
        values.setdefault(currency or "USD", [ZERO, ZERO])[0] = Decimal(str(amount or 0))
    for currency, amount in manual_rows:
        values.setdefault(currency or "USD", [ZERO, ZERO])[1] = Decimal(str(amount or 0))
    return {currency: (items[0], items[1]) for currency, items in values.items()}

def _target(session: Session, user: User, year: int) -> AnnualSalesTarget | None:
    return session.scalar(select(AnnualSalesTarget).where(AnnualSalesTarget.user_id == user.id, AnnualSalesTarget.target_year == year))

def get_progress(session: Session, user: User) -> SalesTargetProgress:
    today = shanghai_today()
    target = _target(session, user, today.year)
    currency = target.currency if target else get_quotation_order_defaults(session).default_currency
    annual_amount = target.target_amount if target else ZERO
    annual_totals = _currency_totals(session, user, date(today.year, 1, 1), today)
    annual_crm, annual_manual = annual_totals.get(currency, (ZERO, ZERO))
    annual_actual = annual_crm + annual_manual
    cards: list[SalesTargetPeriod] = []
    for key, label, start, end, divisor in _periods(today):
        crm, manual = _currency_totals(session, user, start, end).get(currency, (ZERO, ZERO))
        actual = crm + manual
        period_target = annual_amount / divisor if target else ZERO
        cards.append(SalesTargetPeriod(key=key, label=label, actual_amount=actual, target_amount=period_target, completion_percent=(actual / period_target * Decimal("100")) if period_target else None, remaining_amount=max(ZERO, period_target - actual)))
    elapsed_days = today.timetuple().tm_yday
    total_days = 366 if isleap(today.year) else 365
    time_progress = Decimal(elapsed_days) / Decimal(total_days) * Decimal("100")
    expected = annual_amount * time_progress / Decimal("100") if target else ZERO
    pace = ((annual_actual - expected) / annual_amount * Decimal("100")) if annual_amount else None
    months_left = 13 - today.month
    breakdown = [SalesCurrencyBreakdown(currency=entry_currency, crm_order_amount=crm, manual_amount=manual, actual_amount=crm + manual) for entry_currency, (crm, manual) in sorted(annual_totals.items())]
    return SalesTargetProgress(year=today.year, currency=currency, annual_target=AnnualSalesTargetRead(target_year=target.target_year, currency=target.currency, target_amount=target.target_amount) if target else None, periods=cards, currency_breakdown=breakdown, annual_analysis=SalesTargetAnalysis(crm_order_amount=annual_crm, manual_amount=annual_manual, actual_total_amount=annual_actual, completion_percent=(annual_actual / annual_amount * Decimal("100")) if annual_amount else None, time_progress_percent=time_progress, pace_percent=pace, pace_label="领先计划" if pace is not None and pace >= 0 else "落后计划", remaining_amount=max(ZERO, annual_amount - annual_actual), monthly_required_amount=max(ZERO, annual_amount - annual_actual) / Decimal(months_left)))

def update_target(session: Session, user: User, year: int, payload: AnnualSalesTargetUpdate) -> AnnualSalesTargetRead:
    _ensure_writable(user)
    row = _target(session, user, year)
    currency = get_quotation_order_defaults(session).default_currency
    if row is None:
        row = AnnualSalesTarget(user_id=user.id, target_year=year, currency=currency, target_amount=payload.target_amount)
        session.add(row)
    else:
        row.currency = currency
        row.target_amount = payload.target_amount
    session.commit(); session.refresh(row)
    return AnnualSalesTargetRead(target_year=row.target_year, currency=row.currency, target_amount=row.target_amount)

def list_other_sales(session: Session, user: User, year: int) -> list[OtherSalesAmountRead]:
    rows = session.scalars(select(OtherSalesAmount).where(OtherSalesAmount.user_id == user.id, OtherSalesAmount.sale_date >= date(year, 1, 1), OtherSalesAmount.sale_date <= date(year, 12, 31)).order_by(OtherSalesAmount.sale_date.desc(), OtherSalesAmount.id.desc())).all()
    return [OtherSalesAmountRead(id=row.id, sale_date=row.sale_date, amount=row.amount, currency=row.currency, note=row.note, created_at=row.created_at) for row in rows]

def create_other_sale(session: Session, user: User, payload: OtherSalesAmountInput) -> OtherSalesAmountRead:
    _ensure_writable(user)
    row = OtherSalesAmount(user_id=user.id, **payload.model_dump())
    session.add(row); session.commit(); session.refresh(row)
    return OtherSalesAmountRead(id=row.id, sale_date=row.sale_date, amount=row.amount, currency=row.currency, note=row.note, created_at=row.created_at)

def update_other_sale(session: Session, user: User, entry_id: int, payload: OtherSalesAmountInput) -> OtherSalesAmountRead:
    _ensure_writable(user)
    row = session.scalar(select(OtherSalesAmount).where(OtherSalesAmount.id == entry_id, OtherSalesAmount.user_id == user.id))
    if row is None: raise NotFoundError("Other sales entry not found.")
    for key, value in payload.model_dump().items(): setattr(row, key, value)
    session.commit(); session.refresh(row)
    return OtherSalesAmountRead(id=row.id, sale_date=row.sale_date, amount=row.amount, currency=row.currency, note=row.note, created_at=row.created_at)

def delete_other_sale(session: Session, user: User, entry_id: int) -> None:
    _ensure_writable(user)
    row = session.scalar(select(OtherSalesAmount).where(OtherSalesAmount.id == entry_id, OtherSalesAmount.user_id == user.id))
    if row is None: raise NotFoundError("Other sales entry not found.")
    session.delete(row); session.commit()
