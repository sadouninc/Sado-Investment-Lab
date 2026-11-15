from scripts.operational_state_guard import (
    build_auto_green_evidence_fingerprint,
    classify_blocker,
    decide_auto_green_blocker_record,
    evaluate_auto_green_merge,
    mode_contract,
    should_activate_delegated_sora_sm,
    split_away_blockers,
    validate_mode_transition,
)


def _auto_green_evidence(**overrides):
    evidence = {
        "pr_number": 871,
        "head_sha": "a" * 40,
        "ci_state": "PASS",
        "ci_contexts": ["tests", "lint"],
        "technical_review_state": "PASS_WITH_SCOPE",
        "technical_review_evidence_id": "review:123",
        "request_changes": False,
        "unresolved_blockers": ["REQUIRED_REVIEW_POLICY_UNKNOWN"],
        "required_review_policy": "UNKNOWN",
        "required_review_policy_source": "github:403",
        "github_approved": False,
        "github_approval_evidence_id": "github-review:none",
        "mergeable": True,
        "required_gates_pass": True,
        "owner_or_investment_authority": False,
        "path_conflict": False,
        "sensitive_change": False,
        "explicit_owner_acceptance_required": False,
        "protected_issue_79": False,
    }
    evidence.update(overrides)
    return evidence


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
        required_review_policy="PASS",
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
        required_review_policy="PASS",
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
        required_review_policy="PASS",
    )
    assert result.allowed is False
    assert "OWNER_OR_INVESTMENT_AUTHORITY" in result.blocking_reasons
    assert "SENSITIVE_CHANGE" in result.blocking_reasons
    assert "OWNER_ACCEPTANCE_REQUIRED" in result.blocking_reasons


def test_technical_pass_with_scope_does_not_equal_github_approval():
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
        required_review_policy="UNKNOWN",
        github_approved=False,
    )
    assert result.allowed is False
    assert result.blocking_reasons == ("REQUIRED_REVIEW_POLICY_UNKNOWN",)


def test_omitted_required_review_policy_fails_closed():
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
    assert result.allowed is False
    assert result.blocking_reasons == ("REQUIRED_REVIEW_POLICY_UNKNOWN",)


def test_required_github_review_blocks_until_approved():
    arguments = dict(
        mode="AWAY",
        ci_pass=True,
        request_changes=False,
        merge_conflict=False,
        required_gates_pass=True,
        latest_head_reviewed=True,
        owner_or_investment_authority=False,
        sensitive_change=False,
        explicit_owner_acceptance_required=False,
        protected_issue_79=False,
        required_review_policy="REQUIRED",
    )
    assert evaluate_auto_green_merge(**arguments, github_approved=False).blocking_reasons == (
        "GITHUB_APPROVAL_REQUIRED",
    )
    assert evaluate_auto_green_merge(**arguments, github_approved=True).allowed is True


def test_identical_canonical_evidence_suppresses_unchanged_blocker():
    fingerprint = build_auto_green_evidence_fingerprint(**_auto_green_evidence())
    reordered = build_auto_green_evidence_fingerprint(
        **_auto_green_evidence(ci_contexts=["lint", "tests"], unresolved_blockers=["REQUIRED_REVIEW_POLICY_UNKNOWN"])
    )
    assert reordered == fingerprint
    decision = decide_auto_green_blocker_record(
        fingerprint=fingerprint,
        blocking_reasons=["REQUIRED_REVIEW_POLICY_UNKNOWN"],
        previous_fingerprint=fingerprint,
        previous_blocking_reasons=["REQUIRED_REVIEW_POLICY_UNKNOWN"],
    )
    assert decision.action == "SUPPRESS_UNCHANGED_BLOCKER"


def test_changed_evidence_is_reevaluated():
    fingerprint = build_auto_green_evidence_fingerprint(**_auto_green_evidence())
    changes = [
        {"head_sha": "b" * 40},
        {"ci_state": "FAIL"},
        {"technical_review_evidence_id": "review:124"},
        {"required_review_policy": "REQUIRED", "required_review_policy_source": "ruleset:main"},
        {"github_approved": True, "github_approval_evidence_id": "github-review:456"},
        {"owner_or_investment_authority": True},
        {"path_conflict": True},
    ]
    for change in changes:
        changed = build_auto_green_evidence_fingerprint(**_auto_green_evidence(**change))
        decision = decide_auto_green_blocker_record(
            fingerprint=changed,
            blocking_reasons=["REQUIRED_REVIEW_POLICY_UNKNOWN"],
            previous_fingerprint=fingerprint,
            previous_blocking_reasons=["REQUIRED_REVIEW_POLICY_UNKNOWN"],
        )
        assert decision.action == "REEVALUATE_CHANGED_EVIDENCE"


def test_github_approval_grant_and_revocation_change_fingerprint():
    unapproved = build_auto_green_evidence_fingerprint(
        **_auto_green_evidence(
            required_review_policy="REQUIRED",
            required_review_policy_source="ruleset:main",
        )
    )
    approved = build_auto_green_evidence_fingerprint(
        **_auto_green_evidence(
            required_review_policy="REQUIRED",
            required_review_policy_source="ruleset:main",
            github_approved=True,
            github_approval_evidence_id="github-review:456",
        )
    )
    revoked = build_auto_green_evidence_fingerprint(
        **_auto_green_evidence(
            required_review_policy="REQUIRED",
            required_review_policy_source="ruleset:main",
            github_approved=False,
            github_approval_evidence_id="github-review:456:DISMISSED",
        )
    )
    assert len({unapproved, approved, revoked}) == 3


def test_missing_or_malformed_evidence_cannot_suppress():
    try:
        build_auto_green_evidence_fingerprint(**_auto_green_evidence(head_sha=""))
    except ValueError as error:
        assert "incomplete" in str(error)
    else:
        raise AssertionError("missing evidence must fail closed")

    try:
        decide_auto_green_blocker_record(
            fingerprint="malformed",
            blocking_reasons=["CI_NOT_PASS"],
            previous_fingerprint="malformed",
            previous_blocking_reasons=["CI_NOT_PASS"],
        )
    except ValueError as error:
        assert "fingerprint" in str(error)
    else:
        raise AssertionError("malformed marker must not suppress")


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

