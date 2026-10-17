"""Rev.2 Reader lease transition integrity regression tests.

担当: 🪐ソラ / #859 / PR #860
"""
from scripts.recovery_rev2_state_reader import project_state

A = "lease-" + "a"*32
B = "lease-" + "b"*32
C = "lease-" + "c"*32
D = "lease-" + "d"*32


def event(status, cid, attempt=1, lease=A, **extra):
    return {"work_id": "issue:859", "status": status, "comment_id": cid,
            "attempt": attempt, "lease_id": lease, **extra}


def project(*events):
    return project_state(work_id="issue:859", events=list(events), evidence_verified=True)


def test_valid_dispatch_ack_and_pr():
    assert project(event("DISPATCHED", 1), event("ACKED", 2),
                   event("PR_OPEN", 3, pr_number=860))["status"] == "PR_OPEN"


def test_valid_expired_retry():
    assert project(event("DISPATCHED", 1), event("EXPIRED", 2),
                   event("DISPATCHED", 3, 2, B))["status"] == "DISPATCHED"


def test_retry_limit_after_four_real_expirations():
    events = []
    for i, lease in enumerate((A, B, C, D), 1):
        events.extend([event("DISPATCHED", 2*i-1, i, lease),
                       event("EXPIRED", 2*i, i, lease)])
    assert project(*events)["reason"] == "RETRY_LIMIT"


def test_duplicate_dispatch_same_attempt_fails():
    assert project(event("DISPATCHED", 1), event("DISPATCHED", 2))["status"] == "UNKNOWN"


def test_changed_lease_same_attempt_fails():
    assert project(event("DISPATCHED", 1), event("ACKED", 2, lease=B))["status"] == "UNKNOWN"


def test_late_ack_after_expiry_fails():
    assert project(event("DISPATCHED", 1), event("EXPIRED", 2),
                   event("ACKED", 3))["status"] == "UNKNOWN"


def test_retry_without_expired_fails():
    assert project(event("DISPATCHED", 1), event("DISPATCHED", 2, 2, B))["status"] == "UNKNOWN"


def test_retry_reuses_lease_fails():
    assert project(event("DISPATCHED", 1), event("EXPIRED", 2),
                   event("DISPATCHED", 3, 2, A))["status"] == "UNKNOWN"


def test_reordered_comments_fail():
    assert project(event("DISPATCHED", 10), event("ACKED", 9))["status"] == "UNKNOWN"


def test_ack_without_dispatch_fails():
    assert project(event("ACKED", 1))["status"] == "UNKNOWN"


def test_retry_after_blocked_fails():
    assert project(event("DISPATCHED", 1), event("BLOCKED", 2),
                   event("DISPATCHED", 3, 2, B))["status"] == "UNKNOWN"


def test_done_standalone_legacy_compat():
    assert project(event("DONE", 1, dod_verified=True))["status"] == "DONE"


def test_pr_open_direct_after_dispatch_compat():
    assert project(event("DISPATCHED", 1),
                   event("PR_OPEN", 2, pr_number=860))["status"] == "PR_OPEN"


def test_merging_direct_after_dispatch_compat():
    assert project(event("DISPATCHED", 1),
                   event("MERGED", 2, pr_number=860, merge_sha="a"*40))["status"] == "MERGED"


def test_nonhex_merge_sha_fails():
    assert project(event("DISPATCHED", 1),
                   event("MERGED", 2, pr_number=860, merge_sha="z"*40))["status"] == "UNKNOWN"


def test_protected_issue_79():
    result = project_state(work_id="issue:79", events=[], evidence_verified=True)
    assert result["status"] == "BLOCKED" and not result["dispatch_allowed"]
