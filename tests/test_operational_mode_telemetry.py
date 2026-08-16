from scripts.operational_mode_telemetry import (
    AUTO_GREEN_FIXTURES,
    build_operational_mode_telemetry,
    evaluate_auto_green_fixtures,
    evaluate_delegation_fixtures,
    parse_team_state,
)
from scripts.telemetry_collector import collect_from_fixture


TEAM_STATE = """
## User Mode v2
```yaml
user_mode: AWAY
presence: AWAY
merge_policy: AUTO_GREEN
flow_authority_primary: NAGI
flow_authority_fallback: SORA_DELEGATED
```
"""


def test_parse_team_state_reads_explicit_mode_and_policy():
    assert parse_team_state(TEAM_STATE) == {
        "user_mode": "AWAY",
        "merge_policy": "AUTO_GREEN",
    }


def test_parse_team_state_missing_evidence_remains_unknown():
    assert parse_team_state("user_mode: AWAY\n") == {
        "user_mode": "AWAY",
        "merge_policy": None,
    }


def test_delegation_counts_explicit_fixture_activations_only():
    result = evaluate_delegation_fixtures()
    assert result["delegated_flow_activation_count"] == 3
    assert result["delegated_flow_steps"] is None
    assert result["delegation_fixture_mismatches"] == []


def test_auto_green_shadow_counts_are_reproducible():
    result = evaluate_auto_green_fixtures()
    assert result["shadow_auto_green_evaluated_count"] == len(AUTO_GREEN_FIXTURES) == 6
    assert result["shadow_auto_green_eligible_count"] == 1
    assert result["shadow_auto_green_blocked_count"] == 5
    assert result["dangerous_false_positive_count"] == 0
    assert result["shadow_fixture_mismatches"] == []


def test_expected_block_turning_eligible_is_dangerous_false_positive():
    fixtures = (
        {"name": "bad-expectation", "expected": "BLOCK", "overrides": {}},
    )
    result = evaluate_auto_green_fixtures(fixtures)
    assert result["shadow_auto_green_evaluated_count"] == 1
    assert result["shadow_auto_green_eligible_count"] == 1
    assert result["dangerous_false_positive_count"] == 1
    assert result["shadow_fixture_mismatches"] == ["bad-expectation"]


def test_missing_fixture_expectation_fails_closed_to_unknown_counts():
    result = evaluate_auto_green_fixtures(({"name": "unknown", "overrides": {}},))
    assert result["shadow_auto_green_evaluated_count"] is None
    assert result["dangerous_false_positive_count"] is None


def test_projection_emits_required_nine_metrics_without_zero_filling_unknowns():
    record = build_operational_mode_telemetry(team_state_text=TEAM_STATE)
    metrics = record["metrics"]
    assert set(metrics) == {
        "user_mode",
        "merge_policy",
        "delegated_flow_activation_count",
        "delegated_flow_steps",
        "global_scan_steps",
        "shadow_auto_green_evaluated_count",
        "shadow_auto_green_eligible_count",
        "shadow_auto_green_blocked_count",
        "dangerous_false_positive_count",
    }
    assert metrics["user_mode"] == "AWAY"
    assert metrics["merge_policy"] == "AUTO_GREEN"
    assert metrics["delegated_flow_steps"] is None
    assert metrics["global_scan_steps"] is None


def test_projection_is_deterministic_for_same_input():
    first = build_operational_mode_telemetry(team_state_text=TEAM_STATE)
    second = build_operational_mode_telemetry(team_state_text=TEAM_STATE)
    assert first == second


def test_mode_policy_mismatch_fails_closed():
    inconsistent = "user_mode: ACTIVE_MANUAL\nmerge_policy: AUTO_GREEN\n"
    record = build_operational_mode_telemetry(team_state_text=inconsistent)
    assert record["metrics"]["user_mode"] == "ACTIVE_MANUAL"
    assert record["metrics"]["merge_policy"] is None


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
