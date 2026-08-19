from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import jsonschema
import pytest

from scripts.development_diary_collector import (
    build_snapshot,
    calc_window,
    load_schema,
    persist_snapshot,
    validate_snapshot,
)

JST = ZoneInfo("Asia/Tokyo")
DAY = date(2026, 8, 19)


def ev(event_id, kind, at, **kw):
    return {
        "event_id": event_id,
        "kind": kind,
        "occurred_at": at,
        "executor": kw.pop("executor", "SORA"),
        "task_class": kw.pop("task_class", "IMPLEMENTATION"),
        **kw,
    }


def test_jst_half_open_boundary():
    start, end = calc_window(DAY)
    assert start == datetime(2026, 8, 19, 0, 0, tzinfo=JST)
    assert end == datetime(2026, 8, 20, 0, 0, tzinfo=JST)
    snap = build_snapshot(
        DAY,
        [
            ev("in", "READY", "2026-08-19T23:59:59+09:00", nonconflicting=True),
            ev("out", "READY", "2026-08-20T00:00:00+09:00", nonconflicting=True),
        ],
    )
    assert snap["factory_output"]["ready_count"] == 1
    assert snap["flow_health"]["ready_nonconflicting_count"] == 1


def test_same_evidence_deduplicates_and_rerun_is_semantically_stable():
    evidence = [
        ev("exec-1", "EXECUTION_EVIDENCE", "2026-08-19T10:00:00+09:00"),
        ev("exec-1", "EXECUTION_EVIDENCE", "2026-08-19T10:00:00+09:00"),
    ]
    a = build_snapshot(DAY, evidence)
    b = build_snapshot(DAY, evidence)
    assert a == b
    assert a["factory_output"]["implementation_start_count"] == 1


def test_dispatched_and_acked_do_not_start_implementation():
    snap = build_snapshot(
        DAY,
        [
            ev("d", "DISPATCHED", "2026-08-19T09:00:00+09:00"),
            ev("a", "ACKED", "2026-08-19T09:05:00+09:00"),
        ],
    )
    assert snap["factory_output"]["implementation_start_count"] == 0
    assert snap["flow_health"]["waiting_work_count"] == 1


def test_execution_evidence_preserves_executor_task_class_losslessly():
    snap = build_snapshot(
        DAY,
        [
            ev("e1", "EXECUTION_EVIDENCE", "2026-08-19T10:00:00+09:00", executor="SORA", task_class="CODE"),
            ev("e2", "EXECUTION_EVIDENCE", "2026-08-19T10:01:00+09:00", executor="SORA", task_class="DOCS"),
        ],
    )
    pairs = {(r["executor"], r["task_class"]): r for r in snap["executor_performance"]}
    assert pairs[("SORA", "CODE")]["execution_evidence_count"] == 1
    assert pairs[("SORA", "DOCS")]["execution_evidence_count"] == 1


def test_unavailable_economics_is_null_and_observed_zero_is_zero():
    snap = build_snapshot(DAY, [])
    assert snap["economics"]["copilot_credits"] is None
    assert snap["economics"]["ai_cost_per_merge"] is None
    assert snap["economics"]["paid_fallback_count"] == 0


def test_late_evidence_creates_exactly_one_correction_on_replay():
    existing = build_snapshot(DAY, [])
    late = ev(
        "pr:999:merged",
        "PR_MERGED",
        "2026-08-19T23:00:00+09:00",
        observed_at="2026-08-20T00:20:00+09:00",
        evidence_refs=["pr:#999"],
        correction_reason="late merge evidence",
    )
    once = build_snapshot(DAY, [late], existing_snapshot=existing)
    twice = build_snapshot(DAY, [late, late], existing_snapshot=once)
    assert len(once["corrections"]) == 1
    assert len(twice["corrections"]) == 1
    assert twice["factory_output"]["pr_merged"] == 0


def test_invalid_snapshot_does_not_replace_prior_file(tmp_path: Path):
    path = tmp_path / "2026-08-19.json"
    valid = build_snapshot(DAY, [])
    persist_snapshot(path, valid)
    before = path.read_text(encoding="utf-8")

    invalid = deepcopy(valid)
    invalid["factory_output"]["ready_count"] = -1
    with pytest.raises(jsonschema.ValidationError):
        persist_snapshot(path, invalid)
    assert path.read_text(encoding="utf-8") == before


def test_factory_capability_status_is_preserved_not_promoted():
    snap = build_snapshot(
        DAY,
        [
            ev(
                "cap-1",
                "FACTORY_CAPABILITY_CHANGE",
                "2026-08-19T12:00:00+09:00",
                capability_change={
                    "effective_at": "2026-08-19T12:00:00+09:00",
                    "capability": "daily collector",
                    "before": False,
                    "after": True,
                    "evidence_refs": ["pr:#1"],
                    "validation_status": "PILOT",
                },
            )
        ],
    )
    assert snap["factory_capability_changes"][0]["validation_status"] == "PILOT"


def test_schema_is_merged_725_authority():
    schema = load_schema()
    assert schema["$id"] == "development-diary-daily-v1.schema.json"
    snap = build_snapshot(DAY, [])
    validate_snapshot(snap)
