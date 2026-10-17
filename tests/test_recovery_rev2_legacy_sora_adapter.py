"""Legacy SORA comment inspection must never grant dispatch authority."""
import json
from scripts.recovery_rev2_evidence_adapter import inspect_legacy_sora_lease

LEASE = "lease-" + "a" * 32

def comment(*, issue=859, lease=LEASE, status="DISPATCHED", run=123, cid=77):
    event = {"work_ref": f"issue:{issue}", "canonical_lease_id": lease,
             "executor": "SORA", "status": status, "writer_run_id": run}
    body = (f"<!-- AUTO_ROUTER_DISPATCH lease_id={lease} executor=SORA target_issue={issue} -->\n"
            + json.dumps(event) + "\n\n担当: ナギ")
    return {"id": cid, "body": body}

def test_valid_legacy_still_unverified():
    result = inspect_legacy_sora_lease(comment(), work_id="issue:859")
    assert result["status"] == "UNVERIFIED"
    assert result["dispatch_allowed"] is False
    assert result["writer_run_id"] == 123
    assert result["comment_id"] == 77

def test_protected_issue_79():
    result = inspect_legacy_sora_lease(comment(issue=79), work_id="issue:79")
    assert result["status"] == "BLOCKED" and result["dispatch_allowed"] is False

def test_wrong_work_id_fails_closed():
    result = inspect_legacy_sora_lease(comment(), work_id="issue:860")
    assert result["status"] == "UNKNOWN" and result["dispatch_allowed"] is False

def test_duplicate_json_fails_closed():
    item = comment()
    item["body"] += "\n" + json.dumps({"status": "MERGED"})
    assert inspect_legacy_sora_lease(item, work_id="issue:859")["status"] == "UNKNOWN"

def test_malformed_json_fails_closed():
    item = comment()
    item["body"] += "\n{bad json"
    assert inspect_legacy_sora_lease(item, work_id="issue:859")["status"] == "UNKNOWN"

def test_mismatched_lease_fails_closed():
    item = comment()
    item["body"] = item["body"].replace('"canonical_lease_id": "' + LEASE + '"',
                                          '"canonical_lease_id": "lease-' + "b" * 32 + '"')
    assert inspect_legacy_sora_lease(item, work_id="issue:859")["status"] == "UNKNOWN"

def test_missing_run_id_fails_closed():
    item = comment(run=0)
    assert inspect_legacy_sora_lease(item, work_id="issue:859")["status"] == "UNKNOWN"
