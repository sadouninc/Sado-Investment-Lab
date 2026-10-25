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


# Normalized synthetic projections only: these fixtures are not real ledger
# records, authenticated GitHub evidence, or operational authorization.
def owner_inventory(claims, **overrides):
    from scripts.recovery_rev2_read_bridge import project_attested_owner_inventory
    arguments = dict(work_id="issue:859", claims=claims,
                     source_refs={name: "synthetic-test-snapshot" for name in
                                  ("issues", "pull_requests", "branches", "actions_runs", "owner_lease_ledger")},
                     coverage_complete=True, provenance_verified=True,
                     freshness_verified=True)
    arguments.update(overrides)
    return project_attested_owner_inventory(**arguments)


def owner_claim(work="issue:859", owner="KAI", state="EXECUTION_EVIDENCE", paths=None):
    return {"work_id": work, "owner": owner, "state": state,
            "paths": paths if paths is not None else ["scripts/recovery_rev2_read_bridge.py"]}


def test_owner_inventory_without_pr_retains_execution_evidence():
    result = owner_inventory([owner_claim()])
    assert result["status"] == "COMPLETE"
    assert result["active_claims"][0]["owner"] == "KAI"
    assert result["active_claims"][0]["active_wip"] is True
    assert result["dispatch_allowed"] is False


def test_attested_complete_empty_owner_inventory_is_distinct_from_unknown():
    result = owner_inventory([])
    assert result["status"] == "COMPLETE_EMPTY"
    assert result["active_claims"] == []
    assert result["dispatch_allowed"] is False
    for overrides in ({"claims": None}, {"source_refs": None},
                      {"coverage_complete": False}, {"provenance_verified": False},
                      {"freshness_verified": False}, {"source_refs": {}}):
        inputs = {"claims": []}
        inputs.update(overrides)
        held = owner_inventory(**inputs)
        assert held["status"] == "UNKNOWN"
        assert held["active_claims"] is None
        assert held["dispatch_allowed"] is False


def test_owner_inventory_comment_or_pr_sources_alone_are_not_complete():
    for references in ({"issues": "comment:123"}, {"pull_requests": "open-prs:0"}):
        held = owner_inventory([], source_refs=references)
        assert held["status"] == "UNKNOWN"
        assert held["active_claims"] is None


def test_waiting_owner_does_not_consume_wip_but_keeps_path_claim():
    result = owner_inventory([owner_claim(state="CI_WAIT")])
    assert result["status"] == "COMPLETE"
    assert result["active_claims"][0]["active_wip"] is False
    assert result["active_claims"][0]["paths"]


def test_conflicting_owner_or_path_inventory_holds():
    for claims in ([owner_claim(), owner_claim(owner="SORA")],
                   [owner_claim(), owner_claim(work="issue:828", owner="SORA")],
                   [owner_claim(paths=["scripts/**"]), owner_claim(work="issue:828")]):
        held = owner_inventory(claims)
        assert held["status"] == "UNKNOWN"
        assert held["active_claims"] is None


def test_invalid_unknown_or_ambiguous_owner_claim_holds():
    for claim in (None, {}, owner_claim(state="UNKNOWN"), owner_claim(state=[]),
                  owner_claim(owner=""), owner_claim(paths=[]),
                  owner_claim(paths=["scripts/recovery_*.py"]), owner_claim(work="issue:79"),
                  owner_claim(paths=["scripts/../tests/a.py"]), owner_claim(paths=["/scripts/a.py"]),
                  owner_claim(paths=["scripts//a.py"])):
        result = owner_inventory([claim])
        assert result["status"] == "UNKNOWN"
        assert result["dispatch_allowed"] is False


def test_owner_inventory_is_deterministic_and_does_not_mutate_input():
    from copy import deepcopy
    claims = [owner_claim(work="issue:860", paths=["tests/b.py"]), owner_claim()]
    original = deepcopy(claims)
    assert owner_inventory(claims) == owner_inventory(list(reversed(claims)))
    assert claims == original


def test_owner_inventory_protected_target_denies_even_complete_empty():
    assert owner_inventory([], work_id="issue:79")["status"] == "BLOCKED"


def test_owner_inventory_requires_literal_true_attestation_flags():
    for field in ("coverage_complete", "provenance_verified", "freshness_verified"):
        for value in (1, "true", None):
            assert owner_inventory([], **{field: value})["status"] == "UNKNOWN"
