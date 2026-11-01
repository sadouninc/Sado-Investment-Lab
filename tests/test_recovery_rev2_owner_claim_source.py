"""Bounded negative and positive fixtures for the read-only #859 source adapter."""
from copy import deepcopy
from datetime import datetime, timezone

from scripts.recovery_rev2_owner_claim_source import DOMAINS, project_owner_claim_source
from scripts.recovery_rev2_owner_claim_source import diagnose_owner_ledger_source


def test_source_diagnostic_reports_candidates_but_never_authorizes():
    result = diagnose_owner_ledger_source(
        repository="sadouninc/Sado-Investment-Lab", workflow_run_id=123,
        artifact_inventory={"total_count": 2, "artifacts": [
            {"id": 1, "name": "owner-lease-ledger", "expired": False},
            {"id": 2, "name": "unrelated", "expired": False}]})
    assert result["reason"] == "SOURCE_UNVERIFIED"
    assert result["candidate_artifacts"] == [{"id": 1, "name": "owner-lease-ledger", "expired": False}]
    assert result["dispatch_allowed"] is False


def test_source_diagnostic_invalid_run_ids_fail_closed():
    for invalid in (None, 0, -1, "not-an-int"):
        result = diagnose_owner_ledger_source(
            repository="sadouninc/Sado-Investment-Lab", workflow_run_id=invalid,
            artifact_inventory={"total_count": 0, "artifacts": []})
        assert result["reason"] == "ACTIONS_RUN_UNVERIFIED"
        assert result["dispatch_allowed"] is False


def test_source_diagnostic_rejects_partial_inventory():
    result = diagnose_owner_ledger_source(
        repository="sadouninc/Sado-Investment-Lab", workflow_run_id=123,
        artifact_inventory={"total_count": 2, "artifacts": []})
    assert result["reason"] == "INCOMPLETE_ARTIFACT_INVENTORY"
    assert result["dispatch_allowed"] is False


def test_source_diagnostic_missing_run_and_protected_work_remains_separate():
    result = diagnose_owner_ledger_source(
        repository="sadouninc/Sado-Investment-Lab", workflow_run_id=None,
        artifact_inventory=None)
    assert result["reason"] == "ACTIONS_RUN_UNVERIFIED"
    assert result["dispatch_allowed"] is False


def test_repository_diagnostic_finds_other_run_candidates_without_authority():
    from scripts.recovery_rev2_owner_claim_source import diagnose_repository_owner_ledger_candidates
    result = diagnose_repository_owner_ledger_candidates(
        repository="sadouninc/Sado-Investment-Lab",
        artifact_inventory={"total_count": 2, "artifacts": [
            {"id": 11, "name": "owner-lease-ledger", "expired": False,
             "workflow_run": {"id": 987}},
            {"id": 12, "name": "other", "workflow_run": {"id": 988}},
        ]})
    assert result["candidate_count"] == 1
    assert result["candidate_artifacts"] == [
        {"id": 11, "name": "owner-lease-ledger", "run_id": 987, "expired": False}]
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "SOURCE_UNVERIFIED"
    assert result["dispatch_allowed"] is False


def test_repository_diagnostic_fails_closed_on_partial_or_duplicate_inventory():
    from scripts.recovery_rev2_owner_claim_source import diagnose_repository_owner_ledger_candidates
    a = {"id": 11, "name": "owner-lease-ledger", "workflow_run": {"id": 987}}
    partial = diagnose_repository_owner_ledger_candidates(
        repository="sadouninc/Sado-Investment-Lab",
        artifact_inventory={"total_count": 2, "artifacts": [a]})
    assert partial["reason"] == "INCOMPLETE_ARTIFACT_INVENTORY"
    duplicate = diagnose_repository_owner_ledger_candidates(
        repository="sadouninc/Sado-Investment-Lab",
        artifact_inventory={"total_count": 2, "artifacts": [a, dict(a)]})
    assert duplicate["reason"] == "DUPLICATE_ARTIFACT_ID"
    assert duplicate["dispatch_allowed"] is False


def test_repository_diagnostic_rejects_unverified_candidate_run():
    from scripts.recovery_rev2_owner_claim_source import diagnose_repository_owner_ledger_candidates
    result = diagnose_repository_owner_ledger_candidates(
        repository="sadouninc/Sado-Investment-Lab",
        artifact_inventory={"total_count": 1, "artifacts": [
            {"id": 11, "name": "lease-ledger", "workflow_run": None}]})
    assert result["reason"] == "CANDIDATE_RUN_UNVERIFIED"
    assert result["candidate_artifacts"] == []
    assert result["dispatch_allowed"] is False



def test_repository_diagnostic_21_candidates_reports_truncation_fail_closed():
    from scripts.recovery_rev2_owner_claim_source import diagnose_repository_owner_ledger_candidates
    artifacts = [
        {"id": i, "name": "owner-lease-ledger", "workflow_run": {"id": 987}}
        for i in range(1, 22)
    ]
    result = diagnose_repository_owner_ledger_candidates(
        repository="sadouninc/Sado-Investment-Lab",
        artifact_inventory={"total_count": 21, "artifacts": artifacts})
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "INCOMPLETE_CANDIDATE_LIST"
    assert result["candidate_count"] == 21
    assert result["returned_count"] == len(result["candidate_artifacts"]) == 20
    assert result["truncated"] is True
    assert result["dispatch_allowed"] is False


def test_repository_diagnostic_1001_total_with_1000_fetched_is_incomplete():
    from scripts.recovery_rev2_owner_claim_source import diagnose_repository_owner_ledger_candidates
    artifacts = [{"id": i, "name": "other"} for i in range(1, 1001)]
    result = diagnose_repository_owner_ledger_candidates(
        repository="sadouninc/Sado-Investment-Lab",
        artifact_inventory={"total_count": 1001, "artifacts": artifacts})
    assert result["reason"] == "INCOMPLETE_ARTIFACT_INVENTORY"
    assert result["candidate_artifacts"] == []
    assert result["dispatch_allowed"] is False


def test_repository_diagnostic_rejects_duplicate_across_page_boundary():
    from scripts.recovery_rev2_owner_claim_source import diagnose_repository_owner_ledger_candidates
    artifacts = [{"id": i, "name": "other"} for i in range(1, 101)]
    artifacts.append({"id": 1, "name": "owner-lease-ledger",
                      "workflow_run": {"id": 987}})
    result = diagnose_repository_owner_ledger_candidates(
        repository="sadouninc/Sado-Investment-Lab",
        artifact_inventory={"total_count": 101, "artifacts": artifacts})
    assert result["reason"] == "DUPLICATE_ARTIFACT_ID"
    assert result["dispatch_allowed"] is False


def test_repository_workflow_has_explicit_page_limit_and_total_drift_guards():
    from pathlib import Path
    workflow = (Path(__file__).resolve().parents[1]
                / ".github/workflows/sora-recovery-control-plane.yml").read_text()
    assert 'repo_total is not None and repo_total != total' in workflow
    assert 'CHANGING_REPOSITORY_ARTIFACT_INVENTORY' in workflow
    assert 'OWNER_LEDGER_REPOSITORY_PAGE_LIMIT_EXCEEDED=INCOMPLETE' in workflow
    assert 'raise ValueError("REPOSITORY_ARTIFACT_PAGE_LIMIT_EXCEEDED")' in workflow
    assert 'raise ValueError("INCOMPLETE_REPOSITORY_ARTIFACT_INVENTORY")' in workflow


NOW = datetime(2026, 10, 28, tzinfo=timezone.utc)


def fixture():
    d = {name: {"items": [], "complete": True, "fresh": True,
                "source_ref": "github:" + name} for name in DOMAINS}
    d["actions_runs"]["items"] = [{"id": 123, "conclusion": "success"}]
    d["owner_lease_ledger"]["items"] = [{
        "work_id": "issue:859", "status": "ACKNOWLEDGED",
        "writer_run_id": 123, "artifact_run_id": 123,
        "run_artifact_verified": True, "issuer": "github-actions",
        "owner": "sora", "lease_id": "test-only",
        "exact_paths": ["scripts/example.py"], "ack_verified": True,
        "expires_at": "2026-10-29T00:00:00Z",
    }]
    return d


def project(d):
    return project_owner_claim_source(work_id="issue:859", domains=d, now=NOW)


def test_verified_snapshot():
    result = project(fixture())
    assert result["status"] == "COMPLETE"
    assert len(result["claims"]) == 1
    assert result["dispatch_allowed"] is False


def test_missing_domain_holds():
    d = fixture()
    del d["branches"]
    assert project(d)["status"] == "UNKNOWN"


def test_partial_pagination_holds():
    d = fixture()
    d["issues"]["complete"] = False
    assert project(d)["reason"] == "INCOMPLETE_PAGINATION"


def test_stale_holds():
    d = fixture()
    d["actions_runs"]["fresh"] = False
    assert project(d)["reason"] == "SOURCE_STALE"


def test_comment_only_claim_holds():
    d = fixture()
    d["owner_lease_ledger"]["items"][0]["run_artifact_verified"] = False
    assert project(d)["reason"] == "ISSUER_RUN_ATTESTATION_MISSING"


def test_wrong_run_holds():
    d = fixture()
    d["owner_lease_ledger"]["items"][0]["artifact_run_id"] = 999
    assert project(d)["status"] == "UNKNOWN"


def test_pre_pr_claim_preserved():
    d = fixture()
    assert d["pull_requests"]["items"] == []
    assert len(project(d)["claims"]) == 1


def test_conflicting_paths_hold():
    d = fixture()
    other = deepcopy(d["owner_lease_ledger"]["items"][0])
    other["lease_id"] = "second-test-only"
    d["owner_lease_ledger"]["items"].append(other)
    assert project(d)["reason"] == "CONFLICTING_OWNER_PATHS"


def test_duplicate_claim_holds():
    d = fixture()
    d["owner_lease_ledger"]["items"].append(deepcopy(d["owner_lease_ledger"]["items"][0]))
    assert project(d)["reason"] == "DUPLICATE_CLAIM"


def test_expired_holds():
    d = fixture()
    d["owner_lease_ledger"]["items"][0]["expires_at"] = "2026-10-27T00:00:00Z"
    assert project(d)["status"] == "UNKNOWN"


def test_unverified_ack_holds():
    d = fixture()
    d["owner_lease_ledger"]["items"][0]["ack_verified"] = False
    assert project(d)["reason"] == "ACK_UNVERIFIED"


def test_protected_issue():
    result = project_owner_claim_source(work_id="issue:79", domains=fixture(), now=NOW)
    assert result["status"] == "BLOCKED"


def test_attested_empty():
    d = fixture()
    d["owner_lease_ledger"]["items"] = []
    assert project(d)["status"] == "COMPLETE_EMPTY"


def test_unknown_issuer_holds():
    d = fixture()
    d["owner_lease_ledger"]["items"][0]["issuer"] = "issue-comment"
    assert project(d)["status"] == "UNKNOWN"


def test_terminal_releases_matching_active_claim():
    d = fixture()
    terminal = deepcopy(d["owner_lease_ledger"]["items"][0])
    terminal["status"] = "RELEASE"
    d["owner_lease_ledger"]["items"].append(terminal)
    result = project(d)
    assert result["status"] == "COMPLETE_EMPTY"
    assert result["claims"] == []
    assert result["dispatch_allowed"] is False


def test_terminal_without_matching_active_holds():
    d = fixture()
    d["owner_lease_ledger"]["items"][0]["status"] = "STOP"
    assert project(d)["reason"] == "UNMATCHED_OR_REPEATED_TERMINAL_EVENT"


def test_terminal_scope_mismatch_holds():
    d = fixture()
    terminal = deepcopy(d["owner_lease_ledger"]["items"][0])
    terminal["status"] = "REVOKED"
    terminal["owner"] = "different-owner"
    d["owner_lease_ledger"]["items"].append(terminal)
    assert project(d)["reason"] == "CONFLICTING_LEASE_OWNER"


def test_active_after_terminal_holds():
    d = fixture()
    terminal = deepcopy(d["owner_lease_ledger"]["items"][0])
    terminal["status"] = "STOP"
    d["owner_lease_ledger"]["items"].extend(
        [terminal, deepcopy(d["owner_lease_ledger"]["items"][0])])
    assert project(d)["reason"] == "ACTIVE_AFTER_TERMINAL_EVENT"


def test_terminal_unverified_run_holds():
    d = fixture()
    terminal = deepcopy(d["owner_lease_ledger"]["items"][0])
    terminal["status"] = "RELEASE"
    terminal["run_artifact_verified"] = False
    d["owner_lease_ledger"]["items"].append(terminal)
    assert project(d)["reason"] == "ISSUER_RUN_ATTESTATION_MISSING"


def test_projection_never_claims_independent_attestation():
    result = project(fixture())
    assert result["reason"] == "PROJECTION_ONLY_EXTERNAL_ATTESTATION_REQUIRED"
    assert result["dispatch_allowed"] is False


def test_collector_paginates_and_still_holds_cross_domain():
    from scripts.recovery_rev2_owner_claim_source import collect_authenticated_owner_claims
    d = fixture()
    calls = []
    def fetch(name, page, per_page):
        calls.append((name, page, per_page))
        data = d[name]["items"]
        if name == "issues" and page == 1:
            return {"items": [{"number": 859}], "source_ref": "page-1",
                    "fresh": True, "next_page": 2}
        return {"items": data if page == 1 else [], "source_ref": "page",
                "fresh": True, "next_page": None}
    result = collect_authenticated_owner_claims(
        work_id="issue:859", fetch_page=fetch,
        verify_run_artifact=lambda claim, run: run["id"] == 123, now=NOW)
    assert ("issues", 2, 100) in calls
    assert result["reason"] == "CROSS_DOMAIN_CLAIM_RECONCILIATION_REQUIRED"
    assert result["dispatch_allowed"] is False


def test_collector_rejects_forged_artifact():
    from scripts.recovery_rev2_owner_claim_source import collect_authenticated_owner_claims
    d = fixture()
    def fetch(name, page, per_page):
        return {"items": d[name]["items"], "source_ref": name,
                "fresh": True, "next_page": None}
    result = collect_authenticated_owner_claims(
        work_id="issue:859", fetch_page=fetch,
        verify_run_artifact=lambda claim, run: False, now=NOW)
    assert result["reason"] == "ISSUER_RUN_ATTESTATION_MISSING"


def test_collector_fails_closed_on_missing_page():
    from scripts.recovery_rev2_owner_claim_source import collect_authenticated_owner_claims
    def fetch(name, page, per_page):
        raise PermissionError("403")
    result = collect_authenticated_owner_claims(
        work_id="issue:859", fetch_page=fetch,
        verify_run_artifact=lambda claim, run: True, now=NOW)
    assert result["reason"] == "SOURCE_FETCH_FAILED"


def test_collector_fails_closed_on_pagination_loop():
    from scripts.recovery_rev2_owner_claim_source import collect_authenticated_owner_claims
    def fetch(name, page, per_page):
        return {"items": [], "source_ref": name, "fresh": True,
                "next_page": page}
    result = collect_authenticated_owner_claims(
        work_id="issue:859", fetch_page=fetch,
        verify_run_artifact=lambda claim, run: True, now=NOW)
    assert result["status"] == "UNKNOWN"


def test_nested_directory_scope_conflict_holds():
    d = fixture()
    other = deepcopy(d["owner_lease_ledger"]["items"][0])
    other["lease_id"] = "second-test-only"
    other["exact_paths"] = ["scripts/example.py/subdir"]
    d["owner_lease_ledger"]["items"].append(other)
    assert project(d)["reason"] == "CONFLICTING_OWNER_PATHS"


def test_parent_directory_scope_conflict_holds():
    d = fixture()
    other = deepcopy(d["owner_lease_ledger"]["items"][0])
    other["lease_id"] = "second-test-only"
    other["exact_paths"] = ["scripts/"]
    d["owner_lease_ledger"]["items"].append(other)
    assert project(d)["reason"] == "CONFLICTING_OWNER_PATHS"


def test_same_lease_different_owner_holds():
    d = fixture()
    other = deepcopy(d["owner_lease_ledger"]["items"][0])
    other["owner"] = "different-owner"
    other["status"] = "ASSIGNED"
    d["owner_lease_ledger"]["items"].append(other)
    assert project(d)["reason"] == "CONFLICTING_LEASE_OWNER"


def test_foreign_pre_pr_claim_is_not_ignored():
    d = fixture()
    foreign = deepcopy(d["owner_lease_ledger"]["items"][0])
    foreign["work_id"] = "issue:999"
    foreign["lease_id"] = "other-test-only"
    d["owner_lease_ledger"]["items"].insert(0, foreign)
    assert d["pull_requests"]["items"] == []
    assert project(d)["reason"] == "ALL_ACTOR_SCOPE_RECONCILIATION_REQUIRED"


def test_conflicting_duplicate_run_id_holds():
    d = fixture()
    d["actions_runs"]["items"].append({"id": 123, "conclusion": "failure"})
    assert project(d)["reason"] == "CONFLICTING_ACTIONS_RUN_RECORDS"


def test_collector_requires_foreign_claim_attestation():
    from scripts.recovery_rev2_owner_claim_source import collect_authenticated_owner_claims
    d = fixture()
    foreign = deepcopy(d["owner_lease_ledger"]["items"][0])
    foreign["work_id"] = "issue:999"
    foreign["lease_id"] = "other-test-only"
    d["owner_lease_ledger"]["items"].append(foreign)
    def fetch(name, page, per_page):
        return {"items": d[name]["items"], "source_ref": name,
                "fresh": True, "next_page": None}
    result = collect_authenticated_owner_claims(
        work_id="issue:859", fetch_page=fetch,
        verify_run_artifact=lambda claim, run: claim["work_id"] == "issue:859",
        now=NOW)
    assert result["reason"] == "ISSUER_RUN_ATTESTATION_MISSING"
