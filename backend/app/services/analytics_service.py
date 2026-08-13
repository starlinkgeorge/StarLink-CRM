"""Database-side, read-only business analytics for StarLink CRM.

This module deliberately aggregates data in PostgreSQL/SQLAlchemy instead of
returning customer, quotation, or follow-up records to the browser for
JavaScript-side counting.  It has no writes and therefore needs no migration.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
import re
from typing import Iterable

from sqlalchemy import Date, and_, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.followup import FollowUp
from app.models.lead import Opportunity, OpportunityDealStage, OpportunityDealStageHistory
from app.models.quotation import Quotation, QuotationItem, QuotationVersion
from app.models.user import User, UserRole
from app.schemas.analytics import AnalyticsPeriod
from app.services.access_service import customer_scope
from app.services.customer_followup_stage_service import (
    MANUAL_FOLLOWUP_STAGES,
    normalize_manual_followup_stage,
)
from app.services.followup_reminder_service import list_customer_followup_reminders, shanghai_today


OTHER_HISTORICAL_STAGE = "Other historical stage"
UNSET_VALUE = "Not configured"


@dataclass(frozen=True)
class DateRange:
    start_date: date
    end_date: date
    comparison_start_date: date
    comparison_end_date: date
    label: str
    granularity: str


def _period_range(
    period: AnalyticsPeriod,
    start_date: date | None,
    end_date: date | None,
    *,
    today: date | None = None,
) -> DateRange:
    current_day = today or shanghai_today()
    if period is AnalyticsPeriod.TODAY:
        start = end = current_day
        label = current_day.isoformat()
        granularity = "day"
    elif period is AnalyticsPeriod.WEEK:
        start = current_day - timedelta(days=current_day.weekday())
        end = current_day
        label = f"{start.isoformat()} to {end.isoformat()}"
        granularity = "day"
    elif period is AnalyticsPeriod.MONTH:
        start = current_day.replace(day=1)
        end = current_day
        label = f"{current_day:%Y-%m}"
        granularity = "day"
    elif period is AnalyticsPeriod.YEAR:
        start = current_day.replace(month=1, day=1)
        end = current_day
        label = str(current_day.year)
        granularity = "month"
    else:
        if start_date is None or end_date is None:
            raise ValueError("Custom analytics requires both start_date and end_date.")
        if start_date > end_date:
            raise ValueError("start_date must not be after end_date.")
        start, end = start_date, end_date
        label = f"{start.isoformat()} to {end.isoformat()}"
        granularity = "month" if (end - start).days > 90 else "day"

    length = (end - start).days + 1
    comparison_end = start - timedelta(days=1)
    comparison_start = comparison_end - timedelta(days=length - 1)
    return DateRange(
        start_date=start,
        end_date=end,
        comparison_start_date=comparison_start,
        comparison_end_date=comparison_end,
        label=label,
        granularity=granularity,
    )


def _timestamp_date(session: Session, column):
    """Translate a timestamp to a Shanghai business date on PostgreSQL.

    SQLite is used by tests and stores timestamps without time-zone operations;
    its ``date`` function is the closest compatible behaviour there.
    """
    if session.get_bind().dialect.name == "postgresql":
        return cast(func.timezone("Asia/Shanghai", column), Date)
    return func.date(column)


def _date_between(column, start: date, end: date):
    return and_(column >= start, column <= end)


def _timestamp_between(session: Session, column, start: date, end: date):
    return _date_between(_timestamp_date(session, column), start, end)


def _customer_filters(user: User) -> list:
    scope = customer_scope(user)
    return [scope] if scope is not None else []


def _opportunity_filters(user: User) -> list:
    return [Opportunity.owner_id == user.id] if user.role is UserRole.SALES else []


def _quotation_filters(user: User) -> list:
    if user.role is not UserRole.SALES:
        return []
    # Quotation access follows the same ownership rule as quotation_service:
    # opportunity owner when linked, otherwise the owning customer.
    return [
        or_(
            and_(Quotation.opportunity_id.is_(None), Customer.owner_id == user.id),
            Opportunity.owner_id == user.id,
        )
    ]


def _as_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _bucket_key(value: date, granularity: str) -> str:
    return value.strftime("%Y-%m") if granularity == "month" else value.isoformat()


def _bucket_dates(date_range: DateRange) -> list[str]:
    if date_range.granularity == "day":
        return [
            (date_range.start_date + timedelta(days=offset)).isoformat()
            for offset in range((date_range.end_date - date_range.start_date).days + 1)
        ]
    cursor = date_range.start_date.replace(day=1)
    result: list[str] = []
    while cursor <= date_range.end_date:
        result.append(cursor.strftime("%Y-%m"))
        cursor = (
            cursor.replace(year=cursor.year + 1, month=1)
            if cursor.month == 12
            else cursor.replace(month=cursor.month + 1)
        )
    return result


def _percentage_change(current: int, previous: int) -> float | None:
    if previous == 0:
        return 0.0 if current == 0 else None
    return round((current - previous) / previous * 100, 1)


def _currency_amounts(rows: Iterable[tuple[str, Decimal]]) -> list[dict[str, object]]:
    return [
        {"currency": currency or "USD", "amount": amount or Decimal("0.00")}
        for currency, amount in rows
    ]


def _current_quotation_join(statement):
    return statement.join(Customer).outerjoin(Opportunity).join(
        QuotationVersion,
        and_(
            QuotationVersion.quotation_id == Quotation.id,
            QuotationVersion.version_no == Quotation.current_version,
        ),
    )


def _quote_count(session: Session, user: User, start: date, end: date) -> int:
    statement = _current_quotation_join(
        select(func.count(func.distinct(Quotation.quotation_number))).select_from(Quotation)
    ).where(
        _timestamp_between(session, Quotation.created_at, start, end),
        *_quotation_filters(user),
    )
    return session.scalar(statement) or 0


def _quote_amounts(session: Session, user: User, start: date, end: date) -> list[dict[str, object]]:
    statement = _current_quotation_join(
        select(QuotationVersion.currency, func.coalesce(func.sum(QuotationVersion.total_amount), 0))
        .select_from(Quotation)
    ).where(
        _timestamp_between(session, Quotation.created_at, start, end),
        *_quotation_filters(user),
    ).group_by(QuotationVersion.currency).order_by(QuotationVersion.currency.asc())
    return _currency_amounts(session.execute(statement).all())


def _won_at_subquery():
    """The first recorded transition into Won is the only real won timestamp."""
    return (
        select(
            OpportunityDealStageHistory.opportunity_id.label("opportunity_id"),
            func.min(OpportunityDealStageHistory.created_at).label("won_at"),
        )
        .where(OpportunityDealStageHistory.new_deal_stage == OpportunityDealStage.WON.value)
        .group_by(OpportunityDealStageHistory.opportunity_id)
        .subquery()
    )


def _won_count(session: Session, user: User, start: date, end: date) -> int:
    won_at = _won_at_subquery()
    statement = select(func.count(Opportunity.id)).join(
        won_at, won_at.c.opportunity_id == Opportunity.id
    ).where(
        _timestamp_between(session, won_at.c.won_at, start, end),
        *_opportunity_filters(user),
    )
    return session.scalar(statement) or 0


def _won_amounts(session: Session, user: User, start: date, end: date) -> list[dict[str, object]]:
    """Use the latest quotation's final amount when no actual deal amount exists."""
    won_at = _won_at_subquery()
    latest_quotation_id = (
        select(Quotation.id)
        .where(Quotation.opportunity_id == Opportunity.id)
        .order_by(Quotation.updated_at.desc(), Quotation.id.desc())
        .limit(1)
        .correlate(Opportunity)
        .scalar_subquery()
    )
    statement = (
        select(QuotationVersion.currency, func.coalesce(func.sum(QuotationVersion.total_amount), 0))
        .select_from(Opportunity)
        .join(won_at, won_at.c.opportunity_id == Opportunity.id)
        .join(Quotation, Quotation.id == latest_quotation_id)
        .join(
            QuotationVersion,
            and_(
                QuotationVersion.quotation_id == Quotation.id,
                QuotationVersion.version_no == Quotation.current_version,
            ),
        )
        .where(
            _timestamp_between(session, won_at.c.won_at, start, end),
            *_opportunity_filters(user),
        )
        .group_by(QuotationVersion.currency)
        .order_by(QuotationVersion.currency.asc())
    )
    return _currency_amounts(session.execute(statement).all())


def _quoted_opportunity_count(session: Session, user: User, start: date, end: date) -> int:
    statement = _current_quotation_join(
        select(func.count(func.distinct(Quotation.opportunity_id))).select_from(Quotation)
    ).where(
        Quotation.opportunity_id.is_not(None),
        _timestamp_between(session, Quotation.created_at, start, end),
        *_quotation_filters(user),
    )
    return session.scalar(statement) or 0


def _customer_count(session: Session, user: User, start: date, end: date) -> int:
    return session.scalar(
        select(func.count(Customer.id)).where(
            Customer.customer_acquired_at.is_not(None),
            _date_between(Customer.customer_acquired_at, start, end),
            *_customer_filters(user),
        )
    ) or 0


def _customer_breakdown(session: Session, user: User, column, date_range: DateRange, *, limit: int | None = None) -> list[dict[str, object]]:
    rows = session.execute(
        select(column, func.count(Customer.id))
        .where(
            Customer.customer_acquired_at.is_not(None),
            _date_between(Customer.customer_acquired_at, date_range.start_date, date_range.end_date),
            *_customer_filters(user),
        )
        .group_by(column)
        .order_by(func.count(Customer.id).desc(), column.asc().nulls_last())
    ).all()
    total = sum(count for _, count in rows)
    if limit is not None:
        rows = rows[:limit]
    return [
        {
            "value": str(value).strip() if value is not None and str(value).strip() else UNSET_VALUE,
            "count": count,
            "percentage": round(count / total * 100, 1) if total else 0.0,
        }
        for value, count in rows
    ]


def _split_interested_products(value: str) -> list[str]:
    """Split the archive's multi-select strings without breaking English names."""
    pieces = re.split(r"[,\uFF0C\u3001;/\uFF1B|\n]+", value)
    result: list[str] = []
    for piece in pieces:
        text = piece.strip()
        # The source archive uses Chinese category values. A whitespace-separated
        # sequence of Chinese labels is a multi-select, while English product
        # names such as "Pink Tower" remain a single value.
        if re.fullmatch(r"[\u4e00-\u9fff]+(?:\s+[\u4e00-\u9fff]+)+", text):
            result.extend(part for part in text.split() if part)
        elif text:
            result.append(text)
    return result


def _interested_product_breakdown(session: Session, user: User, date_range: DateRange) -> list[dict[str, object]]:
    rows = session.execute(
        select(Customer.interested_product, func.count(Customer.id))
        .where(
            Customer.customer_acquired_at.is_not(None),
            _date_between(Customer.customer_acquired_at, date_range.start_date, date_range.end_date),
            *_customer_filters(user),
        )
        .group_by(Customer.interested_product)
    ).all()
    counts: dict[str, int] = defaultdict(int)
    for value, count in rows:
        if value is None or not str(value).strip():
            counts[UNSET_VALUE] += count
            continue
        values = _split_interested_products(str(value))
        for item in values or [UNSET_VALUE]:
            counts[item] += count
    total = sum(counts.values())
    return [
        {"value": value, "count": count, "percentage": round(count / total * 100, 1) if total else 0.0}
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _quoted_products(session: Session, user: User, date_range: DateRange) -> list[dict[str, object]]:
    statement = _current_quotation_join(
        select(
            QuotationItem.sku_snapshot,
            QuotationItem.product_name_snapshot,
            QuotationVersion.currency,
            func.count(func.distinct(Quotation.id)),
            func.coalesce(func.sum(QuotationItem.quantity), 0),
            func.coalesce(func.sum(QuotationItem.line_total), 0),
        ).select_from(Quotation)
    ).join(QuotationItem, QuotationItem.quotation_version_id == QuotationVersion.id).where(
        _timestamp_between(session, Quotation.created_at, date_range.start_date, date_range.end_date),
        *_quotation_filters(user),
    ).group_by(
        QuotationItem.sku_snapshot,
        QuotationItem.product_name_snapshot,
        QuotationVersion.currency,
    )
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for sku, name, currency, quotation_count, quantity, amount in session.execute(statement):
        key = (sku, name)
        item = grouped.setdefault(
            key,
            {
                "sku": sku,
                "product_name": name,
                "quotation_count": 0,
                "total_quantity": Decimal("0"),
                "amounts": defaultdict(lambda: Decimal("0")),
            },
        )
        item["quotation_count"] = int(item["quotation_count"]) + quotation_count
        item["total_quantity"] = Decimal(item["total_quantity"]) + quantity
        item["amounts"][currency] += amount
    result = []
    for item in sorted(grouped.values(), key=lambda current: (-int(current["quotation_count"]), str(current["sku"])))[:10]:
        amounts = item.pop("amounts")
        result.append(
            {
                **item,
                "quotation_amounts": _currency_amounts(sorted(amounts.items())),
            }
        )
    return result


def _sales_funnel(session: Session, user: User) -> list[dict[str, object]]:
    rows = session.execute(
        select(Customer.followup_stage, func.count(Customer.id))
        .where(*_customer_filters(user))
        .group_by(Customer.followup_stage)
    ).all()
    counts: dict[str, int] = {stage: 0 for stage in MANUAL_FOLLOWUP_STAGES}
    counts[OTHER_HISTORICAL_STAGE] = 0
    counts[UNSET_VALUE] = 0
    for stored_value, count in rows:
        if stored_value is None or not str(stored_value).strip():
            counts[UNSET_VALUE] += count
            continue
        normalized = normalize_manual_followup_stage(str(stored_value))
        if normalized in MANUAL_FOLLOWUP_STAGES:
            counts[normalized] += count
        else:
            counts[OTHER_HISTORICAL_STAGE] += count
    order = [*MANUAL_FOLLOWUP_STAGES, OTHER_HISTORICAL_STAGE, UNSET_VALUE]
    return [{"stage": stage, "count": counts[stage]} for stage in order]


def _trend_counts(session: Session, user: User, date_range: DateRange) -> list[dict[str, object]]:
    customer_rows = session.execute(
        select(Customer.customer_acquired_at, func.count(Customer.id))
        .where(
            Customer.customer_acquired_at.is_not(None),
            _date_between(Customer.customer_acquired_at, date_range.start_date, date_range.end_date),
            *_customer_filters(user),
        )
        .group_by(Customer.customer_acquired_at)
    ).all()
    quote_day = _timestamp_date(session, Quotation.created_at)
    quote_rows = session.execute(
        _current_quotation_join(
            select(quote_day, func.count(func.distinct(Quotation.quotation_number))).select_from(Quotation)
        ).where(
            _date_between(quote_day, date_range.start_date, date_range.end_date),
            *_quotation_filters(user),
        ).group_by(quote_day)
    ).all()
    won_at = _won_at_subquery()
    won_day = _timestamp_date(session, won_at.c.won_at)
    won_rows = session.execute(
        select(won_day, func.count(Opportunity.id))
        .select_from(Opportunity)
        .join(won_at, won_at.c.opportunity_id == Opportunity.id)
        .where(
            _date_between(won_day, date_range.start_date, date_range.end_date),
            *_opportunity_filters(user),
        )
        .group_by(won_day)
    ).all()
    values = {
        "customer": defaultdict(int),
        "quotation": defaultdict(int),
        "won": defaultdict(int),
    }
    for key, count in customer_rows:
        values["customer"][_bucket_key(_as_date(key), date_range.granularity)] += count
    for key, count in quote_rows:
        values["quotation"][_bucket_key(_as_date(key), date_range.granularity)] += count
    for key, count in won_rows:
        values["won"][_bucket_key(_as_date(key), date_range.granularity)] += count
    return [
        {
            "bucket": bucket,
            "new_customer_count": values["customer"][bucket],
            "quotation_count": values["quotation"][bucket],
            "won_opportunity_count": values["won"][bucket],
        }
        for bucket in _bucket_dates(date_range)
    ]


def get_business_analytics(
    session: Session,
    user: User,
    *,
    period: AnalyticsPeriod,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, object]:
    """Return all business-analysis aggregates in one read-only request."""
    date_range = _period_range(period, start_date, end_date)
    current_customers = _customer_count(session, user, date_range.start_date, date_range.end_date)
    previous_customers = _customer_count(
        session, user, date_range.comparison_start_date, date_range.comparison_end_date
    )
    current_quotes = _quote_count(session, user, date_range.start_date, date_range.end_date)
    previous_quotes = _quote_count(
        session, user, date_range.comparison_start_date, date_range.comparison_end_date
    )
    current_won = _won_count(session, user, date_range.start_date, date_range.end_date)
    previous_won = _won_count(
        session, user, date_range.comparison_start_date, date_range.comparison_end_date
    )
    quoted_opportunities = _quoted_opportunity_count(
        session, user, date_range.start_date, date_range.end_date
    )
    followup_summary, _ = list_customer_followup_reminders(session, user)
    followup_count = session.scalar(
        select(func.count(FollowUp.id))
        .join(Customer)
        .where(
            _date_between(FollowUp.followup_date, date_range.start_date, date_range.end_date),
            *_customer_filters(user),
        )
    ) or 0
    return {
        "period": period,
        "date_range": {
            "start_date": date_range.start_date,
            "end_date": date_range.end_date,
            "comparison_start_date": date_range.comparison_start_date,
            "comparison_end_date": date_range.comparison_end_date,
            "label": date_range.label,
        },
        "kpis": {
            "new_customer_count": current_customers,
            "new_customer_change_percent": _percentage_change(current_customers, previous_customers),
            "quotation_count": current_quotes,
            "quotation_count_change_percent": _percentage_change(current_quotes, previous_quotes),
            "quotation_amounts": _quote_amounts(session, user, date_range.start_date, date_range.end_date),
            "previous_quotation_amounts": _quote_amounts(
                session, user, date_range.comparison_start_date, date_range.comparison_end_date
            ),
            "won_opportunity_count": current_won,
            "won_opportunity_change_percent": _percentage_change(current_won, previous_won),
            "won_amounts": _won_amounts(session, user, date_range.start_date, date_range.end_date),
            "previous_won_amounts": _won_amounts(
                session, user, date_range.comparison_start_date, date_range.comparison_end_date
            ),
            "quoted_opportunity_count": quoted_opportunities,
            "quote_to_win_rate": round(current_won / quoted_opportunities * 100, 1)
            if quoted_opportunities
            else None,
        },
        "trend": _trend_counts(session, user, date_range),
        "source_analysis": _customer_breakdown(session, user, Customer.source, date_range),
        "country_analysis": _customer_breakdown(
            session, user, Customer.country, date_range, limit=10
        ),
        "interested_product_analysis": _interested_product_breakdown(session, user, date_range),
        "customer_type_analysis": _customer_breakdown(
            session, user, Customer.customer_type, date_range
        ),
        "quoted_products": _quoted_products(session, user, date_range),
        "sales_funnel": _sales_funnel(session, user),
        "followup_summary": {
            "created_followup_count": followup_count,
            "overdue_count": followup_summary["overdue_count"],
            "today_count": followup_summary["today_count"],
            "upcoming_count": followup_summary["upcoming_count"],
            "unfollowed_count": followup_summary["unfollowed_count"],
        },
    }
