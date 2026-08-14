from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


FAIL_CLOSED = (
    "PREFLIGHT_INVALID",
    "DEPENDENCY_BLOCKED",
    "WORKER_BLOCKED",
    "OWNER_CONFLICT",
)


@dataclass(frozen=True)
class Candidate:
    issue_number: int
    priority: int
    risk: str
    owner_slice: str
    allowed_paths: tuple[str, ...]
    dependencies_satisfied: bool
    preflight_valid: bool
    preferred_worker: str


def _candidate(raw: Mapping[str, Any]) -> Candidate:
    return Candidate(
        issue_number=int(raw["issue_number"]),
        priority=int(raw.get("priority", 999)),
        risk=str(raw.get("risk", "")),
        owner_slice=str(raw.get("owner_slice", "")),
        allowed_paths=tuple(str(path) for path in raw.get("allowed_paths", ())),
        dependencies_satisfied=bool(raw.get("dependencies_satisfied", False)),
        preflight_valid=bool(raw.get("preflight_valid", False)),
        preferred_worker=str(raw.get("preferred_worker", "")),
    )


def select_next_work(
    candidates: Iterable[Mapping[str, Any]],
    *,
    worker_states: Mapping[str, str],
    active_owner_slices: Iterable[str] = (),
    active_paths: Iterable[str] = (),
) -> dict[str, Any]:
    """Return one deterministic safe candidate without performing GitHub writes."""
    owners = set(active_owner_slices)
    paths = set(active_paths)
    metrics = {
        "candidate_scan_count": 0,
        "duplicate_start_prevented_count": 0,
        "no_safe_candidate_count": 0,
        "routed_to_copilot_count": 0,
    }
    blocked_reasons: list[str] = []
    eligible: list[Candidate] = []

    for raw in candidates:
        metrics["candidate_scan_count"] += 1
        item = _candidate(raw)
        if not item.preflight_valid:
            blocked_reasons.append("PREFLIGHT_INVALID")
            continue
        if not item.dependencies_satisfied:
            blocked_reasons.append("DEPENDENCY_BLOCKED")
            continue
        if worker_states.get(item.preferred_worker) not in {"available", "idle"}:
            blocked_reasons.append("WORKER_BLOCKED")
            continue
        if item.owner_slice in owners or paths.intersection(item.allowed_paths):
            metrics["duplicate_start_prevented_count"] += 1
            blocked_reasons.append("OWNER_CONFLICT")
            continue
        eligible.append(item)

    if not eligible:
        metrics["no_safe_candidate_count"] = 1
        reason = next((code for code in FAIL_CLOSED if code in blocked_reasons), "NO_SAFE_CANDIDATE")
        return {"status": reason, "selected": None, "metrics": metrics}

    eligible.sort(
        key=lambda item: (
            0 if item.risk == "GREEN" else 1,
            item.priority,
            item.issue_number,
        )
    )
    selected = eligible[0]
    if selected.preferred_worker == "copilot":
        metrics["routed_to_copilot_count"] = 1
    return {
        "status": "SELECTED",
        "selected": {
            "issue_number": selected.issue_number,
            "owner_slice": selected.owner_slice,
            "worker": selected.preferred_worker,
            "reason": "SAFE_HIGHEST_PRIORITY",
        },
        "metrics": metrics,
    }
