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


def test_incidental_issue_reference_in_unrelated_pr_does_not_block():
    # #873's PR may mention #859 as background, without owning its work.
    prs = [{"number": 882, "state": "open", "title": "#873 scheduled read-only failure preview",
            "body": "Context: #859 remains HOLD; no recovery implementation here.",
            "head": {"ref": "luna/873-read-only-preview"}}]
    result = check_candidate(issue(), [], prs)
    assert result["status"] == "ALLOW_PRELIMINARY"
    assert result["dispatch_authorized"] is False


def test_explicit_closing_reference_in_pr_body_still_blocks():
    prs = [{"number": 883, "state": "open", "title": "Recovery follow-up",
            "body": "Fixes #859", "head": {"ref": "unrelated-branch"}}]
    result = check_candidate(issue(), [], prs)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "RELATED_PR_EXISTS"
    assert result["pr_number"] == 883


def test_explicit_related_pr_title_still_blocks():
    prs = [{"number": 884, "state": "open", "title": "fix: #859 recovery guard",
            "body": "", "head": {"ref": "other-work"}}]
    result = check_candidate(issue(), [], prs)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "RELATED_PR_EXISTS"


def test_auto_router_dispatch_exact_target_blocks_duplicate_start():
    body = "<!-- AUTO_ROUTER_DISPATCH lease_id=lease-" + "a" * 32 + " executor=SORA target_issue=859 -->"
    result = check_candidate(issue(), [{"id": 20, "body": body}], [])
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "PRIOR_DISPATCH_REQUIRES_RECONCILIATION"


def test_auto_router_dispatch_different_numeric_target_is_not_ours():
    # Do not confuse issue 859 with 8590 when scanning unrelated history.
    body = "<!-- AUTO_ROUTER_DISPATCH lease_id=lease-" + "a" * 32 + " executor=SORA target_issue=8590 -->"
    result = check_candidate(issue(), [{"id": 21, "body": body}], [])
    assert result["status"] == "ALLOW_PRELIMINARY"
    assert result["dispatch_authorized"] is False


def test_cross_repository_explicit_closing_reference_still_blocks():
    prs = [{"number": 885, "state": "open", "title": "Follow-up",
            "body": "Resolves sadouninc/Sado-Investment-Lab#859",
            "head": {"ref": "unrelated-branch"}}]
    result = check_candidate(issue(), [], prs)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "RELATED_PR_EXISTS"
    assert result["pr_number"] == 885


def test_pr_882_real_body_incidental_reference_not_owner_linkage():
    prs = [{"number": 882, "state": "open",
            "title": "[Luna] #873: schedule read-only failure preview (POST remains manual-only)",
            "body": "Refs #873. Scope: writer workflow. ♦️ソラ remains Single Implementation Owner for #859. No #860 changes.",
            "head": {"ref": "luna/873-read-only-preview"}}]
    result = check_candidate(issue(), [], prs)
    assert result["status"] == "ALLOW_PRELIMINARY"
    assert result["dispatch_authorized"] is False


def test_explicit_refs_issue_859_blocks_related_pr():
    prs = [{"number": 886, "state": "open", "title": "Recovery implementation",
            "body": "Refs #859.", "head": {"ref": "other-work"}}]
    result = check_candidate(issue(), [], prs)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "RELATED_PR_EXISTS"
    assert result["pr_number"] == 886


def test_explicit_references_cross_repo_issue_859_blocks():
    prs = [{"number": 887, "state": "open", "title": "Recovery follow-up",
            "body": "References sadouninc/Sado-Investment-Lab#859",
            "head": {"ref": "other-work"}}]
    result = check_candidate(issue(), [], prs)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "RELATED_PR_EXISTS"


def test_refs_8590_does_not_match_859():
    prs = [{"number": 888, "state": "open", "title": "Other issue",
            "body": "Refs #8590.", "head": {"ref": "other-work"}}]
    result = check_candidate(issue(), [], prs)
    assert result["status"] == "ALLOW_PRELIMINARY"


def _verified_885_repair():
    return {
        "number": 885,
        "state": "closed",
        "title": "fix(#859): distinguish incidental PR mentions from recovery ownership",
        "body": "Refs #859",
        "head": {
            "ref": "sora/859-hold-only-workflow-regression-20261020",
            "sha": "788cb555d645bd5b3bba2080c03a667d66a466db",
        },
        "base": {"ref": "main"},
        "merged_at": "2026-10-22T23:20:02Z",
        "merge_commit_sha": "f21eecc5bbc1893510964dea28f8d7c14a09db65",
    }


def test_exact_merged_885_completed_slice_only():
    result = check_candidate(issue(), [], [_verified_885_repair()])
    assert result["status"] == "ALLOW_PRELIMINARY"
    assert result["dispatch_authorized"] is False


def test_885_without_authenticated_merge_sha_remains_held():
    pr = _verified_885_repair()
    pr.pop("merge_commit_sha")
    result = check_candidate(issue(), [], [pr])
    assert result["reason"] == "RELATED_PR_EXISTS"


def test_885_with_mismatched_head_sha_remains_held():
    pr = _verified_885_repair()
    pr["head"]["sha"] = "0" * 40
    result = check_candidate(issue(), [], [pr])
    assert result["reason"] == "RELATED_PR_EXISTS"


def test_885_open_or_unmerged_remains_held():
    for field, value in (("state", "open"), ("merged_at", None), ("merged", False)):
        pr = _verified_885_repair()
        pr[field] = value
        result = check_candidate(issue(), [], [pr])
        assert result["reason"] == "RELATED_PR_EXISTS"


def test_885_missing_base_provenance_remains_held():
    pr = _verified_885_repair()
    pr.pop("base")
    result = check_candidate(issue(), [], [pr])
    assert result["reason"] == "RELATED_PR_EXISTS"


def test_885_does_not_hide_other_related_or_incomplete_pr():
    pr_860 = {"number": 860, "state": "closed", "title": "fix(#859): recovery control plane",
              "body": "Refs #859", "head": {"ref": "nagi/859-sora-control-plane-writer"}}
    result = check_candidate(issue(), [], [_verified_885_repair(), pr_860])
    assert result["reason"] == "RELATED_PR_EXISTS"
    assert result["pr_number"] == 860


def test_885_does_not_hide_unreconciled_lease_event():
    comment = {"id": 1, "body": json.dumps({"work_ref": "issue:859", "status": "DISPATCHED"})}
    result = check_candidate(issue(), [comment], [_verified_885_repair()])
    assert result["reason"] == "UNRECONCILED_WORK_EVENT"


def test_885_does_not_override_issue79_hard_deny():
    result = check_candidate(issue(79), [], [_verified_885_repair()])
    assert result["status"] == "BLOCKED"
