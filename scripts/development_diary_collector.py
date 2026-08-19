"""Deterministic Development Diary daily close collector v1.

Issue #730. The merged #725 JSON schema is the sole snapshot validation authority.
This module normalizes durable evidence into one JST daily snapshot; scheduling and
GitHub fetching remain separate concerns.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import jsonschema

JST = ZoneInfo("Asia/Tokyo")
SCHEMA_VERSION = "1.0"
IMPLEMENTATION_EVIDENCE_KINDS = {"EXECUTION_EVIDENCE", "PR_OPEN", "PR_MERGED"}


def schema_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data/contracts/development-diary-daily-v1.schema.json"


def load_schema() -> dict[str, Any]:
    return json.loads(schema_path().read_text(encoding="utf-8"))


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    validator = jsonschema.Draft202012Validator(
        load_schema(), format_checker=jsonschema.FormatChecker()
    )
    validator.validate(snapshot)


def parse_ts(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return result


def calc_window(diary_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(diary_date, time.min, tzinfo=JST)
    return start, start + timedelta(days=1)


def default_close_time(diary_date: date) -> datetime:
    _, end = calc_window(diary_date)
    return end + timedelta(minutes=10)


def in_window(timestamp: str | datetime, start: datetime, end: datetime) -> bool:
    ts = parse_ts(timestamp).astimezone(JST)
    return start <= ts < end


def _stable_event_id(event: dict[str, Any]) -> str:
    event_id = str(event.get("event_id") or "").strip()
    if not event_id:
        raise ValueError("durable evidence requires non-empty event_id")
    return event_id


def _event_kind(event: dict[str, Any]) -> str:
    kind = str(event.get("kind") or "").strip().upper()
    if not kind:
        raise ValueError("durable evidence requires non-empty kind")
    return kind


def _executor_key(event: dict[str, Any]) -> tuple[str, str]:
    executor = str(event.get("executor") or "UNKNOWN").strip() or "UNKNOWN"
    task_class = str(event.get("task_class") or "UNKNOWN").strip() or "UNKNOWN"
    return executor, task_class


def _new_executor_stats() -> dict[str, Any]:
    return {
        "dispatch_count": 0,
        "ack_count": 0,
        "execution_evidence_count": 0,
        "pr_count": 0,
        "merge_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "terminal_noop_count": 0,
        "elapsed_minutes": None,
        "lead_time_minutes": None,
        "rework_count": 0,
        "duplicate_conflict_waste_count": 0,
    }


def _correction_id(event_id: str) -> str:
    return "corr-" + hashlib.sha256(event_id.encode("utf-8")).hexdigest()[:20]


def _normalize_capability_change(event: dict[str, Any]) -> dict[str, Any]:
    change = deepcopy(event.get("capability_change"))
    if not isinstance(change, dict):
        raise ValueError("FACTORY_CAPABILITY_CHANGE requires capability_change object")
    if change.get("validation_status") not in {"PILOT", "PROVEN", "UNKNOWN"}:
        raise ValueError("invalid capability validation_status")
    change["type"] = "FACTORY_CAPABILITY_CHANGE"
    return change


def _empty_snapshot(diary_date: date, closed_at: datetime) -> dict[str, Any]:
    start, end = calc_window(diary_date)
    return {
        "schema_version": SCHEMA_VERSION,
        "diary_date_jst": diary_date.isoformat(),
        "closed_at_jst": closed_at.astimezone(JST).isoformat(),
        "source_window_start_jst": start.isoformat(),
        "source_window_end_jst": end.isoformat(),
        "factory_output": {
            "ready_count": 0,
            "implementation_start_count": 0,
            "pr_opened": 0,
            "pr_merged": 0,
            "pr_closed_unmerged": 0,
            "durable_output_count": 0,
            "productive_step_count": 0,
            "lead_time_minutes": None,
        },
        "executor_performance": [],
        "flow_health": {
            "active_implementation_wip": 0,
            "waiting_work_count": 0,
            "ready_nonconflicting_count": 0,
            "queue_replenish_latency_minutes": None,
            "path_owner_conflict_count": 0,
            "ci_stall_count": 0,
            "starvation_state": "UNKNOWN",
            "blocked_escape_count": 0,
            "human_intervention_count": 0,
            "durable_output_interval_minutes": None,
        },
        "economics": {
            "free_executor_ratio": None,
            "paid_fallback_count": 0,
            "copilot_usage_count": None,
            "copilot_credits": None,
            "ai_cost_per_accepted_unit": None,
            "ai_cost_per_merge": None,
        },
        "factory_capability_changes": [],
        "corrections": [],
    }


def build_snapshot(
    diary_date: date,
    evidence: Iterable[dict[str, Any]],
    *,
    closed_at: datetime | None = None,
    existing_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema-valid snapshot from normalized durable evidence.

    If ``existing_snapshot`` is supplied, events first observed after its close do
    not silently rewrite historical aggregates. They append one correction audit
    record per stable event identity.
    """
    closed_at = parse_ts(closed_at or default_close_time(diary_date))
    start, end = calc_window(diary_date)
    snapshot = _empty_snapshot(diary_date, closed_at)

    if existing_snapshot is not None:
        validate_snapshot(existing_snapshot)
        expected = (diary_date.isoformat(), start.isoformat(), end.isoformat())
        actual = (
            existing_snapshot["diary_date_jst"],
            existing_snapshot["source_window_start_jst"],
            existing_snapshot["source_window_end_jst"],
        )
        if actual != expected:
            raise ValueError("existing snapshot identity/window mismatch")
        snapshot = deepcopy(existing_snapshot)

    stats: dict[tuple[str, str], dict[str, Any]] = defaultdict(_new_executor_stats)
    if existing_snapshot is not None:
        for row in snapshot["executor_performance"]:
            key = (row["executor"], row["task_class"])
            stats[key] = {
                k: deepcopy(v)
                for k, v in row.items()
                if k not in {"executor", "task_class"}
            }

    seen: set[str] = set()
    existing_correction_ids = {c["correction_id"] for c in snapshot["corrections"]}

    for raw_event in evidence:
        event = deepcopy(raw_event)
        event_id = _stable_event_id(event)
        if event_id in seen:
            continue
        seen.add(event_id)

        occurred_at = event.get("occurred_at")
        if occurred_at is None or not in_window(occurred_at, start, end):
            continue

        if existing_snapshot is not None:
            observed_at = event.get("observed_at")
            if observed_at is not None and parse_ts(observed_at) > parse_ts(existing_snapshot["closed_at_jst"]):
                corr_id = _correction_id(event_id)
                if corr_id not in existing_correction_ids:
                    refs = [str(x) for x in event.get("evidence_refs", []) if str(x)] or [event_id]
                    snapshot["corrections"].append(
                        {
                            "correction_id": corr_id,
                            "reason": str(event.get("correction_reason") or f"late evidence: {event_id}"),
                            "evidence_refs": refs,
                            "recorded_at": parse_ts(observed_at).isoformat(),
                        }
                    )
                    existing_correction_ids.add(corr_id)
                continue

        kind = _event_kind(event)
        key = _executor_key(event)
        row = stats[key]

        if kind == "READY":
            snapshot["factory_output"]["ready_count"] += 1
            if event.get("nonconflicting") is True:
                snapshot["flow_health"]["ready_nonconflicting_count"] += 1
        elif kind == "DISPATCHED":
            row["dispatch_count"] += 1
            snapshot["flow_health"]["waiting_work_count"] += 1
        elif kind == "ACKED":
            row["ack_count"] += 1
        elif kind == "EXECUTION_EVIDENCE":
            row["execution_evidence_count"] += 1
            snapshot["factory_output"]["implementation_start_count"] += 1
            snapshot["flow_health"]["active_implementation_wip"] += 1
        elif kind == "PR_OPEN":
            row["pr_count"] += 1
            snapshot["factory_output"]["pr_opened"] += 1
        elif kind == "PR_MERGED":
            row["merge_count"] += 1
            row["success_count"] += 1
            snapshot["factory_output"]["pr_merged"] += 1
            snapshot["factory_output"]["durable_output_count"] += 1
        elif kind == "PR_CLOSED_UNMERGED":
            row["failure_count"] += 1
            snapshot["factory_output"]["pr_closed_unmerged"] += 1
        elif kind == "TERMINAL_NOOP":
            row["terminal_noop_count"] += 1
        elif kind == "REWORK":
            row["rework_count"] += 1
        elif kind == "DUPLICATE_CONFLICT":
            row["duplicate_conflict_waste_count"] += 1
        elif kind == "PATH_OWNER_CONFLICT":
            snapshot["flow_health"]["path_owner_conflict_count"] += 1
        elif kind == "CI_STALL":
            snapshot["flow_health"]["ci_stall_count"] += 1
        elif kind == "BLOCKED_ESCAPE":
            snapshot["flow_health"]["blocked_escape_count"] += 1
        elif kind == "HUMAN_INTERVENTION":
            snapshot["flow_health"]["human_intervention_count"] += 1
        elif kind == "FACTORY_CAPABILITY_CHANGE":
            snapshot["factory_capability_changes"].append(_normalize_capability_change(event))
        else:
            raise ValueError(f"unsupported durable evidence kind: {kind}")

    snapshot["factory_output"]["productive_step_count"] = (
        snapshot["factory_output"]["implementation_start_count"]
        + snapshot["factory_output"]["pr_opened"]
        + snapshot["factory_output"]["pr_merged"]
    )
    snapshot["executor_performance"] = [
        {"executor": executor, "task_class": task_class, **values}
        for (executor, task_class), values in sorted(stats.items())
        if any(v not in (0, None) for v in values.values())
    ]
    validate_snapshot(snapshot)
    return snapshot


def persist_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    """Validate before atomic replacement; invalid data leaves prior file intact."""
    validate_snapshot(snapshot)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temp_path, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Development Diary daily snapshot v1")
    parser.add_argument("--diary-date", required=True, help="JST date YYYY-MM-DD")
    parser.add_argument("--evidence", required=True, type=Path, help="normalized evidence JSON array")
    parser.add_argument("--output", type=Path, help="defaults to data/development-diary/YYYY-MM-DD.json")
    parser.add_argument("--existing", type=Path, help="optional prior snapshot for late-evidence correction")
    args = parser.parse_args()

    diary_date = date.fromisoformat(args.diary_date)
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    if not isinstance(evidence, list):
        raise ValueError("evidence input must be a JSON array")
    existing = None
    if args.existing:
        existing = json.loads(args.existing.read_text(encoding="utf-8"))
    snapshot = build_snapshot(diary_date, evidence, existing_snapshot=existing)
    output = args.output or Path("data/development-diary") / f"{diary_date.isoformat()}.json"
    persist_snapshot(output, snapshot)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
