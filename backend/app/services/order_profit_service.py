"""Read-only, Admin-only profit analysis for the existing order ledger."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.order import Order
from app.models.user import User, UserRole
from app.schemas.order import (
    OrderProfitAnalytics,
    OrderProfitCurrencyAmount,
    OrderProfitCustomerRank,
    OrderProfitPeriod,
    OrderProfitSummary,
    OrderProfitTrendPoint,
)
from app.services.errors import ForbiddenError
from app.services.followup_reminder_service import shanghai_today


ZERO = Decimal("0.00")


def _decimal(value: object | None) -> Decimal:
    return Decimal(str(value)) if value is not None else ZERO


def _subtract_months(value: date, months: int) -> date:
    absolute_month = value.year * 12 + value.month - 1 - months
    year, month_index = divmod(absolute_month, 12)
    month = month_index + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _next_month(value: date) -> date:
    return date(value.year + 1, 1, 1) if value.month == 12 else date(value.year, value.month + 1, 1)


def _period_dates(
    period: OrderProfitPeriod,
    start_date: date | None,
    end_date: date | None,
    today: date,
) -> tuple[date, date, str]:
    if period is OrderProfitPeriod.TODAY:
        return today, today, "今日利润"
    if period is OrderProfitPeriod.MONTH:
        return today.replace(day=1), today, "本月利润"
    if period is OrderProfitPeriod.QUARTER:
        quarter_start_month = ((today.month - 1) // 3) * 3 + 1
        return date(today.year, quarter_start_month, 1), today, "本季度利润"
    if period is OrderProfitPeriod.HALF_YEAR:
        return _subtract_months(today, 6), today, "近6个月利润"
    if period is OrderProfitPeriod.YEAR:
        return date(today.year, 1, 1), today, "本年度利润"
    if start_date is None or end_date is None:
        raise ValueError("自定义利润分析必须同时提供开始日期和结束日期。")
    if start_date > end_date:
        raise ValueError("开始日期不能晚于结束日期。")
    return start_date, end_date, "自定义时间利润"


def _accounted_condition():
    return and_(
        Order.rmb_received_amount.is_not(None),
        Order.purchase_cost.is_not(None),
        Order.freight_cost.is_not(None),
    )


def _filters(start_date: date, end_date: date) -> list:
    return [Order.order_date >= start_date, Order.order_date <= end_date]


def _currency_amounts(session: Session, filters: list) -> list[OrderProfitCurrencyAmount]:
    rows = session.execute(
        select(Order.currency, func.coalesce(func.sum(Order.order_amount), 0))
        .where(*filters)
        .group_by(Order.currency)
        .order_by(Order.currency)
    ).all()
    return [OrderProfitCurrencyAmount(currency=currency or "USD", amount=_decimal(amount)) for currency, amount in rows]


def _summary(session: Session, start_date: date, end_date: date, label: str) -> OrderProfitSummary:
    filters = _filters(start_date, end_date)
    accounted = _accounted_condition()
    profit_expression = Order.rmb_received_amount - Order.purchase_cost - Order.freight_cost
    row = session.execute(
        select(
            func.count(Order.id),
            func.coalesce(func.sum(case((accounted, 1), else_=0)), 0),
            func.coalesce(func.sum(case((accounted, Order.rmb_received_amount), else_=0)), 0),
            func.coalesce(func.sum(case((accounted, Order.purchase_cost), else_=0)), 0),
            func.coalesce(func.sum(case((accounted, Order.freight_cost), else_=0)), 0),
            func.coalesce(func.sum(case((accounted, profit_expression), else_=0)), 0),
        ).where(*filters)
    ).one()
    order_count = int(row[0] or 0)
    accounted_count = int(row[1] or 0)
    received, purchase, freight, profit = (_decimal(value) for value in row[2:])
    return OrderProfitSummary(
        label=label,
        start_date=start_date,
        end_date=end_date,
        order_count=order_count,
        accounted_order_count=accounted_count,
        pending_order_count=order_count - accounted_count,
        order_amounts=_currency_amounts(session, filters),
        rmb_received_total=received,
        purchase_cost_total=purchase,
        freight_cost_total=freight,
        profit_total=profit,
        profit_margin=(profit / received * Decimal("100")) if received else None,
    )


def _monthly_trend(session: Session, today: date) -> list[OrderProfitTrendPoint]:
    start_month = _subtract_months(_month_start(today), 11)
    accounted = _accounted_condition()
    profit_expression = Order.rmb_received_amount - Order.purchase_cost - Order.freight_cost
    year_expression = func.extract("year", Order.order_date)
    month_expression = func.extract("month", Order.order_date)
    # This is deliberately one grouped query, rather than one summary query per
    # month.  The twelve visual buckets are a fixed presentation concern, not a
    # reason to make database round-trips proportional to them.
    rows = session.execute(
        select(
            year_expression,
            month_expression,
            func.count(Order.id),
            func.coalesce(func.sum(case((accounted, 1), else_=0)), 0),
            func.coalesce(func.sum(case((accounted, Order.rmb_received_amount), else_=0)), 0),
            func.coalesce(func.sum(case((accounted, profit_expression), else_=0)), 0),
        )
        .where(Order.order_date >= start_month, Order.order_date <= today)
        .group_by(year_expression, month_expression)
    ).all()
    by_month = {
        (int(year), int(month)): (int(count or 0), int(accounted_count or 0), _decimal(received), _decimal(profit))
        for year, month, count, accounted_count, received, profit in rows
    }
    result: list[OrderProfitTrendPoint] = []
    cursor = start_month
    while cursor <= _month_start(today):
        count, accounted_count, received, profit = by_month.get(
            (cursor.year, cursor.month), (0, 0, ZERO, ZERO)
        )
        result.append(OrderProfitTrendPoint(
            month=cursor.strftime("%Y-%m"),
            order_count=count,
            accounted_order_count=accounted_count,
            pending_order_count=count - accounted_count,
            rmb_received_total=received,
            profit_total=profit,
        ))
        cursor = _next_month(cursor)
    return result


def _customer_ranking(session: Session, start_date: date, end_date: date) -> list[OrderProfitCustomerRank]:
    filters = _filters(start_date, end_date)
    accounted = _accounted_condition()
    profit_expression = Order.rmb_received_amount - Order.purchase_cost - Order.freight_cost
    rows = session.execute(
        select(
            Customer.id,
            Customer.company_name,
            Customer.contact_name,
            func.count(Order.id),
            func.coalesce(func.sum(case((accounted, 1), else_=0)), 0),
            func.coalesce(func.sum(case((accounted, Order.rmb_received_amount), else_=0)), 0),
            func.coalesce(func.sum(case((accounted, profit_expression), else_=0)), 0),
        )
        .select_from(Order)
        .join(Customer)
        .where(*filters)
        .group_by(Customer.id, Customer.company_name, Customer.contact_name)
        .order_by(func.coalesce(func.sum(case((accounted, profit_expression), else_=0)), 0).desc(), Customer.id.asc())
        .limit(10)
    ).all()
    total_profit = _summary(session, start_date, end_date, "").profit_total
    ranking: list[OrderProfitCustomerRank] = []
    for customer_id, company_name, contact_name, order_count, accounted_count, received, profit in rows:
        value = _decimal(profit)
        ranking.append(OrderProfitCustomerRank(
            customer_id=customer_id,
            customer_company=company_name or contact_name or "—",
            order_count=int(order_count or 0),
            accounted_order_count=int(accounted_count or 0),
            pending_order_count=int(order_count or 0) - int(accounted_count or 0),
            rmb_received_total=_decimal(received),
            profit_total=value,
            profit_contribution_percent=(value / total_profit * Decimal("100")) if total_profit else None,
        ))
    return ranking


def get_profit_analytics(
    session: Session,
    user: User,
    period: OrderProfitPeriod,
    start_date: date | None,
    end_date: date | None,
) -> OrderProfitAnalytics:
    if user.role is not UserRole.ADMIN:
        raise ForbiddenError("Only Admin accounts can access company profit analysis.")
    today = shanghai_today()
    selected_start, selected_end, selected_label = _period_dates(period, start_date, end_date, today)
    card_periods = (
        OrderProfitPeriod.TODAY,
        OrderProfitPeriod.MONTH,
        OrderProfitPeriod.QUARTER,
        OrderProfitPeriod.HALF_YEAR,
        OrderProfitPeriod.YEAR,
    )
    summaries = [
        _summary(session, *_period_dates(card_period, None, None, today))
        for card_period in card_periods
    ]
    return OrderProfitAnalytics(
        period=period,
        selected_summary=_summary(session, selected_start, selected_end, selected_label),
        period_summaries=summaries,
        monthly_trend=_monthly_trend(session, today),
        customer_ranking=_customer_ranking(session, selected_start, selected_end),
    )
