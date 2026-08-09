from scripts.owner_acceptance_gate import GateStatus, evaluate_close_preflight


def test_explicit_owner_gate_without_evidence_blocks_close():
    result = evaluate_close_preflight("Owner Acceptance: REQUIRED", [])
    assert result.owner_gate_required is True
    assert result.status == GateStatus.READY_FOR_OWNER_REVIEW
    assert result.close_allowed is False


def test_explicit_owner_pass_allows_close_and_keeps_evidence_ref():
    result = evaluate_close_preflight(
        "Owner Acceptance: REQUIRED",
        [("comment:42", "Owner Acceptance: PASS\nReviewed by: 👑サド")],
    )
    assert result.status == GateStatus.OWNER_REVIEWED
    assert result.close_allowed is True
    assert result.evidence_ref == "comment:42"


def test_internal_ux_review_is_not_owner_acceptance():
    result = evaluate_close_preflight(
        "Owner Acceptance: REQUIRED",
        [("comment:ux", "⭐️ミナ UX review: PASS")],
    )
    assert result.status == GateStatus.READY_FOR_OWNER_REVIEW
    assert result.close_allowed is False


def test_ci_green_is_not_owner_acceptance():
    result = evaluate_close_preflight(
        "Owner Acceptance: REQUIRED",
        [("check:ci", "CI green. PR Preflight passed.")],
    )
    assert result.status == GateStatus.READY_FOR_OWNER_REVIEW
    assert result.close_allowed is False


def test_review_ready_language_is_not_owner_acceptance():
    result = evaluate_close_preflight(
        "Owner Acceptance: REQUIRED",
        [("comment:ready", "👑サドの実使用レビューに渡せる状態です")],
    )
    assert result.status == GateStatus.READY_FOR_OWNER_REVIEW
    assert result.close_allowed is False


def test_owner_gate_absent_preserves_existing_close_behavior():
    result = evaluate_close_preflight("Implementation complete and tests pass.", [])
    assert result.status == GateStatus.NOT_REQUIRED
    assert result.close_allowed is True


def test_ambiguous_contract_fails_closed():
    result = evaluate_close_preflight(
        "Owner Review may be useful.",
        [],
        contract_ambiguous=True,
    )
    assert result.status == GateStatus.OWNER_ACCEPTANCE_UNVERIFIED
    assert result.close_allowed is False


def test_definition_of_done_checkbox_is_explicit_gate():
    body = "## Definition of Done\n- [ ] 👑サド 実使用レビュー\n"
    result = evaluate_close_preflight(body, [])
    assert result.owner_gate_required is True
    assert result.close_allowed is False
