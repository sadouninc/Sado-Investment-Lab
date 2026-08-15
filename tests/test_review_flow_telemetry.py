from scripts.telemetry_collector import collect_from_fixture


def base_event():
    return {
        "issue_ref": "#647",
        "pr_ref": "#648",
        "actor": "nagi",
        "lane": "flow",
        "risk": "GREEN",
        "created_at": "2026-08-16T08:35:00+09:00",
        "markers": [],
        "ci_runs": [],
        "conflicts": [],
    }


def test_legacy_record_does_not_gain_review_flow_keys_without_evidence():
    metrics = collect_from_fixture(base_event())["metrics"]
    assert "blocking_gate_count" not in metrics
    assert "review_wait_age_minutes" not in metrics


def test_review_flow_metrics_are_projected_into_existing_dictionary():
    event = base_event()
    event["review_flow"] = {
        "blocking_gate_count": 1,
        "review_fanout_count": 2,
        "review_wait_age_minutes": 45,
        "unnecessary_gate_wait_count": 0,
        "review_reroute_count": 1,
        "carry_forward_gate_count": 1,
        "specialist_unavailable_count": 1,
        "design_fallback_reroute_count": 1,
        "design_authority_wait_count": 0,
    }
    metrics = collect_from_fixture(event)["metrics"]
    assert metrics["blocking_gate_count"] == 1
    assert metrics["review_fanout_count"] == 2
    assert metrics["review_wait_age_minutes"] == 45
    assert metrics["unnecessary_gate_wait_count"] == 0
    assert metrics["review_reroute_count"] == 1
    assert metrics["carry_forward_gate_count"] == 1
    assert metrics["specialist_unavailable_count"] == 1
    assert metrics["design_fallback_reroute_count"] == 1
    assert metrics["design_authority_wait_count"] == 0
