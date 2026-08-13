#!/usr/bin/env python3
import json
from typing import Any, Dict, List


def normalize_blockers(conflicts: List[str]) -> List[str]:
    mapping = {"stale base": "merge_conflict", "merge conflict": "merge_conflict", "superseded": "superseded", "duplicate work": "superseded"}
    out = []
    for conflict in conflicts:
        key = str(conflict).lower().strip()
        normalized = mapping.get(key, conflict)
        if normalized not in out:
            out.append(normalized)
    return out


def first_marker_time(markers, name):
    for marker in markers or []:
        if marker.get("name") == name:
            return marker.get("at")
    return None


def count_ci_rework(ci_runs):
    rework_count = 0
    failure_open = False
    for run in ci_runs or []:
        status = str(run.get("status", "")).lower()
        if status == "failure":
            failure_open = True
        elif status == "success" and failure_open:
            rework_count += 1
            failure_open = False
    return rework_count


def first_pass_ci(ci_runs):
    for run in ci_runs or []:
        status = str(run.get("status", "")).lower()
        if status == "success": return "PASS"
        if status == "failure": return "FAIL"
    return "UNKNOWN"


def count_review_rework(reviews, fix_events):
    requested = [str(r.get("round_id")) for r in reviews or [] if r.get("event") == "CHANGES_REQUESTED" and r.get("round_id") is not None]
    fixed = {str(f.get("round_id")) for f in fix_events or [] if f.get("explicit", True) and f.get("round_id") is not None}
    return sum(1 for round_id in requested if round_id in fixed)


def collect_from_fixture(event: Dict[str, Any]) -> Dict[str, Any]:
    conflicts = event.get("conflicts") or []
    markers = event.get("markers") or []
    ci_runs = event.get("ci_runs") or []
    return {
        "schema_version": 1, "unit_type": "PR", "issue_ref": event.get("issue_ref"), "pr_ref": event.get("pr_ref"),
        "actor": event.get("actor"), "lane": event.get("lane"), "risk": event.get("risk"),
        "timestamps": {"issue_ready_at": first_marker_time(markers, "READY_FOR_IMPLEMENTATION"), "implementation_started_at": first_marker_time(markers, "Status: IMPLEMENTING"), "pr_created_at": event.get("created_at"), "pr_review_ready_at": first_marker_time(markers, "REVIEW_READY"), "pr_merged_at": event.get("merged_at")},
        "metrics": {"clarification_count": sum(1 for e in event.get("clarification_events") or [] if e.get("explicit", True)), "human_confirmation_count": sum(1 for e in event.get("human_confirmation_events") or [] if e.get("explicit", True)), "review_rework_count": count_review_rework(event.get("reviews") or [], event.get("fix_events") or []), "ci_rework_count": count_ci_rework(ci_runs), "conflict_count": len(conflicts), "false_ready_count": sum(1 for marker in markers if marker.get("name") == "FALSE_READY"), "first_pass_ci": first_pass_ci(ci_runs)},
        "blockers": normalize_blockers(conflicts),
        "result": "MERGED" if event.get("merged_at") else ("OPEN" if event.get("pr_ref") else "UNKNOWN"),
        "evidence_refs": [ref for ref in [event.get("pr_ref"), event.get("issue_ref")] if ref],
    }


def main(in_path, out_path=None):
    with open(in_path, "r", encoding="utf-8") as source: event = json.load(source)
    payload = json.dumps(collect_from_fixture(event), ensure_ascii=False, sort_keys=True)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as destination: destination.write(payload + "\n")
    else: print(payload)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2: raise SystemExit("usage: telemetry_collector.py INPUT_JSON [OUTPUT_JSONL]")
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
