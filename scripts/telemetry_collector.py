#!/usr/bin/env python3
import json
from typing import Any, Dict, List, Mapping


def normalize_blockers(conflicts: List[str]) -> List[str]:
    mapping = {
        "stale base": "merge_conflict",
        "merge conflict": "merge_conflict",
        "superseded": "superseded",
    }
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


def count_review_rework(reviews, review_fix_events):
    requested_rounds = {
        review.get("round_id")
        for review in reviews or []
        if review.get("event") == "CHANGES_REQUESTED" and review.get("round_id")
    }
    fixed_rounds = {
        fix.get("round_id")
        for fix in review_fix_events or []
        if fix.get("round_id") and fix.get("evidence_ref")
    }
    return len(requested_rounds & fixed_rounds)


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
        if status == "success":
            return "PASS"
        if status == "failure":
            return "FAIL"
    return "UNKNOWN"


def collect_flow_health_metrics(event: Mapping[str, Any]) -> Dict[str, Any]:
    """Project optional #645 SM-flow evidence without changing legacy records."""
    flow = event.get("flow_health")
    if not isinstance(flow, Mapping):
        return {}

    return {
        "active_implementation_wip": flow.get("active_implementation_wip"),
        "waiting_work_count": flow.get("waiting_work_count"),
        "ready_nonconflicting_count": flow.get("ready_nonconflicting_count"),
        "last_durable_output_age_minutes": flow.get("last_durable_output_age_minutes"),
        "dispatch_orphan_count": flow.get("dispatch_orphan_count"),
        "blocked_escape_overdue_count": flow.get("blocked_escape_overdue_count"),
        "flow_stall_state": flow.get("flow_stall_state"),
        "queue_replenish_triggered": flow.get("queue_replenish_triggered"),
        "missed_stall_count": flow.get("missed_stall_count"),
        "flow_false_positive_count": flow.get("flow_false_positive_count"),
    }


def collect_review_flow_metrics(event: Mapping[str, Any]) -> Dict[str, Any]:
    """Project optional #647 review-routing evidence into the #479 metric record."""
    review_flow = event.get("review_flow")
    if not isinstance(review_flow, Mapping):
        return {}

    return {
        "blocking_gate_count": review_flow.get("blocking_gate_count"),
        "review_fanout_count": review_flow.get("review_fanout_count"),
        "review_wait_age_minutes": review_flow.get("review_wait_age_minutes"),
        "unnecessary_gate_wait_count": review_flow.get("unnecessary_gate_wait_count"),
        "review_reroute_count": review_flow.get("review_reroute_count"),
        "carry_forward_gate_count": review_flow.get("carry_forward_gate_count"),
        "specialist_unavailable_count": review_flow.get("specialist_unavailable_count"),
        "design_fallback_reroute_count": review_flow.get("design_fallback_reroute_count"),
        "design_authority_wait_count": review_flow.get("design_authority_wait_count"),
    }


def collect_from_fixture(event: Dict[str, Any]) -> Dict[str, Any]:
    conflicts = event.get("conflicts") or []
    markers = event.get("markers") or []
    ci_runs = event.get("ci_runs") or []
    metrics = {
        "clarification_count": len(event.get("clarification_events") or []),
        "human_confirmation_count": len(event.get("human_confirmation_events") or []),
        "review_rework_count": count_review_rework(
            event.get("reviews"),
            event.get("review_fix_events"),
        ),
        "ci_rework_count": count_ci_rework(ci_runs),
        "conflict_count": len(conflicts),
        "false_ready_count": sum(
            1 for marker in markers if marker.get("name") == "FALSE_READY"
        ),
        "first_pass_ci": first_pass_ci(ci_runs),
    }
    metrics.update(collect_flow_health_metrics(event))
    metrics.update(collect_review_flow_metrics(event))

    return {
        "schema_version": 1,
        "unit_type": "PR",
        "issue_ref": event.get("issue_ref"),
        "pr_ref": event.get("pr_ref"),
        "actor": event.get("actor"),
        "lane": event.get("lane"),
        "risk": event.get("risk"),
        "timestamps": {
            "issue_ready_at": first_marker_time(markers, "READY_FOR_IMPLEMENTATION"),
            "implementation_started_at": first_marker_time(markers, "Status: IMPLEMENTING"),
            "pr_created_at": event.get("created_at"),
            "pr_review_ready_at": first_marker_time(markers, "REVIEW_READY"),
            "pr_merged_at": event.get("merged_at"),
        },
        "metrics": metrics,
        "blockers": normalize_blockers(conflicts),
        "result": (
            "MERGED"
            if event.get("merged_at")
            else ("OPEN" if event.get("pr_ref") else "UNKNOWN")
        ),
        "evidence_refs": [
            ref for ref in [event.get("pr_ref"), event.get("issue_ref")] if ref
        ],
    }


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
