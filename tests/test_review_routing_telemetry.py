from scripts.telemetry_collector import collect_from_fixture


def base_event():
    return {
        "issue_ref": "#647",
        "pr_ref": "#651",
        "actor": "nagi",
        "lane": "flow",
        "risk": "GREEN",
        "created_at": "2026-08-16T08:50:00+09:00",
        "markers": [],
        "ci_runs": [],
        "conflicts": [],
    }


def test_legacy_record_does_not_gain_review_keys_without_review_evidence():
    metrics = collect_from_fixture(base_event())["metrics"]
    assert "blocking_gate_count" not in metrics
    assert "review_wait_age_minutes" not in metrics


def test_review_routing_evidence_projects_into_metrics():
    event = base_event()
    event["review_routing"] = {
        "blocking_gates": ["TECHNICAL"],
        "reviewers": ["technical", "design-fyi", "research-fyi"],
        "review_wait_age_minutes": 70,
        "unnecessary_gate_wait_count": 2,
        "review_reroute_count": 1,
        "carry_forward_gate_count": 2,
    }
    metrics = collect_from_fixture(event)["metrics"]
    assert metrics["blocking_gate_count"] == 1
    assert metrics["review_fanout_count"] == 3
    assert metrics["review_wait_age_minutes"] == 70
    assert metrics["unnecessary_gate_wait_count"] == 2
    assert metrics["review_reroute_count"] == 1
    assert metrics["carry_forward_gate_count"] == 2
