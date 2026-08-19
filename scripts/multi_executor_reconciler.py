from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Iterable, Mapping

from scripts.executor_dispatch_adapters import DispatchPlan, already_dispatched, build_dispatch_plan
from scripts.multi_executor_router import evaluate_lease, issue_lease, select_route


@dataclass(frozen=True)
class Observation:
    acknowledged_at: datetime | None = None
    execution_evidence_at: datetime | None = None
    pr_open: bool = False


def dispatch_once(lease: Mapping[str, Any], *, comments: Iterable[Mapping[str, Any]], execute: Callable[[DispatchPlan], Any]) -> dict[str, Any]:
    """Execute one provider plan at most once per lease marker."""
    plan = build_dispatch_plan(lease)
    if already_dispatched(comments, lease_id=plan.lease_id):
        return {"status": "ALREADY_DISPATCHED", "lease_id": plan.lease_id, "idempotency_key": plan.idempotency_key}
    execute(plan)
    return {"status": "DISPATCHED", "lease_id": plan.lease_id, "idempotency_key": plan.idempotency_key, "evidence_marker": plan.evidence_marker}


def reconcile_lease(lease: Mapping[str, Any], *, now: datetime, observation: Observation) -> dict[str, Any]:
    """Map durable observations to the canonical lease state without mutation."""
    if observation.pr_open:
        return {"status": "PR_OPEN", "terminal": False, "implementation_capacity_released": True, "suppress_competing_lease": True}
    state = evaluate_lease(lease, now=now, acknowledged_at=observation.acknowledged_at, execution_evidence_at=observation.execution_evidence_at)
    if state["status"] == "EXECUTION_EVIDENCE":
        return {**state, "suppress_competing_lease": True, "implementation_capacity_released": False}
    return {**state, "suppress_competing_lease": False, "implementation_capacity_released": False}


def reroute_after_terminal(*, lease: Mapping[str, Any], state: Mapping[str, Any], candidates: Iterable[Mapping[str, Any]], provider_health: Mapping[str, Mapping[str, Any]], preflight: Callable[[Mapping[str, Any]], Mapping[str, Any]], assigned_at: datetime) -> dict[str, Any]:
    """Fresh-preflight and reroute only terminal pre-execution failures."""
    if not state.get("terminal") or state.get("status") not in {"DISPATCH_ACK_EXPIRED", "ACK_STALLED", "PROVIDER_UNAVAILABLE"}:
        return {"status": "NO_REROUTE", "lease_id": lease.get("lease_id")}
    refreshed = []
    for raw in candidates:
        item = dict(preflight(raw))
        if item.get("work_ref") == "#79":
            return {"status": "ISSUE_79_HARD_DENY", "selected": None}
        refreshed.append(item)
    current_executor = str(lease.get("executor", "")).upper()
    health = {key: dict(value) for key, value in provider_health.items()}
    current = health.setdefault(current_executor, {})
    try:
        failures = int(current.get("consecutive_activation_failures", 0))
    except (TypeError, ValueError):
        failures = 2
    current["consecutive_activation_failures"] = max(2, failures + 1)
    selection = select_route(refreshed, provider_health=health)
    if selection.get("status") != "SELECTED":
        return {"status": selection.get("status", "NO_SAFE_CANDIDATE"), "selected": None, "fresh_preflight": True}
    new_lease = issue_lease(selection, assigned_at=assigned_at)
    return {"status": "REROUTED", "fresh_preflight": True, "previous_lease_id": lease.get("lease_id"), "lease": new_lease}


def terminal_telemetry(*, lease: Mapping[str, Any], state: Mapping[str, Any], reroute: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Small machine-readable record consumable by #479/#723 collectors."""
    return {"lease_id": lease.get("lease_id"), "work_ref": lease.get("work_ref"), "executor": lease.get("executor"), "task_class": lease.get("task_class"), "terminal_state": state.get("status") if state.get("terminal") else None, "execution_evidence": state.get("status") in {"EXECUTION_EVIDENCE", "PR_OPEN"}, "pr_open": state.get("status") == "PR_OPEN", "rerouted": bool(reroute and reroute.get("status") == "REROUTED"), "next_executor": (reroute or {}).get("lease", {}).get("executor") if reroute else None}
