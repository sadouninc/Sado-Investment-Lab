#!/usr/bin/env python3
import json
from typing import Any, Dict, List


def normalize_blockers(conflicts: List[str]) -> List[str]:
    mapping = {
        "stale base": "merge_conflict",
        "merge conflict": "merge_conflict",
        "superseded": "superseded",
    }
    out = []
    for conflict in conflicts:
        key = conflict.lower().strip()
        out.append(mapping.get(key, conflict))
    return out


def first_marker_time(markers, name):
    for marker in markers or []:
        if marker.get("name") == name:
            return marker.get("at")
    return None


def collect_from_fixture(event: Dict[str, Any]) -> Dict[str, Any]:
    record = {
        "schema_version": 1,
        "unit_type": "PR",
        "issue_ref": event.get("issue_ref"),
        "pr_ref": event.get("pr_ref"),
        "actor": event.get("actor"),
        "lane": None,
        "risk": None,
        "timestamps": {
            "issue_ready_at": first_marker_time(event.get("markers"), "READY_FOR_IMPLEMENTATION"),
            "implementation_started_at": first_marker_time(event.get("markers"), "Status: IMPLEMENTING"),
            "pr_created_at": event.get("created_at"),
            "pr_review_ready_at": first_marker_time(event.get("markers"), "REVIEW_READY"),
            "pr_merged_at": event.get("merged_at"),
        },
        "metrics": {
            "clarification_count": sum(
                1 for review in event.get("reviews", []) if review.get("event") == "CHANGES_REQUESTED"
            ),
            "human_confirmation_count": sum(
                1 for review in event.get("reviews", []) if review.get("event") == "APPROVED"
            ),
            "review_rework_count": sum(
                1 for review in event.get("reviews", []) if review.get("event") == "CHANGES_REQUESTED"
            ),
            "ci_rework_count": sum(
                1 for run in event.get("ci_runs", []) if run.get("status") != "success"
            ),
            "conflict_count": len(event.get("conflicts", [])),
            "false_ready_count": 0,
            "first_pass_ci": "UNKNOWN",
        },
        "blockers": normalize_blockers(event.get("conflicts", [])),
        "result": "MERGED" if event.get("merged_at") else ("OPEN" if event.get("pr_ref") else "UNKNOWN"),
        "evidence_refs": [
            ref for ref in [event.get("pr_ref"), event.get("issue_ref")] if ref
        ],
    }
    ci_runs = event.get("ci_runs") or []
    if ci_runs:
        first = ci_runs[0].get("status")
        record["metrics"]["first_pass_ci"] = "PASS" if first == "success" else "FAIL"
    return record


def main(in_path, out_path=None):
    with open(in_path, "r", encoding="utf-8") as source:
        event = json.load(source)
    record = collect_from_fixture(event)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as destination:
            destination.write(json.dumps(record, ensure_ascii=False) + "\n")
    else:
        print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage: telemetry_collector.py INPUT_JSON [OUTPUT_JSONL]")
        sys.exit(2)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
