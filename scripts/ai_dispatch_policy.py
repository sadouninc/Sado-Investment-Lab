from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


COPILOT_ENGINE = "copilot"
FREE_FALLBACK_ENGINE = "amazon_q_free"
DEFAULT_LEASE_MINUTES = 60

# Safety/contract failures must not be retried by a different model. They indicate
# that the work itself is unsafe or malformed, not that Copilot capacity failed.
FAIL_CLOSED_OUTCOMES = frozenset(
    {
        "BLOCKED_CONTRACT_PREFLIGHT",
        "BLOCKED_FORBIDDEN_PATH",
        "BLOCKED_ISSUE_PATH_CONTRACT",
        "PROTECTED_ISSUE_79",
        "SOURCE_NOT_REVIEW_READY_VALIDATED",
        "MALFORMED_METADATA",
    }
)

# These are execution/capacity-style failures where #607 permits free-engine
# failover. Unknown execution failures also fail closed unless explicitly marked
# as retryable by the orchestration layer.
RETRYABLE_OUTCOMES = frozenset(
    {
        "COPILOT_AUTH_OR_QUOTA_BLOCKED",
        "COPILOT_SERVICE_FAILURE",
        "BLOCKED_AGENT_NOT_REVIEW_READY",
        "BLOCKED_RESULT_MISSING",
        "BLOCKED_BEFORE_HARNESS_COMPLETE",
    }
)


@dataclass(frozen=True)
class DispatchLease:
    work_ref: str
    owner_slice: str
    engine: str
    assigned_at: str
    acknowledged_at: str | None
    lease_expires_at: str
    fallback_owner: str
    status: str = "ASSIGNED"


def _parse_utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def create_dispatch_lease(
    *,
    issue_number: int,
    engine: str,
    assigned_at: str | datetime,
    owner_slice: str | None = None,
    fallback_owner: str = "sora",
    lease_minutes: int = DEFAULT_LEASE_MINUTES,
) -> dict[str, Any]:
    if issue_number == 79:
        return {"status": "PROTECTED_ISSUE_79", "lease": None}
    if lease_minutes <= 0:
        return {"status": "INVALID_LEASE", "lease": None}

    assigned = _parse_utc(assigned_at)
    lease = DispatchLease(
        work_ref=f"issue:{issue_number}",
        owner_slice=owner_slice or f"issue-{issue_number}",
        engine=engine,
        assigned_at=assigned.isoformat().replace("+00:00", "Z"),
        acknowledged_at=None,
        lease_expires_at=(assigned + timedelta(minutes=lease_minutes))
        .isoformat()
        .replace("+00:00", "Z"),
        fallback_owner=fallback_owner,
    )
    return {"status": "LEASE_CREATED", "lease": asdict(lease)}


def evaluate_dispatch_result(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Return the next safe orchestration action for one AI dispatch result.

    This function never performs GitHub writes. The workflow/SM layer executes the
    returned action only after recording the persistent lease/evidence.
    """
    issue_number = int(raw.get("issue_number", 0))
    engine = str(raw.get("engine", ""))
    outcome = str(raw.get("outcome", "UNKNOWN"))
    run_success = bool(raw.get("run_success", False))
    retryable_execution_failure = bool(raw.get("retryable_execution_failure", False))

    if issue_number == 79:
        return {"status": "BLOCK", "action": "NONE", "reason": "PROTECTED_ISSUE_79"}

    if outcome in FAIL_CLOSED_OUTCOMES:
        return {"status": "BLOCK", "action": "NONE", "reason": outcome}

    if engine == COPILOT_ENGINE and run_success and outcome == "REVIEW_READY_VALIDATED":
        return {
            "status": "ACTIONED",
            "action": "PROMOTE_PATCH",
            "reason": "COPILOT_VALIDATED",
        }

    if engine == COPILOT_ENGINE and (
        outcome in RETRYABLE_OUTCOMES or retryable_execution_failure
    ):
        return {
            "status": "ACTIONED",
            "action": "FALLBACK_AMAZON_Q_FREE",
            "reason": outcome if outcome != "UNKNOWN" else "RETRYABLE_EXECUTION_FAILURE",
        }

    if engine == FREE_FALLBACK_ENGINE and not run_success:
        return {
            "status": "BLOCK",
            "action": "ROUTE_HUMAN_OR_NEXT_ENGINE",
            "reason": outcome,
        }

    return {"status": "BLOCK", "action": "NONE", "reason": outcome}


def lease_is_expired(
    lease: Mapping[str, Any], *, now: str | datetime
) -> bool:
    if lease.get("acknowledged_at"):
        return False
    expires = _parse_utc(str(lease["lease_expires_at"]))
    return _parse_utc(now) >= expires
