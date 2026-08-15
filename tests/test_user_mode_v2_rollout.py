from scripts.operational_state_guard import (
    evaluate_auto_green_merge,
    should_activate_delegated_sora_sm,
    validate_mode_transition,
)


def test_transition_shadow_matrix():
    cases = [
        ("AWAY", "AWAY", "ACTIVE_MANUAL", "away-to-manual"),
        ("ACTIVE_MANUAL", "ACTIVE_MANUAL", "ACTIVE_AUTO", "manual-to-auto"),
        ("ACTIVE_AUTO", "ACTIVE_AUTO", "ACTIVE_MANUAL", "auto-to-manual"),
    ]
    for current, expected, target, transition_id in cases:
        result = validate_mode_transition(
            current_mode=current,
            expected_current_mode=expected,
            target_mode=target,
            transition_id=transition_id,
        )
        assert result.allowed is True
        assert result.status == "TRANSITION_ALLOWED"


def test_transition_shadow_rejects_stale_and_duplicate():
    stale = validate_mode_transition(
        current_mode="AWAY",
        expected_current_mode="ACTIVE_MANUAL",
        target_mode="ACTIVE_AUTO",
        transition_id="stale",
    )
    assert stale.allowed is False
    assert stale.status == "STALE_EXPECTED_MODE"

    duplicate = validate_mode_transition(
        current_mode="ACTIVE_MANUAL",
        expected_current_mode="ACTIVE_MANUAL",
        target_mode="ACTIVE_AUTO",
        transition_id="same-id",
        last_transition_id="same-id",
    )
    assert duplicate.allowed is False
    assert duplicate.status == "DUPLICATE_TRANSITION_ID"


def test_away_sora_delegation_is_event_driven():
    assert should_activate_delegated_sora_sm(mode="AWAY", trigger="QUEUE_STARVATION") is True
    assert should_activate_delegated_sora_sm(mode="AWAY", trigger="OWNER_CONFLICT") is True
    assert should_activate_delegated_sora_sm(mode="AWAY", trigger="NO_REROUTE_AFTER_BLOCKED_ESCAPE") is True
    assert should_activate_delegated_sora_sm(mode="AWAY", trigger="ORDINARY_IMPLEMENTATION") is False
    assert should_activate_delegated_sora_sm(mode="ACTIVE_AUTO", trigger="QUEUE_STARVATION") is False


def auto_green(**overrides):
    values = dict(
        mode="ACTIVE_AUTO",
        ci_pass=True,
        request_changes=False,
        merge_conflict=False,
        required_gates_pass=True,
        latest_head_reviewed=True,
        owner_or_investment_authority=False,
        sensitive_change=False,
        explicit_owner_acceptance_required=False,
        protected_issue_79=False,
    )
    values.update(overrides)
    return evaluate_auto_green_merge(**values)


def test_auto_green_shadow_low_risk_green_is_eligible():
    result = auto_green()
    assert result.allowed is True
    assert result.status == "AUTO_GREEN_ELIGIBLE"


def test_auto_green_shadow_blocks_missing_design_or_product_gate():
    result = auto_green(required_gates_pass=False)
    assert result.allowed is False
    assert "REQUIRED_GATE_NOT_PASS" in result.blocking_reasons


def test_auto_green_shadow_blocks_ci_failure():
    result = auto_green(ci_pass=False)
    assert result.allowed is False
    assert "CI_NOT_PASS" in result.blocking_reasons


def test_auto_green_shadow_blocks_owner_acceptance():
    result = auto_green(explicit_owner_acceptance_required=True)
    assert result.allowed is False
    assert "OWNER_ACCEPTANCE_REQUIRED" in result.blocking_reasons


def test_auto_green_shadow_blocks_sensitive_change():
    result = auto_green(sensitive_change=True)
    assert result.allowed is False
    assert "SENSITIVE_CHANGE" in result.blocking_reasons


def test_auto_green_shadow_blocks_unknown_review_evidence_fail_closed():
    result = auto_green(latest_head_reviewed=False)
    assert result.allowed is False
    assert "LATEST_HEAD_NOT_REVIEWED" in result.blocking_reasons
