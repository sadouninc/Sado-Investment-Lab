"""Bounded negative and positive fixtures for the read-only #859 source adapter."""
from copy import deepcopy
from datetime import datetime, timezone

from scripts.recovery_rev2_owner_claim_source import DOMAINS, project_owner_claim_source

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
