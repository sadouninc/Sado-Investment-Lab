"""GitHub metadata correlation never substitutes for durable comment-to-run proof."""
import json
from scripts.recovery_rev2_evidence_adapter import attest_legacy_sora_lease

LEASE = "lease-" + "a" * 32

def sample():
    event = {"work_ref": "issue:859", "canonical_lease_id": LEASE,
             "executor": "SORA", "status": "DISPATCHED", "writer_run_id": 123}
    comment = {"id": 42, "user": {"login": "github-actions[bot]"},
               "created_at": "2026-10-13T10:02:00Z",
               "body": f"<!-- AUTO_ROUTER_DISPATCH lease_id={LEASE} executor=SORA target_issue=859 -->\n" + json.dumps(event)}
    run = {"id": 123, "name": "Sora Recovery Control Plane", "event": "schedule",
           "status": "completed", "conclusion": "success",
           "run_started_at": "2026-10-13T10:00:00Z",
           "updated_at": "2026-10-13T10:05:00Z",
           "repository": {"full_name": "sadouninc/Sado-Investment-Lab"}}
    return comment, run

def check(comment, run):
    return attest_legacy_sora_lease(comment, work_id="issue:859",
        actions_run=run, expected_repository="sadouninc/Sado-Investment-Lab")

def test_matching_metadata_is_still_unverified():
    c, r = sample()
    result = check(c, r)
    assert result["status"] == "REPORTED_UNVERIFIED"
    assert result["dispatch_allowed"] is False

def test_other_comment_author_rejected():
    c, r = sample()
    c["user"]["login"] = "untrusted"
    assert check(c, r)["status"] == "UNKNOWN"

def test_other_repository_rejected():
    c, r = sample()
    r["repository"]["full_name"] = "someone/other"
    assert check(c, r)["status"] == "UNKNOWN"

def test_other_run_rejected():
    c, r = sample()
    r["id"] = 999
    assert check(c, r)["status"] == "UNKNOWN"

def test_failed_run_rejected():
    c, r = sample()
    r["conclusion"] = "failure"
    assert check(c, r)["status"] == "UNKNOWN"

def test_wrong_workflow_rejected():
    c, r = sample()
    r["name"] = "Other workflow"
    assert check(c, r)["status"] == "UNKNOWN"

def test_issue_79_hard_denied():
    c, r = sample()
    result = attest_legacy_sora_lease(c, work_id="issue:79",
        actions_run=r, expected_repository="sadouninc/Sado-Investment-Lab")
    assert result["status"] == "BLOCKED" and result["dispatch_allowed"] is False

def test_comment_before_run_rejected():
    c, r = sample()
    c["created_at"] = "2026-10-13T09:59:59Z"
    assert check(c, r)["reason"] == "COMMENT_RUN_TIME_MISMATCH"

def test_comment_after_run_rejected():
    c, r = sample()
    c["created_at"] = "2026-10-13T10:06:00Z"
    assert check(c, r)["reason"] == "COMMENT_RUN_TIME_MISMATCH"

def test_missing_comment_timestamp_rejected():
    c, r = sample()
    del c["created_at"]
    assert check(c, r)["reason"] == "COMMENT_RUN_TIME_MISMATCH"
