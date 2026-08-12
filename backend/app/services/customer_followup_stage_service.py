"""Shared customer follow-up-stage and automatic-stage rules.

Manual follow-up stages are deliberately kept separate from the dynamic
``automatic_stage_judgement`` value.  In particular, ``冷客户`` is not a
selectable manual stage: it is calculated from the China business day.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

CHINA_TIMEZONE = ZoneInfo("Asia/Shanghai")


MANUAL_FOLLOWUP_STAGES: tuple[str, ...] = (
    "新客户未回复",
    "沟通中",
    "已报价",
    "已成交样品",
    "已成交",
    "已复购",
)

# These are historical values which can be mapped without guessing the user's
# intended commercial state.  ``冷客户`` is intentionally excluded.
LEGACY_FOLLOWUP_STAGE_RENAMES: dict[str, str] = {
    "新开发未回复": "新客户未回复",
    "新开发已回复": "沟通中",
    "已采购样品": "已成交样品",
}

COLD_CUSTOMER_STAGE = "冷客户"
COLD_CUSTOMER_AFTER_DAYS = 30


def normalize_manual_followup_stage(value: str | None) -> str | None:
    """Return a compatible manual stage without converting ``冷客户``."""
    if value is None:
        return None
    stage = value.strip()
    if not stage:
        return None
    return LEGACY_FOLLOWUP_STAGE_RENAMES.get(stage, stage)


def cold_customer_cutoff_date(*, today: date | None = None) -> date:
    """Dates strictly before this value are more than 30 days old."""
    current_day = today or datetime.now(CHINA_TIMEZONE).date()
    return current_day - timedelta(days=COLD_CUSTOMER_AFTER_DAYS)


def calculate_automatic_stage_judgement(
    latest_followup_date: date | None,
    stored_value: str | None,
    *,
    today: date | None = None,
) -> str | None:
    """Overlay the live cold-customer rule without overwriting stored data."""
    if (
        latest_followup_date is not None
        and latest_followup_date < cold_customer_cutoff_date(today=today)
    ):
        return COLD_CUSTOMER_STAGE
    return stored_value
