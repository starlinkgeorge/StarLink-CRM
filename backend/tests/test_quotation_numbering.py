from datetime import date

from app.services.quotation_service import _daily_quotation_prefix, _next_daily_sequence


def test_daily_quotation_sequence_uses_the_highest_existing_suffix() -> None:
    quotation_date = date(2026, 8, 11)
    prefix = _daily_quotation_prefix(quotation_date)

    assert prefix == "SLQ-20260811-"
    assert (
        _next_daily_sequence(
            [
                "SLQ-20260810-99",
                "SLQ-20260811-1",
                "SLQ-20260811-3",
                "SLQ-20260811-000004",
                "SLQ-20260811-invalid",
            ],
            prefix,
        )
        == 5
    )


def test_daily_quotation_sequence_resets_for_a_new_date() -> None:
    previous_day_numbers = ["SLQ-20260811-1", "SLQ-20260811-2"]

    assert _next_daily_sequence(previous_day_numbers, "SLQ-20260812-") == 1
