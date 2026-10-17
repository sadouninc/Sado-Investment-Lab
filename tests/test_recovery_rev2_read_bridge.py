"""Read bridge regressions: never grant execution authority."""
import json
from scripts.recovery_rev2_read_bridge import project_attested_comments

def c(status, cid, **fields):
    body = {"schema_version": 2, "work_id": "issue:859",
            "status": status, "attempt": 1,
            "lease_id": "lease-" + "a"*32}
    body.update(fields)
    return {"id": cid, "body": json.dumps(body)}

def project(comments, trusted, verified=True, work="issue:859"):
    return project_attested_comments(work_id=work, comments=comments,
                                     trusted_comment_ids=trusted,
                                     provenance_verified=verified)

def test_attested_ack_blocks_dispatch():
    result = project([c("DISPATCHED", 10), c("ACKED", 11)], {10, 11})
    assert result["status"] == "ACKED" and result["dispatch_allowed"] is False

def test_unverified_provenance():
    assert project([c("DISPATCHED", 10)], {10}, False)["status"] == "UNKNOWN"

def test_attestation_set_mismatch():
    assert project([c("DISPATCHED", 10)], {10, 11})["status"] == "UNKNOWN"

def test_legacy_comment_fails_closed():
    result = project([{"id": 10, "body": "<!-- AUTO_ROUTER_DISPATCH -->"}], {10})
    assert result["status"] == "UNKNOWN"

def test_pr_open_blocks_dispatch():
    # A valid PR_OPEN requires an attested DISPATCHED event for the same lease.
    result = project([c("DISPATCHED", 10), c("PR_OPEN", 11, pr_number=860)], {10, 11})
    assert result["status"] == "PR_OPEN" and result["dispatch_allowed"] is False

def test_orphan_pr_open_fails_closed():
    # A PR_OPEN without the initial DISPATCHED is an invalid history.
    result = project([c("PR_OPEN", 10, pr_number=860)], {10})
    assert result["status"] == "UNKNOWN" and result["dispatch_allowed"] is False

def test_issue_79_hard_deny():
    result = project([], set(), work="issue:79")
    assert result["status"] == "BLOCKED" and result["dispatch_allowed"] is False


def test_duplicate_attested_comment_ids_fail_closed():
    result = project([c("DISPATCHED", 10), c("ACKED", 10)], {10})
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "ATTESTATION_SET_MISMATCH" or result["reason"] == "INVALID_ATTESTED_COMMENT_INVENTORY"
    assert result["dispatch_allowed"] is False


def test_out_of_order_attested_comments_fail_closed():
    result = project([c("ACKED", 11), c("DISPATCHED", 10)], {10, 11})
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "INVALID_ATTESTED_COMMENT_INVENTORY"


def test_invalid_comment_id_fails_closed():
    result = project([c("DISPATCHED", True)], {True})
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "INVALID_ATTESTED_COMMENT_INVENTORY"
