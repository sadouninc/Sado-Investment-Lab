from scripts.telemetry_collector import collect_from_fixture


def test_operational_mode_metrics_are_projected_without_inference():
    event = {
        "issue_ref": "#642",
        "pr_ref": "#test",
        "operational_mode": {
            "user_mode": "AWAY",
            "merge_policy": "AUTO_GREEN",
            "delegated_flow_activation_count": 3,
            "delegated_flow_steps": None,
            "global_scan_steps": None,
            "shadow_auto_green_evaluated_count": 6,
            "shadow_auto_green_eligible_count": 1,
            "shadow_auto_green_blocked_count": 5,
            "dangerous_false_positive_count": 0,
        },
    }
    metrics = collect_from_fixture(event)["metrics"]
    assert metrics["user_mode"] == "AWAY"
    assert metrics["merge_policy"] == "AUTO_GREEN"
    assert metrics["delegated_flow_activation_count"] == 3
    assert metrics["delegated_flow_steps"] is None
    assert metrics["global_scan_steps"] is None
    assert metrics["shadow_auto_green_evaluated_count"] == 6
    assert metrics["shadow_auto_green_eligible_count"] == 1
    assert metrics["shadow_auto_green_blocked_count"] == 5
    assert metrics["dangerous_false_positive_count"] == 0


def test_absent_operational_mode_preserves_legacy_metric_shape():
    metrics = collect_from_fixture({"issue_ref": "#legacy"})["metrics"]
    assert "user_mode" not in metrics
    assert "dangerous_false_positive_count" not in metrics
