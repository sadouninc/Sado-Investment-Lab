"""Focused regression tests for Margin Position Expiry Tracking PR1."""
from datetime import date

import pytest

from scripts.margin_expiry import (
    DataSource,
    DueStatus,
    ExitReason,
    ExpiryThresholds,
    MarginExpiryInput,
    MarginTerm,
    SourceFreshness,
    calculate_expiry_status,
)


def current_input(**kwargs):
    values = {
        "repayment_due_date": date(2026, 9, 17),
        "as_of": date(2026, 9, 4),
        "source_freshness": SourceFreshness.CURRENT,
    }
    values.update(kwargs)
    return MarginExpiryInput(**values)


def test_exact_due_date_is_deterministic_and_13_days_is_notice():
    result = calculate_expiry_status(current_input(security_code="7011"))
    assert result.days_to_due == 13
    # Default urgent_days is 7; 13 days is NOTICE, not URGENT.
    assert result.due_status == DueStatus.NOTICE
    assert result.is_active_alert is True
    assert result.active_alert_eligible is True
    assert result.authority == "INFORMATION_ONLY"


def test_due_today_is_due():
    result = calculate_expiry_status(current_input(
        repayment_due_date=date(2026, 9, 4),
    ))
    assert result.days_to_due == 0
    assert result.due_status == DueStatus.DUE
    assert result.is_active_alert is True


def test_past_due_is_overdue():
    result = calculate_expiry_status(current_input(
        repayment_due_date=date(2026, 9, 2),
    ))
    assert result.days_to_due == -2
    assert result.due_status == DueStatus.OVERDUE
    assert result.is_active_alert is True


def test_missing_due_date_fails_closed():
    result = calculate_expiry_status(current_input(repayment_due_date=None))
    assert result.days_to_due is None
    assert result.due_status == DueStatus.UNKNOWN
    assert result.active_alert_eligible is False
    assert result.is_active_alert is False


def test_open_date_and_six_month_term_do_not_synthesize_due_date():
    result = calculate_expiry_status(current_input(
        repayment_due_date=None,
        open_date=date(2026, 3, 3),
        margin_term=MarginTerm.SIX_MONTH,
    ))
    assert result.days_to_due is None
    assert result.due_status == DueStatus.UNKNOWN


def test_closed_position_never_emits_active_alert():
    result = calculate_expiry_status(current_input(
        repayment_due_date=date(2026, 9, 4),
        is_closed=True,
    ))
    assert result.due_status == DueStatus.DUE
    assert result.active_alert_eligible is False
    assert result.is_active_alert is False


def test_stale_source_with_exact_due_date_fails_closed_for_alerting():
    result = calculate_expiry_status(MarginExpiryInput(
        repayment_due_date=date(2026, 9, 5),
        as_of=date(2026, 9, 4),
        source=DataSource.SBI_CSV,
        source_as_of=date(2026, 8, 31),
        source_freshness=SourceFreshness.STALE,
    ))
    # Due-date arithmetic remains factual, but stale source cannot be CURRENT.
    assert result.days_to_due == 1
    assert result.due_status == DueStatus.URGENT
    assert result.source_freshness == SourceFreshness.STALE
    assert result.active_alert_eligible is False
    assert result.is_active_alert is False


def test_unknown_source_freshness_with_exact_due_date_fails_closed_for_alerting():
    result = calculate_expiry_status(MarginExpiryInput(
        repayment_due_date=date(2026, 9, 5),
        as_of=date(2026, 9, 4),
        source=DataSource.BROKER_EXPORT,
        source_as_of=date(2026, 9, 4),
        # Default is UNKNOWN; the domain model does not infer freshness.
    ))
    assert result.days_to_due == 1
    assert result.due_status == DueStatus.URGENT
    assert result.source_freshness == SourceFreshness.UNKNOWN
    assert result.active_alert_eligible is False
    assert result.is_active_alert is False


def test_current_source_is_machine_readable_and_alert_eligible():
    result = calculate_expiry_status(current_input(
        repayment_due_date=date(2026, 9, 5),
        source=DataSource.MANUAL_VERIFIED,
        source_as_of=date(2026, 9, 4),
    ))
    assert result.source_freshness == SourceFreshness.CURRENT
    assert result.active_alert_eligible is True
    assert result.is_active_alert is True


def test_same_security_multiple_positions_are_independent():
    first = calculate_expiry_status(current_input(
        repayment_due_date=date(2026, 11, 5),
        security_code="7011",
        position_id="7011-a",
    ))
    second = calculate_expiry_status(current_input(
        repayment_due_date=date(2026, 11, 25),
        security_code="7011",
        position_id="7011-b",
    ))
    assert (first.position_id, first.days_to_due) == ("7011-a", 62)
    assert (second.position_id, second.days_to_due) == ("7011-b", 82)


def test_exit_reason_distinguishes_expiry_from_discretionary_sell():
    assert ExitReason.MARGIN_EXPIRY.value == "MARGIN_EXPIRY"
    assert ExitReason.DISCRETIONARY_SELL.value == "DISCRETIONARY_SELL"
    assert ExitReason.MARGIN_EXPIRY != ExitReason.DISCRETIONARY_SELL


def test_default_and_custom_thresholds():
    notice = calculate_expiry_status(current_input(
        repayment_due_date=date(2026, 10, 4),
    ))
    urgent = calculate_expiry_status(current_input(
        repayment_due_date=date(2026, 9, 11),
    ))
    assert notice.days_to_due == 30 and notice.due_status == DueStatus.NOTICE
    assert urgent.days_to_due == 7 and urgent.due_status == DueStatus.URGENT

    custom = ExpiryThresholds(notice_days=14, urgent_days=3)
    custom_notice = calculate_expiry_status(
        current_input(repayment_due_date=date(2026, 9, 18)), custom
    )
    assert custom_notice.days_to_due == 14
    assert custom_notice.due_status == DueStatus.NOTICE


def test_invalid_thresholds_fail_closed():
    with pytest.raises(ValueError, match="notice_days.*must be >= urgent_days"):
        ExpiryThresholds(notice_days=5, urgent_days=10)
    with pytest.raises(ValueError, match="urgent_days.*must be >= 0"):
        ExpiryThresholds(notice_days=10, urgent_days=-1)


def test_metadata_is_preserved():
    result = calculate_expiry_status(current_input(
        position_id="pos-123",
        security_code="7011",
        margin_term=MarginTerm.SIX_MONTH,
        source=DataSource.SBI_CSV,
        source_as_of=date(2026, 9, 4),
    ))
    assert result.position_id == "pos-123"
    assert result.security_code == "7011"
    assert result.margin_term == MarginTerm.SIX_MONTH
    assert result.source == DataSource.SBI_CSV
    assert result.source_as_of == date(2026, 9, 4)
    assert result.source_freshness == SourceFreshness.CURRENT
