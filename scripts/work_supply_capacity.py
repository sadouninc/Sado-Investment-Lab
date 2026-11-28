"""Read-only offline classifier for #738 work-supply capacity and wait stalls.

Purely evaluates normalized synthetic/offline snapshots without network calls,
wall-clock assumptions, GitHub writes, or dispatch/merge authorization.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from scripts.queue_owner_inventory_pilot import _paths_overlap

PREPARED_TARGET_MIN = 10
PREPARED_TARGET_MAX = 20
PREPARED_REPLENISH_BELOW = 5

READY_TARGET = 10
READY_REPLENISH_MIN = 5
READY_URGENT_MIN = 1

PREPARED_STATES = frozenset({"READY", "NEXT", "RESERVE", "PREPARED"})
ACTIVE_IMPLEMENTATION_STATES = frozenset({
    "IMPLEMENTING",
    "EXECUTION_EVIDENCE",
    "REVISION_REQUIRED",
    "CONFLICT_RESOLUTION",
})
WAIT_STATES = frozenset({
    "PR_OPEN",
    "CI_WAIT",
    "REVIEW_WAIT",
    "MERGE_WAIT",
    "MERGE_READY",
    "DESIGN_GATE_WAIT",
    "RESEARCH_GATE_WAIT",
    "OWNER_WAIT",
    "EXTERNAL_WAIT",
})
BLOCKED_STATES = frozenset({"BLOCKED", "DEPENDENCY_HOLD", "STOP_HOLD"})
KNOWN_ITEM_STATES = PREPARED_STATES | ACTIVE_IMPLEMENTATION_STATES | WAIT_STATES | BLOCKED_STATES


def _is_positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_valid_paths(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) > 0
        and all(isinstance(path, str) and bool(path.strip()) for path in value)
    )


def _parse_iso_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
            parsed = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
        else:
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc)


def _compute_age_hours(as_of_dt: datetime | None, updated_at: Any) -> float | None:
    if as_of_dt is None:
        return None
    updated_dt = _parse_iso_timestamp(updated_at)
    if updated_dt is None or updated_dt > as_of_dt:
        return None
    return round((as_of_dt - updated_dt).total_seconds() / 3600.0, 2)


def _classify_prepared_status(prepared_count: int | None, *, complete: bool) -> str:
    if not complete or prepared_count is None:
        return "UNKNOWN"
    if prepared_count < PREPARED_REPLENISH_BELOW:
        return "REPLENISH"
    if prepared_count < PREPARED_TARGET_MIN:
        return "BELOW_TARGET"
    if prepared_count <= PREPARED_TARGET_MAX:
        return "ON_TARGET"
    return "ABOVE_TARGET"


def _classify_ready_status(verified_ready_count: int | None, *, complete: bool) -> str:
    if not complete or verified_ready_count is None:
        return "UNKNOWN"
    if verified_ready_count == 0:
        return "STARVATION"
    if verified_ready_count < READY_REPLENISH_MIN:
        return "URGENT"
    if verified_ready_count < READY_TARGET:
        return "REPLENISH"
    return "ON_TARGET"


def _incomplete_report(
    *,
    as_of: str | None,
    integrity_errors: list[str],
    duplicate_issues: list[int],
    duplicate_prs: list[int],
    excluded_79_count: int,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "dispatch_allowed": False,
        "merge_authorized": False,
        "issue_79_excluded": True,
        "complete": False,
        "as_of": as_of,
        "prepared_count": None,
        "verified_ready_count": None,
        "prepared_status": "UNKNOWN",
        "ready_replenishment_status": "UNKNOWN",
        "counts": {
            "prepared": None,
            "verified_ready": None,
            "prepared_non_ready": None,
            "active_implementation": None,
            "ci_review_merge_wait": None,
            "dependency_path_blocked": None,
            "unknown": None,
        },
        "issues_by_bucket": {
            "verified_ready": [],
            "prepared_non_ready": [],
            "active_implementation": [],
            "ci_review_merge_wait": [],
            "dependency_path_blocked": [],
            "unknown": [],
        },
        "open_prs_by_bucket": {
            "active_implementation": [],
            "ci_review_merge_wait": [],
            "unknown": [],
        },
        "item_classifications": [],
        "open_pr_classifications": [],
        "age_summary": {
            "as_of_valid": _parse_iso_timestamp(as_of) is not None,
            "max_active_implementation_hours": None,
            "max_ci_review_merge_wait_hours": None,
        },
        "diagnostics": {
            "integrity_errors": sorted(set(integrity_errors)),
            "duplicate_issues": sorted(set(duplicate_issues)),
            "duplicate_prs": sorted(set(duplicate_prs)),
            "excluded_issue_79_count": excluded_79_count,
        },
    }


def _validate_open_prs(
    open_prs: Any,
) -> tuple[list[dict[str, Any]], dict[int, list[dict[str, Any]]], list[str], list[int]]:
    errors: list[str] = []
    duplicate_prs: list[int] = []
    if not isinstance(open_prs, Mapping):
        return [], {}, ["OPEN_PRS_NOT_MAPPING"], duplicate_prs
    if open_prs.get("complete") is not True:
        errors.append("OPEN_PRS_INCOMPLETE")
    prs_raw = open_prs.get("prs")
    if not isinstance(prs_raw, list):
        errors.append("OPEN_PRS_LIST_INVALID")
        return [], {}, errors, duplicate_prs

    seen_prs: set[int] = set()
    normalized_prs: list[dict[str, Any]] = []
    issue_to_prs: dict[int, list[dict[str, Any]]] = {}

    for pr in prs_raw:
        if not isinstance(pr, Mapping) or not _is_positive_int(pr.get("number")):
            errors.append("MALFORMED_OPEN_PR")
            continue
        pr_num = pr["number"]
        if pr_num in seen_prs:
            duplicate_prs.append(pr_num)
            errors.append("DUPLICATE_PR")
            continue
        seen_prs.add(pr_num)
        paths = pr.get("paths")
        if not _is_valid_paths(paths):
            errors.append("MALFORMED_OPEN_PR_PATHS")
            continue

        linked_raw = pr.get("linked_issues", [])
        if linked_raw is None:
            linked_raw = []
        if not isinstance(linked_raw, list) or any(not _is_positive_int(i) for i in linked_raw):
            errors.append("MALFORMED_OPEN_PR_LINKED_ISSUES")
            continue

        wait_state = pr.get("wait_state")
        if wait_state is not None and (not isinstance(wait_state, str) or not wait_state.strip()):
            errors.append("MALFORMED_OPEN_PR_WAIT_STATE")
            continue

        pr_record = {
            "number": pr_num,
            "paths": [p.strip() for p in paths],
            "linked_issues": sorted(set(linked_raw)),
            "wait_state": wait_state.strip() if isinstance(wait_state, str) else None,
            "updated_at": pr.get("updated_at"),
        }
        normalized_prs.append(pr_record)
        for linked_issue in pr_record["linked_issues"]:
            issue_to_prs.setdefault(linked_issue, []).append(pr_record)

    return normalized_prs, issue_to_prs, errors, duplicate_prs


def _validate_items(
    items_raw: Any,
) -> tuple[list[Mapping[str, Any]], list[str], list[int], int]:
    errors: list[str] = []
    duplicate_issues: list[int] = []
    excluded_79_count = 0

    if not isinstance(items_raw, list):
        return [], ["ITEMS_LIST_INVALID"], duplicate_issues, excluded_79_count

    seen_issues: set[int] = set()
    valid_items: list[Mapping[str, Any]] = []
    for item in items_raw:
        if not isinstance(item, Mapping) or not _is_positive_int(item.get("issue")):
            errors.append("MALFORMED_ITEM")
            continue
        issue_num = item["issue"]
        if issue_num in seen_issues:
            duplicate_issues.append(issue_num)
            errors.append("DUPLICATE_ISSUE")
            continue
        seen_issues.add(issue_num)
        if issue_num == 79:
            excluded_79_count += 1
            continue
        valid_items.append(item)

    return valid_items, errors, duplicate_issues, excluded_79_count


def _classify_linked_pr_bucket(
    item_state: str | None,
    linked_prs: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    if item_state in ACTIVE_IMPLEMENTATION_STATES:
        return "active_implementation", ["OPEN_PR_ACTIVE_IMPLEMENTATION"]
    if item_state in WAIT_STATES:
        return "ci_review_merge_wait", ["OPEN_PR_LINKED_WAIT"]

    pr_states = [pr["wait_state"] for pr in linked_prs if pr["wait_state"] is not None]
    if any(s in ACTIVE_IMPLEMENTATION_STATES for s in pr_states):
        return "active_implementation", ["OPEN_PR_REVISION_OR_ACTIVE"]
    if any(s in WAIT_STATES for s in pr_states):
        return "ci_review_merge_wait", ["OPEN_PR_CI_REVIEW_MERGE_WAIT"]
    return "unknown", ["OPEN_PR_WAIT_STATE_UNKNOWN"]


def _classify_item(
    item: Mapping[str, Any],
    *,
    linked_prs: list[dict[str, Any]],
    all_open_pr_paths: list[str],
    active_owners: set[str],
    active_paths: list[str],
    top_stop_active: bool,
    as_of_dt: datetime | None,
) -> tuple[str, bool, list[str]]:
    """Return (bucket, counts_as_prepared, reason_codes)."""
    raw_state = item.get("state")
    state = raw_state.strip() if isinstance(raw_state, str) and raw_state.strip() else None
    has_explicit_pr_ref = _is_positive_int(item.get("open_pr"))

    if linked_prs or has_explicit_pr_ref:
        bucket, reasons = _classify_linked_pr_bucket(state, linked_prs)
        return bucket, False, reasons

    if state in ACTIVE_IMPLEMENTATION_STATES:
        return "active_implementation", False, [f"STATE_{state}"]

    if state in WAIT_STATES:
        return "ci_review_merge_wait", False, [f"STATE_{state}"]

    if state not in KNOWN_ITEM_STATES:
        return "unknown", False, ["STATE_UNKNOWN_OR_INVALID"]

    missing_reasons: list[str] = []
    if not _is_nonempty_str(item.get("owner_slice")):
        missing_reasons.append("MISSING_OWNER_EVIDENCE")
    if not _is_valid_paths(item.get("allowed_paths")):
        missing_reasons.append("MISSING_PATH_EVIDENCE")
    if type(item.get("dependencies_satisfied")) is not bool:
        missing_reasons.append("MISSING_DEPENDENCY_EVIDENCE")
    if type(item.get("stop_clear")) is not bool:
        missing_reasons.append("MISSING_STOP_EVIDENCE")

    if missing_reasons:
        return "unknown", False, missing_reasons

    owner_slice = str(item["owner_slice"]).strip()
    allowed_paths = [p.strip() for p in item["allowed_paths"]]
    dependencies_satisfied = item["dependencies_satisfied"]
    stop_clear = item["stop_clear"]

    block_reasons: list[str] = []
    if top_stop_active or not stop_clear or state == "STOP_HOLD":
        block_reasons.append("STOP_BLOCKED")
    if not dependencies_satisfied or state in BLOCKED_STATES:
        block_reasons.append("DEPENDENCY_BLOCKED")
    if owner_slice in active_owners:
        block_reasons.append("OWNER_CONFLICT")
    if any(_paths_overlap(p, other) for p in allowed_paths for other in all_open_pr_paths):
        block_reasons.append("OPEN_PR_PATH_CONFLICT")
    if any(_paths_overlap(p, other) for p in allowed_paths for other in active_paths):
        block_reasons.append("ACTIVE_PATH_CONFLICT")

    if block_reasons:
        return "dependency_path_blocked", True, block_reasons

    if state == "READY":
        return "verified_ready", True, ["VERIFIED_READY"]
    return "prepared_non_ready", True, [f"PREPARED_{state}"]


def classify_work_supply_capacity(snapshot: Any) -> dict[str, Any]:
    """Classify offline work-supply capacity and stall states fail-closed."""
    if not isinstance(snapshot, Mapping):
        return _incomplete_report(
            as_of=None,
            integrity_errors=["SNAPSHOT_NOT_MAPPING"],
            duplicate_issues=[],
            duplicate_prs=[],
            excluded_79_count=0,
        )

    as_of_raw = snapshot.get("as_of")
    as_of = as_of_raw.strip() if isinstance(as_of_raw, str) and as_of_raw.strip() else None
    as_of_dt = _parse_iso_timestamp(as_of)

    integrity_errors: list[str] = []
    if snapshot.get("complete") is not True:
        integrity_errors.append("SNAPSHOT_INCOMPLETE")

    valid_items, item_errors, duplicate_issues, excluded_79_count = _validate_items(
        snapshot.get("items")
    )
    integrity_errors.extend(item_errors)

    normalized_prs, issue_to_prs, pr_errors, duplicate_prs = _validate_open_prs(
        snapshot.get("open_prs")
    )
    integrity_errors.extend(pr_errors)

    top_stop_active = snapshot.get("stop_active")
    if top_stop_active is not None and type(top_stop_active) is not bool:
        integrity_errors.append("INVALID_STOP_ACTIVE_FLAG")

    if integrity_errors:
        return _incomplete_report(
            as_of=as_of,
            integrity_errors=integrity_errors,
            duplicate_issues=duplicate_issues,
            duplicate_prs=duplicate_prs,
            excluded_79_count=excluded_79_count,
        )

    # Collect active-implementation owners/paths before classifying READY items so
    # conflict checks are order-independent.
    active_owners: set[str] = set()
    active_paths: list[str] = []
    for item in valid_items:
        raw_state = item.get("state")
        state = raw_state.strip() if isinstance(raw_state, str) else ""
        if state in ACTIVE_IMPLEMENTATION_STATES:
            if _is_nonempty_str(item.get("owner_slice")):
                active_owners.add(str(item["owner_slice"]).strip())
            if _is_valid_paths(item.get("allowed_paths")):
                active_paths.extend(p.strip() for p in item["allowed_paths"])

    all_open_pr_paths = [p for pr in normalized_prs for p in pr["paths"]]

    issues_by_bucket: dict[str, list[int]] = {
        "verified_ready": [],
        "prepared_non_ready": [],
        "active_implementation": [],
        "ci_review_merge_wait": [],
        "dependency_path_blocked": [],
        "unknown": [],
    }
    item_classifications: list[dict[str, Any]] = []
    prepared_count = 0
    active_ages: list[float] = []
    wait_ages: list[float] = []

    present_item_issues = {item["issue"] for item in valid_items}
    for item in sorted(valid_items, key=lambda entry: entry["issue"]):
        issue_num = item["issue"]
        linked_prs = list(issue_to_prs.get(issue_num, []))
        if _is_positive_int(item.get("open_pr")):
            explicit_pr = item["open_pr"]
            for pr in normalized_prs:
                if pr["number"] == explicit_pr and pr not in linked_prs:
                    linked_prs.append(pr)

        bucket, is_prepared, reasons = _classify_item(
            item,
            linked_prs=linked_prs,
            all_open_pr_paths=all_open_pr_paths,
            active_owners=active_owners,
            active_paths=active_paths,
            top_stop_active=bool(top_stop_active),
            as_of_dt=as_of_dt,
        )
        if is_prepared:
            prepared_count += 1
        issues_by_bucket[bucket].append(issue_num)
        age_candidates = [
            age
            for age in (
                _compute_age_hours(as_of_dt, item.get("updated_at")),
                *(_compute_age_hours(as_of_dt, pr.get("updated_at")) for pr in linked_prs),
            )
            if age is not None
        ]
        age_hours = max(age_candidates) if age_candidates else None
        if age_hours is not None:
            if bucket == "active_implementation":
                active_ages.append(age_hours)
            elif bucket == "ci_review_merge_wait":
                wait_ages.append(age_hours)

        item_classifications.append({
            "issue": issue_num,
            "bucket": bucket,
            "prepared": is_prepared,
            "reasons": reasons,
            "age_hours": age_hours,
        })

    # Classify standalone open PRs that were not already represented by an item
    # in `items` (excluding #79-only links from capacity readiness).
    open_prs_by_bucket: dict[str, list[int]] = {
        "active_implementation": [],
        "ci_review_merge_wait": [],
        "unknown": [],
    }
    open_pr_classifications: list[dict[str, Any]] = []
    standalone_active_prs = 0
    standalone_wait_prs = 0
    standalone_unknown_prs = 0

    for pr in sorted(normalized_prs, key=lambda entry: entry["number"]):
        wait_state = pr["wait_state"]
        if wait_state in ACTIVE_IMPLEMENTATION_STATES:
            pr_bucket = "active_implementation"
        elif wait_state in WAIT_STATES:
            pr_bucket = "ci_review_merge_wait"
        else:
            pr_bucket = "unknown"

        open_prs_by_bucket[pr_bucket].append(pr["number"])
        pr_age = _compute_age_hours(as_of_dt, pr.get("updated_at"))
        open_pr_classifications.append({
            "pr": pr["number"],
            "bucket": pr_bucket,
            "linked_issues": [n for n in pr["linked_issues"] if n != 79],
            "age_hours": pr_age,
        })

        is_79_only_pr = pr["linked_issues"] == [79]
        represented_in_items = any(n in present_item_issues for n in pr["linked_issues"])
        if not represented_in_items and not is_79_only_pr:
            if pr_bucket == "active_implementation":
                standalone_active_prs += 1
                if pr_age is not None:
                    active_ages.append(pr_age)
            elif pr_bucket == "ci_review_merge_wait":
                standalone_wait_prs += 1
                if pr_age is not None:
                    wait_ages.append(pr_age)
            else:
                standalone_unknown_prs += 1

    verified_ready_count = len(issues_by_bucket["verified_ready"])
    counts = {
        "prepared": prepared_count,
        "verified_ready": verified_ready_count,
        "prepared_non_ready": len(issues_by_bucket["prepared_non_ready"]),
        "active_implementation": len(issues_by_bucket["active_implementation"]) + standalone_active_prs,
        "ci_review_merge_wait": len(issues_by_bucket["ci_review_merge_wait"]) + standalone_wait_prs,
        "dependency_path_blocked": len(issues_by_bucket["dependency_path_blocked"]),
        "unknown": len(issues_by_bucket["unknown"]) + standalone_unknown_prs,
    }

    return {
        "schema_version": 1,
        "dispatch_allowed": False,
        "merge_authorized": False,
        "issue_79_excluded": True,
        "complete": True,
        "as_of": as_of,
        "prepared_count": prepared_count,
        "verified_ready_count": verified_ready_count,
        "prepared_status": _classify_prepared_status(prepared_count, complete=True),
        "ready_replenishment_status": _classify_ready_status(verified_ready_count, complete=True),
        "counts": counts,
        "issues_by_bucket": issues_by_bucket,
        "open_prs_by_bucket": open_prs_by_bucket,
        "item_classifications": item_classifications,
        "open_pr_classifications": open_pr_classifications,
        "age_summary": {
            "as_of_valid": as_of_dt is not None,
            "max_active_implementation_hours": max(active_ages) if active_ages else None,
            "max_ci_review_merge_wait_hours": max(wait_ages) if wait_ages else None,
        },
        "diagnostics": {
            "integrity_errors": [],
            "duplicate_issues": [],
            "duplicate_prs": [],
            "excluded_issue_79_count": excluded_79_count,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only offline classifier for #738 work-supply capacity."
    )
    parser.add_argument("--input", required=True, type=Path, help="Normalized snapshot JSON file")
    parser.add_argument("--output", type=Path, default=None, help="Optional output JSON path")
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        error_report = _incomplete_report(
            as_of=None,
            integrity_errors=[f"INPUT_UNAVAILABLE:{type(exc).__name__}"],
            duplicate_issues=[],
            duplicate_prs=[],
            excluded_79_count=0,
        )
        print(json.dumps(error_report, ensure_ascii=False, sort_keys=True))
        return 2

    report = classify_work_supply_capacity(payload)
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(serialized, encoding="utf-8")
        except OSError:
            error_report = {
                **report,
                "dispatch_allowed": False,
                "merge_authorized": False,
                "diagnostics": {
                    **report["diagnostics"],
                    "integrity_errors": sorted(
                        set(report["diagnostics"]["integrity_errors"]) | {"OUTPUT_UNAVAILABLE"}
                    ),
                },
            }
            print(json.dumps(error_report, ensure_ascii=False, sort_keys=True))
            return 2

    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
