from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from scripts.development_diary_collector import DailyCollector, calc_window, collect_events, persist_snapshot, validate_snapshot

JST = ZoneInfo("Asia/Tokyo")
DAY = date(2026, 8, 19)


def event(kind, ref, at, executor="SORA", task_class="CODE", **extra):
    return {"kind": kind, "ref": ref, "occurred_at": at, "executor": executor, "task_class": task_class, **extra}


def test_jst_half_open_boundary():
    start, end = calc_window(DAY)
    assert start == datetime(2026, 8, 19, 0, 0, tzinfo=JST)
    c = DailyCollector(DAY)
    c.record(event("PR_OPEN", "pr:1", "2026-08-19T14:59:59Z"))  # 23:59:59 JST
    c.record(event("PR_OPEN", "pr:2", "2026-08-19T15:00:00Z"))  # next 00:00 JST
    assert c.pr_opened == 1
    assert end == datetime(2026, 8, 20, 0, 0, tzinfo=JST)


def test_same_event_rerun_is_idempotent():
    e = event("PR_OPEN", "pr:10", "2026-08-19T03:00:00Z")
    c = DailyCollector(DAY)
    c.record(e); c.record(dict(e))
    assert c.pr_opened == 1


def test_dispatch_and_ack_are_not_implementation_start():
    snap = collect_events([
        event("DISPATCHED", "lease:1", "2026-08-19T01:00:00Z"),
        event("ACKED", "lease:1:ack", "2026-08-19T01:01:00Z"),
    ], DAY)
    assert snap["factory_output"]["implementation_start_count"] == 0
    assert snap["executor_performance"][0]["execution_evidence_count"] == 0


def test_execution_evidence_preserves_executor_task_class():
    snap = collect_events([
        event("EXECUTION_EVIDENCE", "commit:a", "2026-08-19T02:00:00Z", executor="SORA", task_class="CODE"),
        event("EXECUTION_EVIDENCE", "commit:b", "2026-08-19T02:01:00Z", executor="SORA", task_class="DOCS"),
    ], DAY)
    rows = {(r["executor"], r["task_class"]): r for r in snap["executor_performance"]}
    assert rows[("SORA", "CODE")]["execution_evidence_count"] == 1
    assert rows[("SORA", "DOCS")]["execution_evidence_count"] == 1
    assert snap["factory_output"]["implementation_start_count"] == 2


def test_unknown_economics_are_null_but_observed_zero_is_zero():
    snap = collect_events([], DAY)
    assert snap["economics"]["copilot_credits"] is None
    assert snap["economics"]["ai_cost_per_merge"] is None
    assert snap["economics"]["paid_fallback_count"] == 0


def test_late_evidence_correction_is_deduplicated():
    c = DailyCollector(DAY)
    late = event("MERGED", "pr:99", "2026-08-19T15:05:00Z", evidence_refs=["pr:#99"])
    recorded = datetime(2026, 8, 20, 0, 20, tzinfo=JST)
    c.add_correction(late, "late evidence", recorded)
    c.add_correction(dict(late), "late evidence replay", recorded)
    assert len(c.corrections) == 1
    assert c.corrections[0]["evidence_refs"] == ["pr:#99"]


def test_schema_metadata_matches_725_authority():
    snap = collect_events([], DAY)
    assert snap["schema_version"] == "1.0"
    assert snap["source_window_start_jst"] == "2026-08-19T00:00:00+09:00"
    assert snap["source_window_end_jst"] == "2026-08-20T00:00:00+09:00"
    validate_snapshot(snap)


def test_invalid_snapshot_does_not_mutate_existing_file(tmp_path: Path):
    target = tmp_path / "2026-08-19.json"
    target.write_text("ORIGINAL\n", encoding="utf-8")
    invalid = collect_events([], DAY)
    invalid["factory_output"]["ready_count"] = -1
    with pytest.raises(Exception):
        persist_snapshot(invalid, target)
    assert target.read_text(encoding="utf-8") == "ORIGINAL\n"


def test_capability_change_is_not_synthesized_as_proven():
    snap = collect_events([], DAY)
    assert snap["factory_capability_changes"] == []
