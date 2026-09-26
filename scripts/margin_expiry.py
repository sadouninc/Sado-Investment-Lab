"""Margin Position Expiry Tracking - Domain Model (PR1).

Pure deterministic expiry calculation for margin positions with repayment due dates.
This module is INFORMATION_ONLY and never emits BUY/SELL/HOLD/現引/ロール decisions.

Fail-closed rules:
- exact repayment_due_date -> deterministic days_to_due
- missing due date -> UNKNOWN; open_date alone never synthesizes a due date
- closed positions never emit active alerts
- stale or unknown source freshness never qualifies for an active alert
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class DueStatus(str, Enum):
    OK = "OK"
    NOTICE = "NOTICE"
    URGENT = "URGENT"
    DUE = "DUE"
    OVERDUE = "OVERDUE"
    UNKNOWN = "UNKNOWN"


class SourceFreshness(str, Enum):
    """Caller-provided source freshness; UNKNOWN is intentionally fail-closed."""

    CURRENT = "CURRENT"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class ExitReason(str, Enum):
    MARGIN_EXPIRY = "MARGIN_EXPIRY"
    DISCRETIONARY_SELL = "DISCRETIONARY_SELL"


class MarginTerm(str, Enum):
    SIX_MONTH = "6M"
    GENERAL = "GENERAL"
    UNKNOWN = "UNKNOWN"


class DataSource(str, Enum):
    SBI_CSV = "SBI_CSV"
    BROKER_EXPORT = "BROKER_EXPORT"
    MANUAL_VERIFIED = "MANUAL_VERIFIED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class MarginExpiryInput:
    repayment_due_date: date | None
    as_of: date
    open_date: date | None = None
    is_closed: bool = False
    position_id: str | None = None
    security_code: str | None = None
    margin_term: MarginTerm = MarginTerm.UNKNOWN
    source: DataSource = DataSource.UNKNOWN
    source_as_of: date | None = None
    # Freshness is an explicit caller fact. This module does not invent broker
    # freshness thresholds. Omitted/unknown freshness therefore fails closed.
    source_freshness: SourceFreshness = SourceFreshness.UNKNOWN


@dataclass(frozen=True)
class MarginExpiryResult:
    days_to_due: int | None
    due_status: DueStatus
    position_id: str | None
    security_code: str | None
    margin_term: MarginTerm
    source: DataSource
    source_as_of: date | None
    source_freshness: SourceFreshness
    authority: str = "INFORMATION_ONLY"
    is_active_alert: bool = False
    # Explicit eligibility makes stale/unknown distinguishable from a normal
    # non-alerting OK position without requiring callers to reverse-engineer it.
    active_alert_eligible: bool = False


@dataclass(frozen=True)
class ExpiryThresholds:
    """Display/notification thresholds, not trading rules."""

    notice_days: int = 30
    urgent_days: int = 7

    def __post_init__(self) -> None:
        if self.notice_days < self.urgent_days:
            raise ValueError(
                f"notice_days ({self.notice_days}) must be >= urgent_days ({self.urgent_days})"
            )
        if self.urgent_days < 0:
            raise ValueError(f"urgent_days ({self.urgent_days}) must be >= 0")


def _result(
    input_data: MarginExpiryInput,
    *,
    days_to_due: int | None,
    due_status: DueStatus,
    active_alert_eligible: bool,
    is_active_alert: bool,
) -> MarginExpiryResult:
    return MarginExpiryResult(
        days_to_due=days_to_due,
        due_status=due_status,
        position_id=input_data.position_id,
        security_code=input_data.security_code,
        margin_term=input_data.margin_term,
        source=input_data.source,
        source_as_of=input_data.source_as_of,
        source_freshness=input_data.source_freshness,
        active_alert_eligible=active_alert_eligible,
        is_active_alert=is_active_alert,
    )


def calculate_expiry_status(
    input_data: MarginExpiryInput,
    thresholds: ExpiryThresholds | None = None,
) -> MarginExpiryResult:
    """Calculate expiry proximity while failing closed on source freshness.

    `due_status` remains a deterministic statement about the supplied due date.
    Active-alert eligibility is separate: only an open position whose caller
    explicitly marks the source CURRENT may produce an active alert.
    """
    thresholds = thresholds or ExpiryThresholds()

    if input_data.repayment_due_date is None:
        return _result(
            input_data,
            days_to_due=None,
            due_status=DueStatus.UNKNOWN,
            active_alert_eligible=False,
            is_active_alert=False,
        )

    days_to_due = (input_data.repayment_due_date - input_data.as_of).days
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

    active_alert_eligible = (
        not input_data.is_closed
        and input_data.source_freshness is SourceFreshness.CURRENT
    )
    is_active_alert = (
        active_alert_eligible
        and due_status
        in {DueStatus.NOTICE, DueStatus.URGENT, DueStatus.DUE, DueStatus.OVERDUE}
    )

    return _result(
        input_data,
        days_to_due=days_to_due,
        due_status=due_status,
        active_alert_eligible=active_alert_eligible,
        is_active_alert=is_active_alert,
    )


__all__ = [
    "DueStatus",
    "SourceFreshness",
    "ExitReason",
    "MarginTerm",
    "DataSource",
    "MarginExpiryInput",
    "MarginExpiryResult",
    "ExpiryThresholds",
    "calculate_expiry_status",
]
