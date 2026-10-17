from scripts.sora_recovery_dispatch_gate import decide_dispatch


def inputs():
    return {
        "issue_number": 859, "lease_id": "lease-" + "a" * 32,
        "candidate": {"status": "ALLOW_PRELIMINARY", "issue_number": 859,
                      "dispatch_authorized": False},
        "projection": {"status": "READY", "dispatch_allowed": False, "work_id": "issue:859", "prior_dispatch_count": 0, "attempt": 0},
        "owner_gate": {"status": "APPROVED", "issue_number": 859,
                       "scope": "sora_recovery_dispatch", "verified": True,
                       "owner_comment_id": 42, "lease_id": "lease-" + "a" * 32},
        "evidence_complete": True,
    }


def test_all_independent_gates_required():
    assert decide_dispatch(**inputs())["post_authorized"] is True


def test_unknown_reader_holds():
    data = inputs()
    data["projection"] = {"status": "UNKNOWN", "dispatch_allowed": False}
    assert decide_dispatch(**data)["reason"] == "INVALID_READER_PROJECTION"


def test_owner_approval_must_be_verified():
    data = inputs()
    data["owner_gate"]["verified"] = False
    assert decide_dispatch(**data)["reason"] == "OWNER_APPROVAL_NOT_VERIFIED"


def test_owner_scope_must_match():
    data = inputs()
    data["owner_gate"]["scope"] = "merge"
    assert decide_dispatch(**data)["post_authorized"] is False


def test_issue_79_always_denied():
    data = inputs()
    data["issue_number"] = 79
    assert decide_dispatch(**data)["reason"] == "INVALID_OR_PROTECTED_ISSUE"


def test_incomplete_evidence_denied():
    data = inputs()
    data["evidence_complete"] = False
    assert decide_dispatch(**data)["reason"] == "INCOMPLETE_EVIDENCE"


def test_cross_issue_owner_denied():
    data = inputs()
    data["owner_gate"]["issue_number"] = 860
    assert decide_dispatch(**data)["post_authorized"] is False


def test_prior_dispatch_requires_stop_attestation():
    data = inputs()
    data["projection"].update({"status": "EXPIRED", "prior_dispatch_count": 1, "attempt": 1})
    assert decide_dispatch(**data)["reason"] == "PRIOR_DISPATCH_REQUIRES_STOP_ATTESTATION"


def test_expired_lease_is_not_dispatch_authority():
    data = inputs()
    data["projection"]["status"] = "EXPIRED"
    data["projection"]["prior_dispatch_count"] = 1
    assert decide_dispatch(**data)["post_authorized"] is False


def test_terminal_lease_is_not_dispatch_authority():
    data = inputs()
    data["projection"]["status"] = "DONE"
    data["projection"]["prior_dispatch_count"] = 1
    assert decide_dispatch(**data)["post_authorized"] is False


def test_verified_stop_attestation_allows_gate_to_proceed():
    data = inputs()
    data["projection"].update({"status": "EXPIRED", "prior_dispatch_count": 1, "attempt": 1})
    data["projection"]["stop_attestation"] = {
        "verified": True, "work_id": "issue:859",
        "prior_dispatch_count": 1, "all_prior_executors_stopped": True}
    assert decide_dispatch(**data)["post_authorized"] is True


def test_stale_stop_attestation_cannot_authorize():
    data = inputs()
    data["projection"].update({"status": "EXPIRED", "prior_dispatch_count": 2, "attempt": 2})
    data["projection"]["stop_attestation"] = {
        "verified": True, "work_id": "issue:859",
        "prior_dispatch_count": 1, "all_prior_executors_stopped": True}
    assert decide_dispatch(**data)["post_authorized"] is False


def test_unverified_stop_attestation_cannot_authorize():
    data = inputs()
    data["projection"]["prior_dispatch_count"] = 1
    data["projection"]["stop_attestation"] = {
        "verified": False, "work_id": "issue:859",
        "prior_dispatch_count": 1, "all_prior_executors_stopped": True}
    assert decide_dispatch(**data)["post_authorized"] is False


def test_reader_never_grants_dispatch_authority():
    data = inputs()
    data["projection"]["dispatch_allowed"] = True
    assert decide_dispatch(**data)["reason"] == "INVALID_READER_PROJECTION"


def test_expired_retry_requires_all_previous_stops():
    data = inputs()
    data["projection"].update({"status": "EXPIRED", "prior_dispatch_count": 2, "attempt": 2})
    data["projection"]["stop_attestation"] = {
        "verified": True, "work_id": "issue:859",
        "prior_dispatch_count": 2, "all_prior_executors_stopped": True}
    assert decide_dispatch(**data)["post_authorized"] is True


def test_fourth_expired_attempt_is_retry_limit():
    data = inputs()
    data["projection"].update({"status": "EXPIRED", "prior_dispatch_count": 4, "attempt": 4})
    data["projection"]["stop_attestation"] = {
        "verified": True, "work_id": "issue:859",
        "prior_dispatch_count": 4, "all_prior_executors_stopped": True}
    assert decide_dispatch(**data)["reason"] == "PRIOR_DISPATCH_NOT_RETRYABLE"


def test_active_ack_cannot_redispatch_even_with_stop_attestation():
    data = inputs()
    data["projection"].update({"status": "ACKED", "prior_dispatch_count": 1, "attempt": 1})
    data["projection"]["stop_attestation"] = {
        "verified": True, "work_id": "issue:859",
        "prior_dispatch_count": 1, "all_prior_executors_stopped": True}
    assert decide_dispatch(**data)["post_authorized"] is False


def test_owner_approval_for_different_lease_is_rejected():
    data = inputs()
    data["owner_gate"]["lease_id"] = "lease-" + "b" * 32
    assert decide_dispatch(**data)["reason"] == "OWNER_APPROVAL_NOT_VERIFIED"


def test_owner_approval_requires_comment_identity():
    data = inputs()
    data["owner_gate"]["owner_comment_id"] = None
    assert decide_dispatch(**data)["post_authorized"] is False
