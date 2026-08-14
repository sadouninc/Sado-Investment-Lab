from __future__ import annotations

from typing import Any, Mapping

from scripts.work_contract_consumer_preflight import evaluate_issue


def build_queue_candidate(
    issue: Mapping[str, Any],
    *,
    preferred_worker: str,
    dependencies_satisfied: bool,
    priority: int = 999,
) -> dict[str, Any]:
    """Normalize one GitHub Issue into the pure selector candidate contract.

    This adapter performs no GitHub writes and delegates contract validity to the
    existing Work Contract consumer preflight.
    """
    preflight = evaluate_issue(issue)
    contract = preflight.get("contract") or {}
    return {
        "issue_number": int(issue.get("number", 0)),
        "priority": int(priority),
        "risk": str(contract.get("risk", "")),
        "owner_slice": str(contract.get("owner_slice", "")),
        "allowed_paths": list(contract.get("allowed_paths") or []),
        "dependencies_satisfied": bool(dependencies_satisfied),
        "preflight_valid": bool(preflight.get("executable", False)),
        "preferred_worker": preferred_worker,
        "preflight_reason_codes": list(preflight.get("reason_codes") or []),
    }
