"""Cross-component regression: Reader is observational; retries require all gates.

Fixtures are synthetic and do not constitute authenticated GitHub evidence.
"""
from scripts.recovery_rev2_state_reader import project_state
from scripts.sora_recovery_dispatch_gate import (
    attach_verified_stop_evidence, decide_dispatch,
)

WORK = "issue:859"
OLD = "lease-" + "a" * 32
NEW = "lease-" + "b" * 32


def event(status, comment_id):
    return {"work_id": WORK, "status": status, "comment_id": comment_id,
            "attempt": 1, "lease_id": OLD}


def decision(projection, *, owner_verified=True, complete=True):
    return decide_dispatch(
        issue_number=859, lease_id=NEW,
        candidate={"status": "ALLOW_PRELIMINARY", "issue_number": 859},
        projection=projection,
        owner_gate={"status": "APPROVED", "issue_number": 859,
                    "scope": "sora_recovery_dispatch", "verified": owner_verified,
                    "owner_comment_id": 51, "lease_id": NEW},
        evidence_complete=complete,
    )


def stop_result():
    return {"verified": True, "work_id": WORK, "prior_dispatch_count": 1,
            "all_prior_executors_stopped": True, "stop_comment_ids": [50]}


def test_reader_expiry_never_suffices_without_verified_stop():
    projected = project_state(
        work_id=WORK, events=[event("DISPATCHED", 41), event("EXPIRED", 42)],
        evidence_verified=True)
    assert projected["status"] == "EXPIRED"
    assert projected["dispatch_allowed"] is False
    assert decision(projected)["post_authorized"] is False
    combined = attach_verified_stop_evidence(
        projection=projected, stop_result=stop_result())
    assert combined["dispatch_allowed"] is False
    assert decision(combined)["post_authorized"] is True
    assert decision(combined, owner_verified=False)["post_authorized"] is False
    assert decision(combined, complete=False)["post_authorized"] is False


def test_unverified_reader_history_cannot_be_rescued_by_stop_claim():
    projected = project_state(
        work_id=WORK, events=[event("DISPATCHED", 41), event("EXPIRED", 42)],
        evidence_verified=False)
    combined = attach_verified_stop_evidence(
        projection=projected, stop_result=stop_result())
    assert combined["status"] == "UNKNOWN"
    assert decision(combined)["post_authorized"] is False


def test_acknowledged_or_running_executor_cannot_be_redispatched():
    for status in ("ACKED", "RUNNING", "PR_OPEN"):
        events = [event("DISPATCHED", 41), event(status, 42)]
        if status == "PR_OPEN":
            events[1]["pr_number"] = 860
        projected = project_state(work_id=WORK, events=events, evidence_verified=True)
        combined = attach_verified_stop_evidence(
            projection=projected, stop_result=stop_result())
        assert decision(combined)["post_authorized"] is False


def test_protected_issue_79_cannot_pass_integrated_reader_gate():
    projected = project_state(work_id="issue:79", events=[], evidence_verified=True)
    assert projected["status"] == "BLOCKED"
    assert decide_dispatch(
        issue_number=79, lease_id=NEW,
        candidate={"status": "ALLOW_PRELIMINARY", "issue_number": 79},
        projection=projected,
        owner_gate={"status": "APPROVED", "issue_number": 79,
                    "scope": "sora_recovery_dispatch", "verified": True,
                    "owner_comment_id": 51, "lease_id": NEW},
        evidence_complete=True)["post_authorized"] is False


def test_artifact_to_reader_to_final_gate_is_hold_only():
    """Synthetic linked artifact cannot grant a retry while lease is active."""
    from scripts.recovery_rev2_linked_history import project_authenticated_artifact_inventory
    observed = [{"comment_id": 41, "lease_id": OLD, "writer_run_id": 123}]
    authenticated = [{
        "status": "ATTESTED_LINKAGE", "work_id": WORK,
        "comment_id": 41, "lease_id": OLD, "writer_run_id": 123,
        "dispatch_allowed": False,
    }]
    projection = project_authenticated_artifact_inventory(
        work_id=WORK, observed=observed, authenticated=authenticated,
        complete=True)
    assert projection["status"] == "DISPATCHED"
    assert projection["dispatch_allowed"] is False
    assert decision(projection)["post_authorized"] is False
    assert decision(attach_verified_stop_evidence(
        projection=projection, stop_result=stop_result()))["post_authorized"] is False


def test_partial_artifact_inventory_cannot_be_rescued_by_owner_approval():
    from scripts.recovery_rev2_linked_history import project_authenticated_artifact_inventory
    projection = project_authenticated_artifact_inventory(
        work_id=WORK,
        observed=[{"comment_id": 41, "lease_id": OLD, "writer_run_id": 123}],
        authenticated=[], complete=False)
    assert projection["status"] == "UNKNOWN"
    assert decision(projection)["post_authorized"] is False
