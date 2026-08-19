import json
from pathlib import Path

import jsonschema
import pytest


SCHEMA_PATH = Path("data/contracts/development-diary-daily-v1.schema.json")


def schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def valid_snapshot():
    return {
        "schema_version": "1.0",
        "diary_date_jst": "2026-08-19",
        "closed_at_jst": "2026-08-20T00:10:00+09:00",
        "source_window_start_jst": "2026-08-19T00:00:00+09:00",
        "source_window_end_jst": "2026-08-20T00:00:00+09:00",
        "factory_output": {"ready_count": 0, "implementation_start_count": 0, "pr_opened": 0, "pr_merged": 0, "pr_closed_unmerged": 0, "durable_output_count": 0, "productive_step_count": 0, "lead_time_minutes": None},
        "executor_performance": [],
        "flow_health": {"active_implementation_wip": 0, "waiting_work_count": 0, "ready_nonconflicting_count": 0, "queue_replenish_latency_minutes": None, "path_owner_conflict_count": 0, "ci_stall_count": 0, "starvation_state": "NONE", "blocked_escape_count": 0, "human_intervention_count": 0, "durable_output_interval_minutes": None},
        "economics": {"free_executor_ratio": None, "paid_fallback_count": 0, "copilot_usage_count": None, "copilot_credits": None, "ai_cost_per_accepted_unit": None, "ai_cost_per_merge": None},
        "factory_capability_changes": [],
        "corrections": [],
    }


def validate(value):
    jsonschema.Draft202012Validator(schema(), format_checker=jsonschema.FormatChecker()).validate(value)


def test_minimal_snapshot_accepts_unknown_and_observed_zero():
    snap = valid_snapshot()
    validate(snap)
    assert snap["factory_output"]["ready_count"] == 0
    assert snap["factory_output"]["lead_time_minutes"] is None
    assert snap["economics"]["free_executor_ratio"] is None


def test_same_executor_different_task_class_is_lossless():
    snap = valid_snapshot()
    base = {"executor": "JULES", "dispatch_count": 1, "ack_count": 1, "execution_evidence_count": 1, "pr_count": 1, "merge_count": 0, "success_count": 1, "failure_count": 0, "terminal_noop_count": 0, "elapsed_minutes": None, "lead_time_minutes": None, "rework_count": 0, "duplicate_conflict_waste_count": 0}
    snap["executor_performance"] = [{**base, "task_class": "DOCS"}, {**base, "task_class": "CODE"}]
    validate(snap)
    assert [x["task_class"] for x in snap["executor_performance"]] == ["DOCS", "CODE"]


@pytest.mark.parametrize("path,key", [("factory_output", "ready_count"), ("flow_health", "active_implementation_wip")])
def test_negative_counts_rejected(path, key):
    snap = valid_snapshot()
    snap[path][key] = -1
    with pytest.raises(jsonschema.ValidationError):
        validate(snap)


def test_negative_duration_rejected():
    snap = valid_snapshot()
    snap["factory_output"]["lead_time_minutes"] = -0.1
    with pytest.raises(jsonschema.ValidationError):
        validate(snap)


def test_capability_change_requires_evidence_and_known_status():
    snap = valid_snapshot()
    change = {"type": "FACTORY_CAPABILITY_CHANGE", "effective_at": "2026-08-19T09:00:00+09:00", "capability": "Jules production dispatch", "before": "UNAVAILABLE", "after": "AVAILABLE", "evidence_refs": ["issue:#685"], "validation_status": "PROVEN"}
    snap["factory_capability_changes"] = [change]
    validate(snap)
    snap["factory_capability_changes"][0]["evidence_refs"] = []
    with pytest.raises(jsonschema.ValidationError):
        validate(snap)
    snap["factory_capability_changes"][0]["evidence_refs"] = ["issue:#685"]
    snap["factory_capability_changes"][0]["validation_status"] = "CERTAIN"
    with pytest.raises(jsonschema.ValidationError):
        validate(snap)


def test_correction_audit_fields_are_required_and_preserved():
    snap = valid_snapshot()
    correction = {"correction_id": "corr-001", "reason": "late merge evidence", "evidence_refs": ["pr:#1"], "recorded_at": "2026-08-20T00:20:00+09:00"}
    snap["corrections"] = [correction]
    validate(snap)
    assert snap["corrections"][0] == correction
    del snap["corrections"][0]["reason"]
    with pytest.raises(jsonschema.ValidationError):
        validate(snap)


def test_missing_top_level_layer_rejected():
    snap = valid_snapshot()
    del snap["economics"]
    with pytest.raises(jsonschema.ValidationError):
        validate(snap)


def test_ratio_zero_and_unknown_remain_distinct():
    snap = valid_snapshot()
    snap["economics"]["free_executor_ratio"] = 0
    validate(snap)
    assert snap["economics"]["free_executor_ratio"] == 0
    snap["economics"]["free_executor_ratio"] = None
    validate(snap)
    assert snap["economics"]["free_executor_ratio"] is None
