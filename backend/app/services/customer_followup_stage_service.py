"""Shared customer follow-up-stage and automatic-stage rules.

Manual follow-up stages are deliberately kept separate from the dynamic
``automatic_stage_judgement`` value.  In particular, ``冷客户`` is not a
selectable manual stage: it is calculated from the China business day.
"""

from __future__ import annotations

from datetime import date


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


def normalize_manual_followup_stage(value: str | None) -> str | None:
    """Return a compatible manual stage without converting ``冷客户``."""
    if value is None:
        return None
    stage = value.strip()
    if not stage:
        return None
    return LEGACY_FOLLOWUP_STAGE_RENAMES.get(stage, stage)


def calculate_automatic_stage_judgement(
    latest_followup_date: date | None,
    stored_value: str | None,
    *,
    today: date | None = None,
) -> str | None:
    """Keep the archive's automatic judgement independent from cold status.

    Cold customers are now represented by ``Customer.is_cold_customer`` and
    are calculated from the acquisition date plus manual follow-up stage.  Do
    not overwrite a historical automatic-stage value based on a stale follow-up
    date.
    """
    return stored_value
