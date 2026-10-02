from scripts.durable_writer import (
    WriteObservation,
    already_landed,
    build_idempotency_key,
    evaluate_landing_gate,
    execute_landing,
    landing_marker,
)


def lease(**overrides):
    value = {
        "expected_head_sha": "head-1",
        "allowed_actions": ["FIX", "TEST", "REBASE"],
        "allowed_paths": ["scripts/", "tests/"],
    }
    value.update(overrides)
    return value


def request(**overrides):
    value = {
        "action": "FIX",
        "current_head_sha": "head-1",
        "paths": ["scripts/example.py", "tests/test_example.py"],
    }
    value.update(overrides)
    return value


def observation(**overrides):
    value = {
        "exact_head_sha": "head-1",
        "observed_head_sha": "head-1",
        "ci_status": "GREEN",
        "unresolved_review_threads": 0,
        "mergeability": "MERGEABLE",
        "authority": "STANDARD",
    }
    value.update(overrides)
    return WriteObservation(**value)


def test_all_evidence_affirmative_is_ready():
    gate = evaluate_landing_gate(lease(), request(), observation())
    assert gate == {"status": "READY", "write_allowed": True, "reason_codes": ()}


def test_lease_and_scope_failures_still_fail_closed():
    assert evaluate_landing_gate(None, request(), observation())["reason_codes"] == ("LEASE_MISSING",)
    stale = evaluate_landing_gate(lease(), request(current_head_sha="head-2"), observation())
    assert stale["reason_codes"] == ("LEASE_STALE",)
    assert evaluate_landing_gate(lease(), request(action="MERGE"), observation())["reason_codes"] == ("RED_BLOCKED",)
    assert evaluate_landing_gate(lease(), request(issue_number=79), observation())["reason_codes"] == ("RED_BLOCKED",)


def test_exact_head_mismatch_fails_closed():
    gate = evaluate_landing_gate(lease(), request(), observation(observed_head_sha="head-2"))
    assert gate["write_allowed"] is False
    assert "EXACT_HEAD_MISMATCH" in gate["reason_codes"]


def test_ci_non_green_fails_closed():
    for status in ("FAILURE", "PENDING", "UNKNOWN", ""):
        gate = evaluate_landing_gate(lease(), request(), observation(ci_status=status))
        assert gate["write_allowed"] is False
        assert "CI_NOT_GREEN" in gate["reason_codes"]


def test_unresolved_review_blocker_and_unknown_both_fail_closed():
    unresolved = evaluate_landing_gate(lease(), request(), observation(unresolved_review_threads=2))
    assert "REVIEW_BLOCKER_UNRESOLVED" in unresolved["reason_codes"]
    unknown = evaluate_landing_gate(lease(), request(), observation(unresolved_review_threads=None))
    assert "REVIEW_BLOCKER_UNKNOWN" in unknown["reason_codes"]


def test_mergeability_unknown_or_blocked_fails_closed():
    unknown = evaluate_landing_gate(lease(), request(), observation(mergeability="UNKNOWN"))
    assert "MERGEABILITY_UNKNOWN" in unknown["reason_codes"]
    conflicting = evaluate_landing_gate(lease(), request(), observation(mergeability="CONFLICTING"))
    assert "MERGEABILITY_BLOCKED" in conflicting["reason_codes"]


def test_authority_ambiguity_fails_closed():
    for authority in ("OWNER_REQUIRED", "PROHIBITED", "UNKNOWN", ""):
        gate = evaluate_landing_gate(lease(), request(), observation(authority=authority))
        assert gate["write_allowed"] is False
        assert "AUTHORITY_AMBIGUOUS" in gate["reason_codes"]


def test_reason_codes_are_deterministically_ordered():
    gate = evaluate_landing_gate(
        lease(),
        request(),
        observation(observed_head_sha="head-2", ci_status="FAILURE", authority="UNKNOWN"),
    )
    assert gate["reason_codes"] == ("EXACT_HEAD_MISMATCH", "CI_NOT_GREEN", "AUTHORITY_AMBIGUOUS")


def test_landing_marker_round_trips_through_already_landed():
    key = "abc123"
    marker = landing_marker(idempotency_key=key)
    assert "idempotency_key=abc123" in marker
    records = [{"body": f"some comment\n{marker}\n"}]
    found = already_landed(records, idempotency_key=key)
    assert found is records[0]
    assert already_landed(records, idempotency_key="other") is None


def test_build_idempotency_key_is_deterministic_and_order_independent_on_paths():
    first = build_idempotency_key(lease_id="lease-1", action="fix", paths=["b.py", "a.py"])
    second = build_idempotency_key(lease_id="lease-1", action="FIX", paths=["a.py", "b.py"])
    assert first == second
    different = build_idempotency_key(lease_id="lease-2", action="fix", paths=["a.py", "b.py"])
    assert different != first


def test_execute_landing_blocks_and_never_writes_when_gate_fails():
    calls = []

    def perform_write(_request):
        calls.append(_request)
        return {"sha": "should-not-happen"}

    result = execute_landing(
        lease=lease(),
        request=request(),
        observation=observation(ci_status="FAILURE"),
        idempotency_key="key-1",
        perform_write=perform_write,
        executed_by="landing-executor-v1",
    )
    assert result["status"] == "FAIL_CLOSED"
    assert result["durable_evidence"] is None
    assert "CI_NOT_GREEN" in result["reason_codes"]
    assert calls == []


def test_execute_landing_persists_durable_evidence_with_attribution():
    def perform_write(_request):
        return {"sha": "deadbeef", "id": 4242}

    result = execute_landing(
        lease=lease(),
        request=request(),
        observation=observation(),
        idempotency_key="key-2",
        perform_write=perform_write,
        executed_by="landing-executor-v1",
    )
    assert result["status"] == "LANDED"
    evidence = result["durable_evidence"]
    assert evidence["sha"] == "deadbeef"
    assert evidence["github_id"] == 4242
    assert evidence["executed_by"] == "landing-executor-v1"
    assert "idempotency_key=key-2" in evidence["marker"]


def test_execute_landing_rejects_write_result_without_id_or_sha():
    def perform_write(_request):
        return {}

    try:
        execute_landing(
            lease=lease(),
            request=request(),
            observation=observation(),
            idempotency_key="key-3",
            perform_write=perform_write,
            executed_by="landing-executor-v1",
        )
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_execute_landing_rerun_promotes_existing_evidence_without_duplicate_write():
    calls = []

    def perform_write(_request):
        calls.append(_request)
        return {"sha": "should-not-happen"}

    marker = landing_marker(idempotency_key="key-4")
    evidence_records = [{"body": marker, "sha": "already-landed-sha"}]

    result = execute_landing(
        lease=lease(),
        request=request(),
        observation=observation(),
        idempotency_key="key-4",
        evidence_records=evidence_records,
        perform_write=perform_write,
        executed_by="landing-executor-v1",
    )
    assert result["status"] == "ALREADY_LANDED"
    assert result["rerun_action"] == "PROMOTE_FOLLOWUP"
    assert result["durable_evidence"]["sha"] == "already-landed-sha"
    assert calls == []


def test_execute_landing_rejects_blank_idempotency_key_or_attribution():
    def perform_write(_request):
        return {"sha": "x"}

    try:
        execute_landing(
            lease=lease(),
            request=request(),
            observation=observation(),
            idempotency_key="  ",
            perform_write=perform_write,
            executed_by="landing-executor-v1",
        )
        assert False, "expected ValueError"
    except ValueError:
        pass

    try:
        execute_landing(
            lease=lease(),
            request=request(),
            observation=observation(),
            idempotency_key="key-5",
            perform_write=perform_write,
            executed_by="  ",
        )
        assert False, "expected ValueError"
    except ValueError:
        pass
