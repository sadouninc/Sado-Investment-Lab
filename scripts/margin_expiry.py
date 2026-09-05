"""Margin Position Expiry Tracking - Domain Model (PR1)

Pure deterministic expiry calculation for margin positions with repayment due dates.
Does not make investment decisions (BUY/SELL/HOLD/現引/ロール).

Authority Boundary:
- Provides INFORMATION_ONLY about margin expiry timeline
- Does not recommend or execute trades
- Distinguishes forced MARGIN_EXPIRY from discretionary SELL

Fail-Closed Approach:
- If exact due date exists → calculate deterministic days_to_due
- If due date missing/ambiguous → return UNKNOWN status
- open_date alone MUST NOT synthesize a six-month due date
- Closed positions emit no active alert
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any


class DueStatus(str, Enum):
    """Status tier for margin position expiry proximity.
    
    These are display/alert tiers, NOT investment decision rules.
    Thresholds are configurable and do not constitute trading signals.
    """
    OK = "OK"  # Not approaching expiry
    NOTICE = "NOTICE"  # Approaching expiry (default: 15-30 days)
    URGENT = "URGENT"  # Very close to expiry (default: 8-14 days)
    DUE = "DUE"  # Expiry date has arrived (0 days)
    OVERDUE = "OVERDUE"  # Past due date but position not yet closed
    UNKNOWN = "UNKNOWN"  # Due date cannot be determined


class ExitReason(str, Enum):
    """Exit reason classification for Trade Journal integration.
    
    Distinguishes forced margin expiry from discretionary user decisions.
    """
    MARGIN_EXPIRY = "MARGIN_EXPIRY"  # Forced settlement due to repayment deadline
    DISCRETIONARY_SELL = "DISCRETIONARY_SELL"  # User-initiated exit (利確/損切り)


class MarginTerm(str, Enum):
    """Margin position term type."""
    SIX_MONTH = "6M"  # 6か月信用
    GENERAL = "GENERAL"  # 制度信用
    UNKNOWN = "UNKNOWN"  # Cannot determine


class DataSource(str, Enum):
    """Source of margin position/expiry data."""
    SBI_CSV = "SBI_CSV"
    BROKER_EXPORT = "BROKER_EXPORT"
    MANUAL_VERIFIED = "MANUAL_VERIFIED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class MarginExpiryInput:
    """Input contract for margin expiry calculation."""
    # Core date facts
    repayment_due_date: date | None  # Exact due date if known
    as_of: date  # Evaluation date (typically today)
    
    # Position context
    open_date: date | None = None  # Position open date (does NOT infer due date)
    is_closed: bool = False  # Whether position is already closed
    
    # Optional metadata
    position_id: str | None = None
    security_code: str | None = None
    margin_term: MarginTerm = MarginTerm.UNKNOWN
    source: DataSource = DataSource.UNKNOWN
    source_as_of: date | None = None


@dataclass(frozen=True)
class MarginExpiryResult:
    """Output contract for margin expiry evaluation."""
    # Deterministic calculation results
    days_to_due: int | None  # None if due date unknown
    due_status: DueStatus
    
    # Context echoed from input
    position_id: str | None
    security_code: str | None
    margin_term: MarginTerm
    source: DataSource
    source_as_of: date | None
    
    # Authority declaration
    authority: str = "INFORMATION_ONLY"
    
    # Expiry-specific flag for Trade Journal
    is_active_alert: bool = False  # True only if position open and expiry near/due


@dataclass(frozen=True)
class ExpiryThresholds:
    """Configurable thresholds for status tiers.
    
    These are display/notification settings, NOT trading rules.
    """
    notice_days: int = 30  # Start showing notice
    urgent_days: int = 7   # Escalate to urgent
    
    def __post_init__(self):
        if self.notice_days < self.urgent_days:
            raise ValueError(f"notice_days ({self.notice_days}) must be >= urgent_days ({self.urgent_days})")
        if self.urgent_days < 0:
            raise ValueError(f"urgent_days ({self.urgent_days}) must be >= 0")


def calculate_expiry_status(
    input_data: MarginExpiryInput,
    thresholds: ExpiryThresholds | None = None
) -> MarginExpiryResult:
    """Calculate margin position expiry status deterministically.
    
    Fail-closed approach:
    - If repayment_due_date exists → calculate exact days_to_due
    - If repayment_due_date is None → return UNKNOWN (no inference)
    - If is_closed=True → is_active_alert=False
    
    Args:
        input_data: Margin position with due date and context
        thresholds: Optional custom thresholds (defaults to standard)
    
    Returns:
        MarginExpiryResult with deterministic status
    """
    if thresholds is None:
        thresholds = ExpiryThresholds()
    
    # If no due date, cannot calculate → UNKNOWN
    if input_data.repayment_due_date is None:
        return MarginExpiryResult(
            days_to_due=None,
            due_status=DueStatus.UNKNOWN,
            position_id=input_data.position_id,
            security_code=input_data.security_code,
            margin_term=input_data.margin_term,
            source=input_data.source,
            source_as_of=input_data.source_as_of,
            is_active_alert=False,  # Unknown = no alert
        )
    
    # Calculate deterministic days to due
    days_to_due = (input_data.repayment_due_date - input_data.as_of).days
    
    # Determine status based on days remaining
    if days_to_due < 0:
        due_status = DueStatus.OVERDUE
    elif days_to_due == 0:
        due_status = DueStatus.DUE
    elif days_to_due <= thresholds.urgent_days:
        due_status = DueStatus.URGENT
    elif days_to_due <= thresholds.notice_days:
        due_status = DueStatus.NOTICE
    else:
        due_status = DueStatus.OK
    
    # Active alert only if position is open AND status requires attention
    # (Closed positions emit no active alert)
    is_active_alert = (
        not input_data.is_closed
        and due_status in {DueStatus.NOTICE, DueStatus.URGENT, DueStatus.DUE, DueStatus.OVERDUE}
    )
    
    return MarginExpiryResult(
        days_to_due=days_to_due,
        due_status=due_status,
        position_id=input_data.position_id,
        security_code=input_data.security_code,
        margin_term=input_data.margin_term,
        source=input_data.source,
        source_as_of=input_data.source_as_of,
        is_active_alert=is_active_alert,
    )


__all__ = ["DueStatus", "ExitReason", "MarginTerm", "DataSource", "MarginExpiryInput", "MarginExpiryResult", "ExpiryThresholds", "calculate_expiry_status"]
