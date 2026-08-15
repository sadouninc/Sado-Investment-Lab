from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


ACTIVE_IMPLEMENTATION_STATES = frozenset(
    {"IMPLEMENTING", "REVISION_REQUIRED", "CONFLICT_RESOLUTION"}
)

WAIT_STATES = frozenset(
    {
        "CI_WAIT",
        "REVIEW_WAIT",
        "RESEARCH_GATE_WAIT",
        "DESIGN_GATE_WAIT",
        "OWNER_WAIT",
        "EXTERNAL_WAIT",
        "MERGE_READY",
    }
)


@dataclass(frozen=True)
class FlowHealthInput:
    user_mode: str
    worker_state: str
    work_states: tuple[str, ...]
    ready_nonconflicting_count: int
    last_new_pr_age_minutes: int | None
    dispatch_unacked_age_minutes: int | None = None
    same_blocker_run_count: int = 0


def active_implementation_wip(work_states: Iterable[str]) -> int:
    return sum(
        1 for state in work_states if str(state).upper() in ACTIVE_IMPLEMENTATION_STATES
    )


def waiting_work_count(work_states: Iterable[str]) -> int:
    return sum(1 for state in work_states if str(state).upper() in WAIT_STATES)


def evaluate_flow_health(raw: Mapping[str, Any] | FlowHealthInput) -> dict[str, Any]:
    """Evaluate queue-stall invariants without mutating GitHub state."""
    if isinstance(raw, FlowHealthInput):
        item = raw
    else:
        item = FlowHealthInput(
            user_mode=str(raw.get("user_mode", "UNKNOWN")),
            worker_state=str(raw.get("worker_state", "unknown")),
            work_states=tuple(str(value) for value in raw.get("work_states", ())),
            ready_nonconflicting_count=int(raw.get("ready_nonconflicting_count", 0)),
            last_new_pr_age_minutes=(
                None
                if raw.get("last_new_pr_age_minutes") is None
                else int(raw["last_new_pr_age_minutes"])
            ),
            dispatch_unacked_age_minutes=(
                None
                if raw.get("dispatch_unacked_age_minutes") is None
                else int(raw["dispatch_unacked_age_minutes"])
            ),
            same_blocker_run_count=int(raw.get("same_blocker_run_count", 0)),
        )

    active_wip = active_implementation_wip(item.work_states)
    waiting = waiting_work_count(item.work_states)
    actions: list[str] = []
    reasons: list[str] = []
    status = "PASS"

    if item.user_mode == "AWAY" and item.worker_state in {"idle", "available"}:
        if item.ready_nonconflicting_count > 0 and active_wip == 0:
            status = "CRITICAL"
            reasons.append("QUEUE_STARVATION")
            actions.append("ROUTE_READY_WORK")

        if item.ready_nonconflicting_count > 0 and item.last_new_pr_age_minutes is not None:
            if item.last_new_pr_age_minutes >= 240:
                status = "CRITICAL"
                reasons.append("FLOW_STALL_CRITICAL")
                actions.append("REROUTE_SAME_RUN")
            elif item.last_new_pr_age_minutes >= 120 and status == "PASS":
                status = "WARN"
                reasons.append("FLOW_STALL_WARNING")
                actions.append("CHECK_QUEUE_REPLENISH")

    if item.dispatch_unacked_age_minutes is not None and item.dispatch_unacked_age_minutes >= 60:
        status = "CRITICAL"
        reasons.append("DISPATCH_LEASE_EXPIRED")
        actions.append("EXPIRE_OR_REROUTE_DISPATCH")

    if item.same_blocker_run_count >= 2:
        status = "CRITICAL"
        reasons.append("BLOCKED_ESCAPE_OVERDUE")
        actions.append("BLOCKED_ESCAPE")

    if item.ready_nonconflicting_count > 0 and item.last_new_pr_age_minutes is None:
        if status == "PASS":
            status = "WARN"
        reasons.append("LAST_PR_AGE_UNKNOWN")
        actions.append("COLLECT_DURABLE_OUTPUT_AGE")

    if waiting > 0 and active_wip == 0:
        reasons.append("WAITING_WORK_RELEASES_IMPLEMENTATION_CAPACITY")

    return {
        "status": status,
        "active_implementation_wip": active_wip,
        "waiting_work_count": waiting,
        "ready_nonconflicting_count": item.ready_nonconflicting_count,
        "last_new_pr_age_minutes": item.last_new_pr_age_minutes,
        "dispatch_unacked_age_minutes": item.dispatch_unacked_age_minutes,
        "same_blocker_run_count": item.same_blocker_run_count,
        "reasons": tuple(dict.fromkeys(reasons)),
        "actions": tuple(dict.fromkeys(actions)),
    }
