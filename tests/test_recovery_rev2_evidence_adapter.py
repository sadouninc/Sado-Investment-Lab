"""Read-only evidence adapter regressions. No GitHub mutations."""
import json
from scripts.recovery_rev2_evidence_adapter import canonical_event

WORK = "issue:859"
def comment(payload, cid=42):
    return {"id": cid, "body": json.dumps(payload)}
def event(**extra):
    return {"schema_version": 2, "work_id": WORK, "status": "DISPATCHED",
            "attempt": 1, "lease_id": "lease-" + "a"*32, **extra}

def test_attested_canonical_event():
    result = canonical_event(comment(event()), work_id=WORK, trusted_comment_ids={42})
    assert result["comment_id"] == 42 and result["status"] == "DISPATCHED"

def test_unattested_comment_is_unknown():
    result = canonical_event(comment(event()), work_id=WORK, trusted_comment_ids=set())
    assert result["status"] == "UNKNOWN"

def test_legacy_marker_is_unknown():
    result = canonical_event({"id": 42, "body": "<!-- AUTO_ROUTER_DISPATCH -->\n{}"},
                             work_id=WORK, trusted_comment_ids={42})
    assert result["status"] == "UNKNOWN"

def test_wrong_work_is_unknown():
    result = canonical_event(comment(event(work_id="issue:727")), work_id=WORK,
                             trusted_comment_ids={42})
    assert result["status"] == "UNKNOWN"

def test_comment_id_conflict_is_unknown():
    result = canonical_event(comment(event(comment_id=999)), work_id=WORK,
                             trusted_comment_ids={42})
    assert result["status"] == "UNKNOWN"

def test_issue_79_is_protected():
    result = canonical_event(comment(event()), work_id="issue:79", trusted_comment_ids={42})
    assert result["status"] == "BLOCKED"

def test_non_dict_json_is_unknown():
    result = canonical_event({"id": 42, "body": "[]"}, work_id=WORK,
                             trusted_comment_ids={42})
    assert result["status"] == "UNKNOWN"
