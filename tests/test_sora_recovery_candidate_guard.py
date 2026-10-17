import json
from scripts.sora_recovery_candidate_guard import check_candidate

BODY = """## Recovery Work Contract — NAGI → SORA
**Priority:** P0 Flow Recovery
**Flow Authority:** 🌙ルナ is Single Flow Authority
**Recovery Engineer:** 🪐ソラ
"""


def issue(n=859, **overrides):
    return {"number": n, "state": "open", "body": BODY, **overrides}


def test_fresh_issue_preliminary_only():
    out = check_candidate(issue(), [], [])
    assert out["status"] == "ALLOW_PRELIMINARY"
    assert out["dispatch_authorized"] is False


def test_issue79_hard_denied():
    assert check_candidate(issue(79), [], [])["status"] == "BLOCKED"


def test_closed_issue_denied():
    assert check_candidate(issue(state="closed"), [], [])["status"] == "BLOCKED"


def test_prior_expired_dispatch_still_held():
    body = '<!-- AUTO_ROUTER_DISPATCH lease_id=lease-' + 'a'*32 + ' executor=SORA target_issue=859 -->\n' + json.dumps({"work_ref":"issue:859", "status":"DISPATCHED", "lease_expires_at":"2000-01-01T00:00:00Z"})
    assert check_candidate(issue(), [{"id":1,"body":body}], [])["status"] == "BLOCKED"


def test_unicode_escaped_work_ref_denied():
    body = '{"work_ref":"issue:\\u0038\\u0035\\u0039", "status":"ACKNOWLEDGED"}'
    assert check_candidate(issue(), [{"id":1,"body":body}], [])["status"] == "BLOCKED"


def test_multiline_rev2_event_denied():
    body = 'header\n' + json.dumps({"work_id":"issue:859","status":"PR_OPEN"}, indent=2) + '\nfooter'
    assert check_candidate(issue(), [{"id":1,"body":body}], [])["status"] == "BLOCKED"


def test_unrelated_issue_event_does_not_block():
    body = json.dumps({"work_ref":"issue:860","status":"ACKNOWLEDGED"})
    assert check_candidate(issue(), [{"id":1,"body":body}], [])["status"] == "ALLOW_PRELIMINARY"


def test_existing_pr_branch_blocks_even_without_issue_in_title():
    prs = [{"number":860,"state":"open","title":"Recovery writer","body":"none", "head":{"ref":"nagi/859-sora-control-plane-writer"}}]
    assert check_candidate(issue(), [], prs)["status"] == "BLOCKED"


def test_other_pr_branch_does_not_block():
    prs = [{"number":861,"state":"open","title":"Other work","body":"none", "head":{"ref":"nagi/860-sora-control-plane-writer"}}]
    assert check_candidate(issue(), [], prs)["status"] == "ALLOW_PRELIMINARY"


def test_malformed_pr_inventory_denied():
    assert check_candidate(issue(), [], [{"number":1,"state":"open","title":"a","head":{"ref":None}}])["status"] == "BLOCKED"


def test_duplicate_comment_ids_denied():
    assert check_candidate(issue(), [{"id":1,"body":""},{"id":1,"body":""}], [])["status"] == "BLOCKED"


def test_oversize_comment_denied():
    assert check_candidate(issue(), [{"id":1,"body":"x"*200001}], [])["status"] == "BLOCKED"


def test_duplicate_pr_numbers_fail_closed():
    pr = {"number": 861, "state": "closed", "title": "Unrelated", "body": "", "head": {"ref": "other"}}
    result = check_candidate(issue(), [], [pr, dict(pr)])
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "DUPLICATE_PR_INVENTORY"


def test_closed_related_pr_blocks_redispatch():
    pr = {"number": 860, "state": "closed", "title": "Recovery writer", "body": "",
          "head": {"ref": "nagi/859-sora-control-plane-writer"},
          "merged_at": "2026-10-01T00:00:00Z"}
    result = check_candidate(issue(), [], [pr])
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "RELATED_PR_EXISTS"


def test_old_flow_authority_rejected():
    old = issue()
    old["body"] = BODY.replace("🌙ルナ", "🌊ナギ")
    result = check_candidate(old, [], [])
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "RECOVERY_CONTRACT_MISSING"


def test_malformed_related_lease_event_fails_closed():
    body = '{"canonical_lease_id":"lease-' + 'a'*32 + '","work_ref":"issue:859",'
    result = check_candidate(issue(), [{"id": 11, "body": body}], [])
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "AMBIGUOUS_RELATED_EVENT"


def test_malformed_unrelated_lease_event_does_not_block():
    body = '{"canonical_lease_id":"lease-' + 'a'*32 + '","work_ref":"issue:860",'
    result = check_candidate(issue(), [{"id": 11, "body": body}], [])
    assert result["status"] == "ALLOW_PRELIMINARY"
