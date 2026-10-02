from __future__ import annotations

"""Autonomous Queue Consumer adapter (Issue #556)."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from scripts.executor_dispatch_adapters import FORBIDDEN_ISSUE, build_dispatch_plan
from scripts.multi_executor_router import issue_lease
from scripts.queue_auto_promotion import select_next_work
from scripts.queue_candidate_adapter import build_queue_candidate
from scripts.work_contract_consumer_preflight import evaluate_issue

SUPPORTED_WORKER = "copilot"
AUTONOMOUS_AUTHORITY = "STANDARD"

def build_bounded_candidates(issues: Iterable[Mapping[str, Any]], *, priority_by_issue: Mapping[int, int] | None = None) -> list[dict[str, Any]]:
    priority_by_issue = priority_by_issue or {}
    candidates: list[dict[str, Any]] = []
    for issue in sorted(issues, key=lambda item: int(item.get("number", 0))):
        number = int(issue.get("number", 0))
        if number == FORBIDDEN_ISSUE:
            continue
        preflight = evaluate_issue(issue)
        contract = preflight.get("contract") or {}
        authority = str(contract.get("authority", "")).strip().upper()
        dependencies = contract.get("dependencies")
        dependencies_satisfied = bool(preflight.get("executable")) and authority == AUTONOMOUS_AUTHORITY and isinstance(dependencies, list) and len(dependencies) == 0
        candidate = build_queue_candidate(issue, preferred_worker=SUPPORTED_WORKER, dependencies_satisfied=dependencies_satisfied, priority=int(priority_by_issue.get(number, 999)))
        if authority != AUTONOMOUS_AUTHORITY:
            candidate["preflight_valid"] = False
        candidates.append(candidate)
    return candidates

def plan_consumer_tick(candidates: Iterable[Mapping[str, Any]], *, worker_states: Mapping[str, str], active_owner_slices: Iterable[str] = (), active_paths: Iterable[str] = (), base_sha: str, assigned_at: datetime) -> dict[str, Any]:
    candidates = list(candidates)
    selection = select_next_work(candidates, worker_states=worker_states, active_owner_slices=active_owner_slices, active_paths=active_paths)
    if selection["status"] != "SELECTED":
        return {**selection, "dispatch": None}
    selected = selection["selected"]
    issue_number = int(selected["issue_number"])
    if issue_number == FORBIDDEN_ISSUE:
        return {"status": "PROTECTED_ISSUE_79", "selected": None, "metrics": selection["metrics"], "dispatch": None}
    if selected.get("worker") != SUPPORTED_WORKER:
        return {"status": "UNSUPPORTED_WORKER", "selected": selected, "metrics": selection["metrics"], "dispatch": None}
    owner_slice = str(selected.get("owner_slice", ""))
    allowed_paths = tuple(str(path) for raw in candidates if int(raw.get("issue_number", -1)) == issue_number for path in raw.get("allowed_paths", ()))
    router_selection = {"status": "SELECTED", "work_ref": f"#{issue_number}", "task_class": "GENERAL", "executor": "COPILOT", "allowed_paths": allowed_paths, "forbidden_paths": (), "base_sha": str(base_sha), "fallback_order": ("AMAZON_Q",)}
    try:
        lease = issue_lease(router_selection, assigned_at=assigned_at)
        plan = build_dispatch_plan({"lease_id": lease["lease_id"], "executor": "COPILOT", "work_ref": f"#{issue_number}"})
    except ValueError:
        return {"status": "PROTECTED_ISSUE_79" if issue_number == FORBIDDEN_ISSUE else "LEASE_BUILD_FAILED", "selected": selected, "metrics": selection["metrics"], "dispatch": None}
    return {"status": "DISPATCH_READY", "selected": selected, "metrics": selection["metrics"], "owner_slice": owner_slice, "lease": lease, "dispatch": {"evidence_comment": plan.evidence_marker, "workflow_dispatch": {"workflow": plan.payload["workflow"], "ref": "main", "inputs": {"issue_number": str(issue_number), "lease_id": plan.lease_id}}}}

def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def _load_optional_list(path: Path | None) -> list[str]:
    if path is None:
        return []
    payload = _load_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"{path}: expected a JSON list")
    return [str(item) for item in payload]

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Queue Auto-Promotion Consumer tick (no GitHub writes)")
    parser.add_argument("--issues", required=True, type=Path)
    parser.add_argument("--worker-state", required=True, type=Path)
    parser.add_argument("--priorities", type=Path, default=None)
    parser.add_argument("--active-owner-slices", type=Path, default=None)
    parser.add_argument("--active-paths", type=Path, default=None)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--assigned-at", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        issues = _load_json(args.issues)
        if not isinstance(issues, list): raise ValueError(f"{args.issues}: expected a JSON list of Issue payloads")
        worker_states = _load_json(args.worker_state)
        if not isinstance(worker_states, dict): raise ValueError(f"{args.worker_state}: expected a JSON object")
        priorities = _load_json(args.priorities) if args.priorities else {}
        if not isinstance(priorities, dict): raise ValueError(f"{args.priorities}: expected a JSON object")
        priority_by_issue = {int(k): int(v) for k, v in priorities.items()}
        assigned_at = datetime.fromisoformat(args.assigned_at.replace("Z", "+00:00")) if args.assigned_at else datetime.now(timezone.utc)
        issues = [issue for issue in issues if int(issue.get("number", -1)) != FORBIDDEN_ISSUE]
        candidates = build_bounded_candidates(issues, priority_by_issue=priority_by_issue)
        packet = plan_consumer_tick(candidates, worker_states=worker_states, active_owner_slices=_load_optional_list(args.active_owner_slices), active_paths=_load_optional_list(args.active_paths), base_sha=args.base_sha, assigned_at=assigned_at)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.exit(2, f"queue auto-promotion consumer error: {exc}\n")
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0 if packet["status"] == "DISPATCH_READY" else 1

if __name__ == "__main__":
    raise SystemExit(main())
