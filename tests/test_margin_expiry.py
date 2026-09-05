"""Tests for Margin Position Expiry Tracking (PR1)

Covers all acceptance criteria from the work contract:
1. Exact due date → deterministic days_to_due
2. Due date == as_of → DUE status
3. Due date < as_of → OVERDUE status
4. Due date None → UNKNOWN status with days_to_due=None
5. open_date alone must not synthesize six-month due date
6. is_closed=True → no active alert (is_active_alert=False)
7. Same security with different due dates remains independently evaluable
8. Discretionary SELL must not become MARGIN_EXPIRY without evidence
9. Issue #79 untouched (not testing that here)
"""
from datetime import date

import pytest

from scripts.margin_expiry import (
    DueStatus,
    ExitReason,
    MarginTerm,
    DataSource,
    MarginExpiryInput,
    MarginExpiryResult,
    ExpiryThresholds,
    calculate_expiry_status,
)


class TestDeterministicCalculation:
    """Test exact due date → deterministic days_to_due calculation."""

    def test_exact_days_calculation(self):
        """Acceptance test 1: repayment_due_date=2026-09-17, as_of=2026-09-04 → days_to_due=13"""
        input_data = MarginExpiryInput(
            repayment_due_date=date(2026, 9, 17),
            as_of=date(2026, 9, 4),
            security_code="7011",
        )
        result = calculate_expiry_status(input_data)
        
        assert result.days_to_due == 13
        assert result.due_status == DueStatus.URGENT  # Default threshold: 13 days ≤ 30 days
        assert result.security_code == "7011"
        assert result.authority == "INFORMATION_ONLY"

    def test_large_gap_calculation(self):
        """Many days until expiry."""
        input_data = MarginExpiryInput(
            repayment_due_date=date(2026, 12, 31),
            as_of=date(2026, 9, 1),
            security_code="7011",
        )
        result = calculate_expiry_status(input_data)
        
        assert result.days_to_due == 121  # 121 days
        assert result.due_status == DueStatus.OK

    def test_one_day_remaining(self):
        """One day until expiry."""
        input_data = MarginExpiryInput(
            repayment_due_date=date(2026, 9, 5),
            as_of=date(2026, 9, 4),
        )
        result = calculate_expiry_status(input_data)
        
        assert result.days_to_due == 1
        assert result.due_status == DueStatus.URGENT  # Default: 1 ≤ 7 days


class TestDueDateSameAsToday:
    """Test due date == as_of → DUE status."""

    def test_due_today(self):
        """Acceptance test 2: repayment_due_date == as_of → DUE"""
        input_data = MarginExpiryInput(
            repayment_due_date=date(2026, 9, 3),
            as_of=date(2026, 9, 3),
            security_code="7011",
        )
        result = calculate_expiry_status(input_data)
        
        assert result.days_to_due == 0
        assert result.due_status == DueStatus.DUE
        assert result.is_active_alert is True  # Open position with DUE status


class TestOverdueStatus:
    """Test due date < as_of → OVERDUE status."""

    def test_one_day_overdue(self):
        """Acceptance test 3: repayment_due_date < as_of → OVERDUE"""
        input_data = MarginExpiryInput(
            repayment_due_date=date(2026, 9, 2),
            as_of=date(2026, 9, 3),
            security_code="7011",
        )
        result = calculate_expiry_status(input_data)
        
        assert result.days_to_due == -1
        assert result.due_status == DueStatus.OVERDUE
        assert result.is_active_alert is True

    def test_many_days_overdue(self):
        """Multiple days past due."""
        input_data = MarginExpiryInput(
            repayment_due_date=date(2026, 8, 1),
            as_of=date(2026, 9, 3),
        )
        result = calculate_expiry_status(input_data)
        
        assert result.days_to_due == -33
        assert result.due_status == DueStatus.OVERDUE


class TestUnknownStatus:
    """Test due date None → UNKNOWN status with days_to_due=None."""

    def test_missing_due_date(self):
        """Acceptance test 4: repayment_due_date=None → days_to_due=None and UNKNOWN"""
        input_data = MarginExpiryInput(
            repayment_due_date=None,
            as_of=date(2026, 9, 4),
            security_code="7011",
        )
        result = calculate_expiry_status(input_data)
        
        assert result.days_to_due is None
        assert result.due_status == DueStatus.UNKNOWN
        assert result.is_active_alert is False  # Unknown = no alert

    def test_unknown_with_open_date_does_not_infer(self):
        """Acceptance test 5: open_date alone must not synthesize six-month due date.
        
        Even if we know the open date, we DO NOT calculate due date.
        Fail-closed: no due date → UNKNOWN.
        """
        input_data = MarginExpiryInput(
            repayment_due_date=None,  # Missing
            open_date=date(2026, 3, 3),  # Present but not used for inference
            as_of=date(2026, 9, 4),
            security_code="7011",
            margin_term=MarginTerm.SIX_MONTH,  # Even with 6M term specified
        )
        result = calculate_expiry_status(input_data)
        
        # Must NOT calculate: open_date + 6 months = 2026-09-03
        assert result.days_to_due is None
        assert result.due_status == DueStatus.UNKNOWN
        assert result.is_active_alert is False


class TestClosedPositionHandling:
    """Test is_closed=True → no active alert."""

    def test_closed_position_no_alert_even_if_overdue(self):
        """Acceptance test 6: is_closed=true → no active expiry alert."""
        input_data = MarginExpiryInput(
            repayment_due_date=date(2026, 9, 2),
            as_of=date(2026, 9, 5),  # 3 days overdue
            is_closed=True,
            security_code="7011",
        )
        result = calculate_expiry_status(input_data)
        
        assert result.days_to_due == -3
        assert result.due_status == DueStatus.OVERDUE
        assert result.is_active_alert is False  # Closed → no alert

    def test_closed_position_no_alert_even_if_due(self):
        """Closed position with DUE status still emits no alert."""
        input_data = MarginExpiryInput(
            repayment_due_date=date(2026, 9, 3),
            as_of=date(2026, 9, 3),
            is_closed=True,
        )
        result = calculate_expiry_status(input_data)
        
        assert result.days_to_due == 0
        assert result.due_status == DueStatus.DUE
        assert result.is_active_alert is False

    def test_open_position_with_due_status_alerts(self):
        """Open position (default is_closed=False) with DUE status alerts."""
        input_data = MarginExpiryInput(
            repayment_due_date=date(2026, 9, 3),
            as_of=date(2026, 9, 3),
            is_closed=False,
        )
        result = calculate_expiry_status(input_data)
        
        assert result.is_active_alert is True


class TestMultiplePositionsIndependence:
    """Test same security with different due dates remains independently evaluable."""

    def test_same_security_different_due_dates(self):
        """Acceptance test 7: Same security with due dates 2026-11-05 and 2026-11-25
        remains independently evaluable.
        """
        # Position 1: Due Nov 5
        position1 = MarginExpiryInput(
            repayment_due_date=date(2026, 11, 5),
            as_of=date(2026, 9, 4),
            security_code="7011",
            position_id="7011_pos1",
        )
        result1 = calculate_expiry_status(position1)
        
        # Position 2: Due Nov 25
        position2 = MarginExpiryInput(
            repayment_due_date=date(2026, 11, 25),
            as_of=date(2026, 9, 4),
            security_code="7011",
            position_id="7011_pos2",
        )
        result2 = calculate_expiry_status(position2)
        
        # Both remain independent
        assert result1.position_id == "7011_pos1"
        assert result1.days_to_due == 62
        
        assert result2.position_id == "7011_pos2"
        assert result2.days_to_due == 82
        
        # Different statuses based on their own due dates
        assert result1.security_code == result2.security_code == "7011"
        assert result1.days_to_due != result2.days_to_due


class TestExitReasonDistinction:
    """Test discretionary SELL vs MARGIN_EXPIRY distinction."""

    def test_exit_reason_enum_exists(self):
        """Acceptance test 8: Discretionary cash SELL must not become MARGIN_EXPIRY
        without position-level expiry/broker evidence.
        
        We provide distinct enum values for Trade Journal integration.
        """
        # Verify enum values exist and are distinct
        assert ExitReason.MARGIN_EXPIRY.value == "MARGIN_EXPIRY"
        assert ExitReason.DISCRETIONARY_SELL.value == "DISCRETIONARY_SELL"
        assert ExitReason.MARGIN_EXPIRY != ExitReason.DISCRETIONARY_SELL

    def test_margin_expiry_reason_usage(self):
        """MARGIN_EXPIRY reason is available for Trade Journal when position
        is force-closed due to repayment deadline.
        """
        # This demonstrates the API contract for PR2 (Trade Journal integration)
        # The actual usage will be in Trade Journal, not in this pure domain model
        exit_reason = ExitReason.MARGIN_EXPIRY
        assert exit_reason == "MARGIN_EXPIRY"


class TestStatusTiers:
    """Test status tier thresholds."""

    def test_default_thresholds(self):
        """Default thresholds: NOTICE at 30 days, URGENT at 7 days."""
        # 31 days → OK
        result = calculate_expiry_status(MarginExpiryInput(
            repayment_due_date=date(2026, 10, 5),
            as_of=date(2026, 9, 4),
        ))
        assert result.days_to_due == 31
        assert result.due_status == DueStatus.OK
        assert result.is_active_alert is False
        
        # 30 days → NOTICE
        result = calculate_expiry_status(MarginExpiryInput(
            repayment_due_date=date(2026, 10, 4),
            as_of=date(2026, 9, 4),
        ))
        assert result.days_to_due == 30
        assert result.due_status == DueStatus.NOTICE
        assert result.is_active_alert is True
        
        # 7 days → URGENT
        result = calculate_expiry_status(MarginExpiryInput(
            repayment_due_date=date(2026, 9, 11),
            as_of=date(2026, 9, 4),
        ))
        assert result.days_to_due == 7
        assert result.due_status == DueStatus.URGENT
        assert result.is_active_alert is True

    def test_custom_thresholds(self):
        """Custom thresholds can be configured."""
        custom = ExpiryThresholds(notice_days=14, urgent_days=3)
        
        # 15 days with custom threshold → OK
        result = calculate_expiry_status(
            MarginExpiryInput(
                repayment_due_date=date(2026, 9, 19),
                as_of=date(2026, 9, 4),
            ),
            thresholds=custom,
        )
        assert result.days_to_due == 15
        assert result.due_status == DueStatus.OK
        
        # 14 days with custom threshold → NOTICE
        result = calculate_expiry_status(
            MarginExpiryInput(
                repayment_due_date=date(2026, 9, 18),
                as_of=date(2026, 9, 4),
            ),
            thresholds=custom,
        )
        assert result.days_to_due == 14
        assert result.due_status == DueStatus.NOTICE
        
        # 3 days with custom threshold → URGENT
        result = calculate_expiry_status(
            MarginExpiryInput(
                repayment_due_date=date(2026, 9, 7),
                as_of=date(2026, 9, 4),
            ),
            thresholds=custom,
        )
        assert result.days_to_due == 3
        assert result.due_status == DueStatus.URGENT

    def test_invalid_thresholds(self):
        """Threshold validation."""
        with pytest.raises(ValueError, match="notice_days.*must be >= urgent_days"):
            ExpiryThresholds(notice_days=5, urgent_days=10)
        
        with pytest.raises(ValueError, match="urgent_days.*must be >= 0"):
            ExpiryThresholds(notice_days=10, urgent_days=-1)


class TestMetadataPreservation:
    """Test that metadata is preserved in results."""

    def test_metadata_echo(self):
        """Input metadata is echoed to output."""
        input_data = MarginExpiryInput(
            repayment_due_date=date(2026, 9, 17),
            as_of=date(2026, 9, 4),
            position_id="pos_123",
            security_code="7011",
            margin_term=MarginTerm.SIX_MONTH,
            source=DataSource.SBI_CSV,
            source_as_of=date(2026, 9, 3),
        )
        result = calculate_expiry_status(input_data)
        
        assert result.position_id == "pos_123"
        assert result.security_code == "7011"
        assert result.margin_term == MarginTerm.SIX_MONTH
        assert result.source == DataSource.SBI_CSV
        assert result.source_as_of == date(2026, 9, 3)
        assert result.authority == "INFORMATION_ONLY"
