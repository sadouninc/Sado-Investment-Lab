from scripts.telemetry_collector import collect_from_fixture


def base_event():
    return {
        "issue_ref": "#645",
        "pr_ref": "#646",
        "actor": "nagi",
        "lane": "flow",
        "risk": "GREEN",
        "created_at": "2026-08-16T08:14:00+09:00",
        "markers": [],
        "ci_runs": [],
        "conflicts": [],
    }


def test_legacy_telemetry_record_does_not_gain_flow_keys_without_flow_evidence():
    record = collect_from_fixture(base_event())
    assert "active_implementation_wip" not in record["metrics"]
    assert "flow_stall_state" not in record["metrics"]


def test_flow_health_evidence_projects_into_existing_metrics_dictionary():
    event = base_event()
    event["flow_health"] = {
        "active_implementation_wip": 0,
        "waiting_work_count": 2,
        "ready_nonconflicting_count": 1,
        "last_durable_output_age_minutes": 260,
        "dispatch_orphan_count": 1,
        "blocked_escape_overdue_count": 0,
        "flow_stall_state": "ACTIONED",
        "queue_replenish_triggered": 1,
        "missed_stall_count": 0,
        "flow_false_positive_count": 0,
    }

    metrics = collect_from_fixture(event)["metrics"]
    assert metrics["active_implementation_wip"] == 0
    assert metrics["waiting_work_count"] == 2
    assert metrics["last_durable_output_age_minutes"] == 260
    assert metrics["dispatch_orphan_count"] == 1
    assert metrics["flow_stall_state"] == "ACTIONED"
    assert metrics["queue_replenish_triggered"] == 1
    assert metrics["missed_stall_count"] == 0
    assert metrics["flow_false_positive_count"] == 0
