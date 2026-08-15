from scripts.operational_state_guard import (
    classify_blocker,
    evaluate_auto_green_merge,
    mode_contract,
    should_activate_delegated_sora_sm,
    split_away_blockers,
    validate_mode_transition,
)


def test_mode_transition_compare_and_set_allows_fresh_transition():
    result = validate_mode_transition(
        current_mode="ACTIVE_MANUAL",
        expected_current_mode="ACTIVE_MANUAL",
        target_mode="AWAY",
        transition_id="2026-08-15T0212+0900-away",
        last_transition_id="previous-active",
    )
    assert result.allowed is True
    assert result.status == "TRANSITION_ALLOWED"


def test_legacy_active_normalizes_to_active_manual():
    assert mode_contract("ACTIVE") == {
        "mode": "ACTIVE_MANUAL",
        "presence": "ACTIVE",
        "merge_policy": "MANUAL",
        "flow_authority": "NAGI",
    }


def test_active_auto_contract_separates_presence_from_merge_policy():
    contract = mode_contract("ACTIVE_AUTO")
    assert contract["presence"] == "ACTIVE"
    assert contract["merge_policy"] == "AUTO_GREEN"
    assert contract["flow_authority"] == "NAGI"


def test_stale_transition_fails_closed():
    result = validate_mode_transition(
        current_mode="ACTIVE_AUTO",
        expected_current_mode="AWAY",
        target_mode="ACTIVE_MANUAL",
        transition_id="stale-active-pr",
    )
    assert result.allowed is False
    assert result.status == "STALE_EXPECTED_MODE"


def test_duplicate_transition_id_fails_closed():
    result = validate_mode_transition(
        current_mode="AWAY",
        expected_current_mode="AWAY",
        target_mode="ACTIVE_AUTO",
        transition_id="same",
        last_transition_id="same",
    )
    assert result.allowed is False
    assert result.status == "DUPLICATE_TRANSITION_ID"


def test_delegated_sora_sm_is_event_driven_only_in_away():
    assert should_activate_delegated_sora_sm(mode="AWAY", trigger="QUEUE_STARVATION") is True
    assert should_activate_delegated_sora_sm(mode="AWAY", trigger="OWNER_CONFLICT") is True
    assert should_activate_delegated_sora_sm(mode="AWAY", trigger="ROUTINE_RUN") is False
    assert should_activate_delegated_sora_sm(mode="ACTIVE_AUTO", trigger="QUEUE_STARVATION") is False


def test_auto_green_allows_only_fully_green_pr_in_auto_mode():
    result = evaluate_auto_green_merge(
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
    assert result.allowed is True
    assert result.status == "AUTO_GREEN_ALLOWED"
    assert result.blocking_reasons == ()


def test_manual_mode_blocks_auto_green_even_when_checks_are_green():
    result = evaluate_auto_green_merge(
        mode="ACTIVE_MANUAL",
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
    assert result.allowed is False
    assert result.blocking_reasons == ("MERGE_POLICY_NOT_AUTO_GREEN",)


def test_auto_green_blocks_authority_and_sensitive_changes():
    result = evaluate_auto_green_merge(
        mode="AWAY",
        ci_pass=True,
        request_changes=False,
        merge_conflict=False,
        required_gates_pass=True,
        latest_head_reviewed=True,
        owner_or_investment_authority=True,
        sensitive_change=True,
        explicit_owner_acceptance_required=True,
        protected_issue_79=False,
    )
    assert result.allowed is False
    assert "OWNER_OR_INVESTMENT_AUTHORITY" in result.blocking_reasons
    assert "SENSITIVE_CHANGE" in result.blocking_reasons
    assert "OWNER_ACCEPTANCE_REQUIRED" in result.blocking_reasons


def test_owner_authority_is_separated_from_autonomous_blockers():
    split = split_away_blockers(
        [
            {"class": "OWNER_AUTHORITY", "detail": "threshold decision", "ref": "#550"},
            {"class": "REVIEW_WAIT", "detail": "design re-gate", "ref": "#584"},
            {"class": "CI_FAILURE", "detail": "tests failed", "ref": "#999"},
        ]
    )
    assert [item["ref"] for item in split["owner_authority"]] == ["#550"]
    assert [item["ref"] for item in split["autonomous"]] == ["#584", "#999"]


def test_unrecognized_blocker_class_is_not_silently_downgraded():
    item = classify_blocker("SOME_NEW_UNMAPPED_CLASS", detail="d", ref="#1")
    assert item["class"] == "UNKNOWN"


def test_unrecognized_blocker_class_fails_closed_into_owner_authority():
    split = split_away_blockers(
        [
            {"class": "TOTALLY_UNKNOWN_CLASS", "detail": "unclassified blocker", "ref": "#601"},
            {"class": "CI_FAILURE", "detail": "tests failed", "ref": "#999"},
        ]
    )
    assert [item["ref"] for item in split["owner_authority"]] == ["#601"]
    assert [item["ref"] for item in split["autonomous"]] == ["#999"]
