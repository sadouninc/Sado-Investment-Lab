"""Regression tests for Rev.2 read-only state projection (PR #860)."""
from scripts.recovery_rev2_state_reader import project_state

def event(status, n, **extra):
    return {"work_id": "issue:859", "status": status, "comment_id": n,
            "attempt": 1, "lease_id": "lease-" + "a"*32} | extra

def project(events, verified=True):
    return project_state(work_id="issue:859", events=events, evidence_verified=verified)

def test_unverified_fails_closed():
    assert project([event("DISPATCHED", 1)], False)["status"] == "UNKNOWN"

def test_ready_requires_preflight():
    assert project([])["dispatch_allowed"] is False

def test_ack_blocks_redispatch():
    assert project([event("DISPATCHED", 1), event("ACKED", 2)])["status"] == "ACKED"
    assert project([event("DISPATCHED", 1), event("ACKED", 2)])["dispatch_allowed"] is False

def test_pr_open_blocks_redispatch():
    result = project([event("DISPATCHED", 1), event("PR_OPEN", 2, pr_number=860)])
    assert result["status"] == "PR_OPEN" and result["dispatch_allowed"] is False

def test_merge_blocks_redispatch():
    result = project([event("DISPATCHED", 1), event("MERGED", 2, pr_number=860, merge_sha="b"*40)])
    assert result["status"] == "MERGED" and result["dispatch_allowed"] is False

def test_done_requires_dod():
    assert project([event("DONE", 1)])["status"] == "UNKNOWN"
    assert project([event("DONE", 1, dod_verified=True)])["status"] == "DONE"

def test_duplicate_comment_fails_closed():
    assert project([event("DISPATCHED", 1), event("ACKED", 1)])["status"] == "UNKNOWN"

def test_state_regression_fails_closed():
    assert project([event("PR_OPEN", 1, pr_number=860), event("ACKED", 2)])["status"] == "UNKNOWN"

def test_unknown_event_fails_closed():
    assert project([event("MAGIC", 1)])["status"] == "UNKNOWN"

def test_protected_issue():
    result = project_state(work_id="issue:79", events=[], evidence_verified=True)
    assert result["status"] == "BLOCKED" and result["dispatch_allowed"] is False

def test_retry_limit():
    events = []
    for i in range(1, 5):
        lease = "lease-" + str(i)*32
        events.extend([event("DISPATCHED", 2*i-1, attempt=i, lease_id=lease),
                       event("EXPIRED", 2*i, attempt=i, lease_id=lease)])
    result = project(events)
    assert result["status"] == "BLOCKED" and result["reason"] == "RETRY_LIMIT"
