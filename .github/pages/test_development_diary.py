"""Test suite for Development Diary renderer core v1.

Validates rendering contract: schema validation, Japanese-first rendering,
null vs zero distinction, executor×task_class preservation, status treatment,
evidence link safety, corrections separation, and mobile-friendly layout.
"""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest
import jsonschema

MODULE_PATH = Path(__file__).with_name("build_development_diary.py")
spec = importlib.util.spec_from_file_location("build_development_diary", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
render_snapshot = module.render_snapshot


def valid_snapshot():
    return {
        "schema_version": "1.0",
        "diary_date_jst": "2026-08-19",
        "closed_at_jst": "2026-08-20T00:10:00+09:00",
        "source_window_start_jst": "2026-08-19T00:00:00+09:00",
        "source_window_end_jst": "2026-08-20T00:00:00+09:00",
        "factory_output": {
            "ready_count": 1,
            "implementation_start_count": 1,
            "pr_opened": 1,
            "pr_merged": 0,
            "pr_closed_unmerged": 0,
            "durable_output_count": 1,
            "productive_step_count": 2,
            "lead_time_minutes": None,
        },
        "executor_performance": [{
            "executor": "SORA",
            "task_class": "CODE",
            "dispatch_count": 1,
            "ack_count": 1,
            "execution_evidence_count": 1,
            "pr_count": 1,
            "merge_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "terminal_noop_count": 0,
            "elapsed_minutes": None,
            "lead_time_minutes": 0,
            "rework_count": 0,
            "duplicate_conflict_waste_count": 0,
        }],
        "flow_health": {
            "active_implementation_wip": 0,
            "waiting_work_count": 0,
            "ready_nonconflicting_count": 1,
            "queue_replenish_latency_minutes": None,
            "path_owner_conflict_count": 0,
            "ci_stall_count": 0,
            "starvation_state": "OK",
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
        "factory_capability_changes": [
            {
                "type": "FACTORY_CAPABILITY_CHANGE",
                "effective_at": "2026-08-19T12:00:00+09:00",
                "capability": "router-pilot",
                "before": "manual",
                "after": "pilot",
                "evidence_refs": ["https://github.com/sadouninc/Sado-Investment-Lab/issues/727"],
                "validation_status": "PILOT",
            },
            {
                "type": "FACTORY_CAPABILITY_CHANGE",
                "effective_at": "2026-08-19T13:00:00+09:00",
                "capability": "collector",
                "before": "none",
                "after": "validated",
                "evidence_refs": ["pr:#739"],
                "validation_status": "PROVEN",
            },
            {
                "type": "FACTORY_CAPABILITY_CHANGE",
                "effective_at": "2026-08-19T14:00:00+09:00",
                "capability": "unknown-capability",
                "before": "?",
                "after": "?",
                "evidence_refs": ["issue:#999"],
                "validation_status": "UNKNOWN",
            },
        ],
        "corrections": [{
            "correction_id": "corr-1",
            "reason": "late merge evidence",
            "evidence_refs": ["https://github.com/sadouninc/Sado-Investment-Lab/pull/739"],
            "recorded_at": "2026-08-20T00:20:00+09:00",
        }],
    }


def test_minimal_valid_day_renders_all_layers():
    page = render_snapshot(valid_snapshot())
    for text in ["Factory Output", "Executor Performance", "Flow Health", "Economics", "Factory Capability Change", "補正履歴"]:
        assert text in page
    assert "Development Diary — 2026-08-19" in page


def test_null_and_zero_are_distinct():
    page = render_snapshot(valid_snapshot())
    assert "不明 / 未取得" in page
    assert 'data-field="lead_time_minutes">0</dd>' in page


def test_executor_task_class_and_start_semantics_are_preserved():
    page = render_snapshot(valid_snapshot())
    assert "SORA" in page and "CODE" in page
    assert "DISPATCHED / ACKED は予約状態。実装開始は EXECUTION_EVIDENCE から。" in page


def test_capability_statuses_are_visually_and_textually_distinct():
    page = render_snapshot(valid_snapshot())
    assert 'status-pilot">PILOT' in page
    assert 'status-proven">PROVEN' in page
    assert 'status-unknown">UNKNOWN' in page


def test_correction_is_separate_and_evidence_link_is_rendered():
    page = render_snapshot(valid_snapshot())
    assert '<section id="corrections"><h2>補正履歴</h2>' in page
    assert 'href="https://github.com/sadouninc/Sado-Investment-Lab/pull/739"' in page
    assert "late merge evidence" in page


def test_non_url_evidence_is_not_promoted_to_link():
    page = render_snapshot(valid_snapshot())
    assert "<code>pr:#739</code>" in page
    assert 'href="pr:#739"' not in page


def test_required_layer_missing_fails_closed():
    snap = valid_snapshot()
    del snap["economics"]
    with pytest.raises(jsonschema.ValidationError):
        render_snapshot(snap)


def test_malformed_type_fails_closed():
    snap = copy.deepcopy(valid_snapshot())
    snap["factory_output"]["ready_count"] = "one"
    with pytest.raises(jsonschema.ValidationError):
        render_snapshot(snap)


def test_mobile_structure_does_not_require_table_scroll():
    page = render_snapshot(valid_snapshot())
    assert "@media (max-width: 390px)" in page
    assert "grid-template-columns: 1fr" in page
    assert "<table" not in page
    assert 'name="viewport" content="width=device-width, initial-scale=1"' in page
