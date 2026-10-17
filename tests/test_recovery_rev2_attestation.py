"""Regression tests for read-only Actions/comment metadata cross-check."""
from scripts.recovery_rev2_attestation import attest_dispatch

WORK = "issue:859"
RUN = {"id": 123, "repository": "sadouninc/Sado-Investment-Lab",
       "workflow": "sora-recovery-control-plane.yml", "event": "schedule",
       "conclusion": "success", "head_sha": "a"*40,
       "created_at": "2026-10-12T10:00:00Z"}
COMMENT = {"id": 45, "created_at": "2026-10-12T10:01:00Z",
           "event": {"schema_version": 2, "work_id": WORK,
                     "dispatch_run_id": 123, "status": "DISPATCHED", "attempt": 1}}

def call(comment=None, run=None, work=WORK):
    return attest_dispatch(work_id=work, comment=COMMENT if comment is None else comment,
                           run=RUN if run is None else run,
                           expected_repository=RUN["repository"],
                           expected_workflow=RUN["workflow"])

def test_matching_metadata_never_proves_provenance():
    x = call()
    assert x["status"] == "METADATA_CONSISTENT_UNVERIFIED"
    assert x["provenance_verified"] is False and x["dispatch_allowed"] is False

def test_wrong_run():
    assert call({**COMMENT, "event": {**COMMENT["event"], "dispatch_run_id": 124}})["status"] == "UNKNOWN"

def test_wrong_repo():
    assert call(run={**RUN, "repository": "attacker/repo"})["status"] == "UNKNOWN"

def test_failed_run():
    assert call(run={**RUN, "conclusion": "failure"})["status"] == "UNKNOWN"

def test_comment_before_run():
    assert call({**COMMENT, "created_at": "2026-10-12T09:59:00Z"})["status"] == "UNKNOWN"

def test_issue79():
    assert call(work="issue:79")["dispatch_allowed"] is False

def test_no_workflow():
    assert call(run={**RUN, "workflow": "other.yml"})["status"] == "UNKNOWN"

def test_invalid_sha():
    assert call(run={**RUN, "head_sha": "xyz"})["status"] == "UNKNOWN"


def native_comment(**overrides):
    import json
    result = {"id": 45, "created_at": COMMENT["created_at"],
              "body": json.dumps(COMMENT["event"])}
    result.update(overrides)
    return result

def native_run(**overrides):
    result = {**RUN,
              "repository": {"full_name": RUN["repository"]},
              "path": ".github/workflows/sora-recovery-control-plane.yml@main",
              "head_branch": "main"}
    result.pop("workflow")
    result.update(overrides)
    return result

def test_native_github_api_payload_consistent_but_unverified():
    result = call(comment=native_comment(), run=native_run())
    assert result["status"] == "METADATA_CONSISTENT_UNVERIFIED"
    assert result["provenance_verified"] is False
    assert result["dispatch_allowed"] is False

def test_native_wrong_head_branch_fails_closed():
    assert call(comment=native_comment(), run=native_run(head_branch="feature"))["status"] == "UNKNOWN"

def test_native_wrong_workflow_path_fails_closed():
    assert call(comment=native_comment(), run=native_run(path=".github/workflows/other.yml@main"))["status"] == "UNKNOWN"

def test_native_malformed_comment_body_fails_closed():
    assert call(comment=native_comment(body="<!-- legacy -->"), run=native_run())["status"] == "UNKNOWN"

def test_native_wrong_repository_fails_closed():
    assert call(comment=native_comment(), run=native_run(repository={"full_name": "attacker/repo"}))["status"] == "UNKNOWN"
