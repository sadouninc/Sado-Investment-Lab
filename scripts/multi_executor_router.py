from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Iterable, Mapping


DEFAULT_EXECUTOR_ORDER = ("AMAZON_Q", "JULES", "SORA")
HEALTHY_STATES = {"HEALTHY", "AVAILABLE", "IDLE"}
TERMINAL_PRE_EXECUTION = {
    "DISPATCH_ACK_EXPIRED",
    "ACK_STALLED",
    "PROVIDER_UNAVAILABLE",
    "ROUTING_CONFLICT",
}


@dataclass(frozen=True)
class RouterCandidate:
    work_ref: str
    task_class: str
    priority: int
    risk: str
    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    base_sha: str
    eligible_executors: tuple[str, ...]
    preflight_valid: bool
    dependencies_satisfied: bool
    owner_conflict: bool
    path_conflict: bool


def _candidate(raw: Mapping[str, Any]) -> RouterCandidate:
    return RouterCandidate(
        work_ref=str(raw["work_ref"]).strip(),
        task_class=str(raw.get("task_class", "GENERAL")).strip() or "GENERAL",
        priority=int(raw.get("priority", 999)),
        risk=str(raw.get("risk", "")).upper(),
        allowed_paths=tuple(str(v) for v in raw.get("allowed_paths", ())),
        forbidden_paths=tuple(str(v) for v in raw.get("forbidden_paths", ())),
        base_sha=str(raw.get("base_sha", "")).strip(),
        eligible_executors=tuple(str(v).upper() for v in raw.get("eligible_executors", DEFAULT_EXECUTOR_ORDER)),
        preflight_valid=bool(raw.get("preflight_valid", False)),
        dependencies_satisfied=bool(raw.get("dependencies_satisfied", False)),
        owner_conflict=bool(raw.get("owner_conflict", False)),
        path_conflict=bool(raw.get("path_conflict", False)),
    )


def _provider_eligible(provider: str, health: Mapping[str, Any]) -> bool:
    state = str(health.get("state", "UNKNOWN")).upper()
    if state not in HEALTHY_STATES:
        return False
    if int(health.get("consecutive_activation_failures", 0)) >= 2:
        return False
    cooldown_until = health.get("cooldown_until")
    if cooldown_until:
        try:
            until = datetime.fromisoformat(str(cooldown_until).replace("Z", "+00:00"))
        except ValueError:
            return False
        if until.tzinfo is None:
            return False
        now = health.get("now")
        if now is None:
            return False
        current = datetime.fromisoformat(str(now).replace("Z", "+00:00"))
        if current.tzinfo is None or current < until:
            return False
    return True


def select_route(
    candidates: Iterable[Mapping[str, Any]],
    *,
    provider_health: Mapping[str, Mapping[str, Any]],
    executor_order: Iterable[str] = DEFAULT_EXECUTOR_ORDER,
) -> dict[str, Any]:
    """Select one READY work item and one executor deterministically.

    Pure function: no GitHub writes, dispatches, or mutations.
    """
    normalized_order = tuple(str(v).upper() for v in executor_order)
    safe: list[RouterCandidate] = []
    blocked: list[str] = []

    for raw in candidates:
        try:
            item = _candidate(raw)
        except (KeyError, TypeError, ValueError):
            blocked.append("PREFLIGHT_INVALID")
            continue
        if not item.work_ref or not item.base_sha or not item.preflight_valid:
            blocked.append("PREFLIGHT_INVALID")
            continue
        if not item.dependencies_satisfied:
            blocked.append("DEPENDENCY_BLOCKED")
            continue
        if item.owner_conflict or item.path_conflict:
            blocked.append("ROUTING_CONFLICT")
            continue
        if item.risk not in {"GREEN", "YELLOW"}:
            blocked.append("RISK_NOT_ELIGIBLE")
            continue
        safe.append(item)

    safe.sort(key=lambda item: (item.priority, item.work_ref))
    for item in safe:
        for executor in normalized_order:
            if executor not in item.eligible_executors:
                continue
            if _provider_eligible(executor, provider_health.get(executor, {})):
                return {
                    "status": "SELECTED",
                    "work_ref": item.work_ref,
                    "task_class": item.task_class,
                    "executor": executor,
                    "risk": item.risk,
                    "allowed_paths": item.allowed_paths,
                    "forbidden_paths": item.forbidden_paths,
                    "base_sha": item.base_sha,
                    "fallback_order": tuple(v for v in normalized_order if v != executor),
                }

    if safe:
        return {"status": "PROVIDER_UNAVAILABLE", "selected": None}
    reason_order = ("PREFLIGHT_INVALID", "DEPENDENCY_BLOCKED", "ROUTING_CONFLICT", "RISK_NOT_ELIGIBLE")
    reason = next((r for r in reason_order if r in blocked), "NO_SAFE_CANDIDATE")
    return {"status": reason, "selected": None}


def issue_lease(selection: Mapping[str, Any], *, assigned_at: datetime) -> dict[str, Any]:
    if selection.get("status") != "SELECTED":
        raise ValueError("lease requires SELECTED routing result")
    if assigned_at.tzinfo is None or assigned_at.utcoffset() is None:
        raise ValueError("assigned_at must be timezone-aware")
    assigned = assigned_at.astimezone(timezone.utc)
    ack_deadline = assigned + timedelta(minutes=10)
    material = "|".join(
        [
            str(selection["work_ref"]),
            str(selection["executor"]),
            str(selection["base_sha"]),
            assigned.isoformat(),
        ]
    )
    lease_id = "lease-" + sha256(material.encode("utf-8")).hexdigest()[:20]
    return {
        "lease_id": lease_id,
        "work_ref": selection["work_ref"],
        "executor": selection["executor"],
        "task_class": selection["task_class"],
        "assigned_at": assigned.isoformat(),
        "ack_deadline": ack_deadline.isoformat(),
        "execution_evidence_deadline": None,
        "allowed_paths": tuple(selection["allowed_paths"]),
        "forbidden_paths": tuple(selection["forbidden_paths"]),
        "base_sha": selection["base_sha"],
        "fallback_order": tuple(selection["fallback_order"]),
        "terminal_state": None,
    }


def evaluate_lease(
    lease: Mapping[str, Any],
    *,
    now: datetime,
    acknowledged_at: datetime | None = None,
    execution_evidence_at: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate canonical dispatch lease semantics without side effects."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now_utc = now.astimezone(timezone.utc)
    assigned = datetime.fromisoformat(str(lease["assigned_at"]))
    ack_deadline = datetime.fromisoformat(str(lease["ack_deadline"]))

    if execution_evidence_at is not None:
        if execution_evidence_at.tzinfo is None:
            raise ValueError("execution_evidence_at must be timezone-aware")
        return {"status": "EXECUTION_EVIDENCE", "terminal": False}

    if acknowledged_at is None:
        if now_utc >= ack_deadline:
            return {"status": "DISPATCH_ACK_EXPIRED", "terminal": True}
        return {"status": "DISPATCHED", "terminal": False}

    if acknowledged_at.tzinfo is None:
        raise ValueError("acknowledged_at must be timezone-aware")
    ack = acknowledged_at.astimezone(timezone.utc)
    if ack >= ack_deadline:
        return {"status": "DISPATCH_ACK_EXPIRED", "terminal": True, "late_ack": True}
    evidence_deadline = ack + timedelta(minutes=20)
    if now_utc >= evidence_deadline:
        return {"status": "ACK_STALLED", "terminal": True, "execution_evidence_deadline": evidence_deadline.isoformat()}
    return {"status": "ACKED", "terminal": False, "execution_evidence_deadline": evidence_deadline.isoformat()}
