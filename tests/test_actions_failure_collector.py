"""No live GitHub access. Test all read-only paths with injected inventory."""
from datetime import datetime, timezone

import pytest

from scripts.actions_failure_collector import GitHubReadOnlyClient, IncompleteInventory, collect_current_failure

NOW = datetime(2026, 10, 18, 0, 0, tzinfo=timezone.utc)
SHA = "a" * 40


def pr():
    return {"number": 870, "head": {"ref": "feature/870", "sha": SHA}}


def run(conclusion="failure"):
    return {"id": 100, "name": "PR Preflight", "workflow_id": 10, "event": "pull_request",
            "status": "completed", "conclusion": conclusion, "head_branch": "feature/870",
            "head_sha": SHA, "created_at": "2026-10-17T23:00:00Z",
            "pull_requests": [{"number": 870}]}


def jobs():
    return [{"id": 111, "name": "preflight", "conclusion": "failure",
             "steps": [{"name": "pytest", "conclusion": "failure"}]}]


class Stub(GitHubReadOnlyClient):
    def __init__(self, prs=None, runs=None, job_list=None, issues=None):
        super().__init__("sadouninc/Sado-Investment-Lab", "test-token")
        self.responses = {"pulls": [pr()] if prs is None else prs,
                          "issues": [] if issues is None else issues,
                          "actions/runs": [run()] if runs is None else runs,
                          "actions/runs/100/jobs": jobs() if job_list is None else job_list}
        self.calls = []

    def get_json(self, endpoint, params):
        self.calls.append((endpoint, params["page"]))
        if params["page"] > 1:
            return [] if endpoint in {"pulls", "issues"} else {"total_count": len(self.responses[endpoint]), "jobs" if endpoint.endswith("/jobs") else "workflow_runs": []}
        value = self.responses[endpoint]
        return value if endpoint in {"pulls", "issues"} else {"total_count": len(value), "jobs" if endpoint.endswith("/jobs") else "workflow_runs": value}


def test_readonly_collector_creates_draft_but_never_writes():
    c = Stub()
    out = collect_current_failure(c, as_of=NOW)
    assert out["decision"] == "ISSUE_DRAFT_ELIGIBLE"
    assert out["issue_draft"]["body"].count("TRIAGE_REQUIRED") == 1
    assert out["write_performed"] is False
    assert out["ready_promoted"] is False
    assert c.calls == [("pulls", 1), ("actions/runs", 1), ("actions/runs/100/jobs", 1), ("issues", 1)]


def test_no_current_failure_never_reads_jobs():
    c = Stub(runs=[run("success")])
    out = collect_current_failure(c, as_of=NOW)
    assert out["decision"] == "NO_CURRENT_OPEN_PR_FAILURE"
    assert len(c.calls) == 2


def test_closed_pr_never_produces_issue():
    c = Stub(prs=[])
    assert collect_current_failure(c, as_of=NOW)["decision"] == "NO_CURRENT_OPEN_PR_FAILURE"


def test_failed_job_inventory_stays_hold():
    c = Stub(job_list=[])
    assert collect_current_failure(c, as_of=NOW)["decision"] == "HOLD_NO_VERIFIED_FAILED_JOB"


def test_api_error_fails_closed():
    c = Stub()
    def error(*_):
        raise IncompleteInventory("API failed")
    c.get_json = error
    with pytest.raises(IncompleteInventory):
        collect_current_failure(c, as_of=NOW)


def test_full_last_page_does_not_truncate():
    c = Stub()
    c.max_pages = 1
    c.responses["pulls"] = [pr()] * 100
    with pytest.raises(IncompleteInventory, match="pagination bound"):
        collect_current_failure(c, as_of=NOW)


def test_repository_and_token_required():
    with pytest.raises(ValueError):
        GitHubReadOnlyClient("bad", "token")
    with pytest.raises(IncompleteInventory):
        GitHubReadOnlyClient("a/b", "")


def test_endpoint_allowlist_rejects_mutation_surfaces():
    c = GitHubReadOnlyClient("a/b", "fake")
    with pytest.raises(ValueError):
        c.get_json("issues/79/comments", {"page": 1})


def test_existing_open_issue_suppresses_draft():
    first = collect_current_failure(Stub(), as_of=NOW)
    marker = first["issue_draft"]["body"].splitlines()[2]
    c = Stub(issues=[{"number": 999, "state": "open", "body": marker}])
    out = collect_current_failure(c, as_of=NOW)
    assert out["decision"] == "DUPLICATE_SUPPRESSED"
    assert "issue_draft" not in out
    assert out["write_performed"] is False


def test_existing_closed_issue_also_suppresses_draft():
    first = collect_current_failure(Stub(), as_of=NOW)
    marker = first["issue_draft"]["body"].splitlines()[2]
    out = collect_current_failure(Stub(issues=[{"number": 998, "state": "closed", "body": marker}]), as_of=NOW)
    assert out["decision"] == "DUPLICATE_SUPPRESSED"


def test_incomplete_issue_pagination_fails_closed():
    c = Stub(issues=[{"number": i+1000, "body": ""} for i in range(100)])
    c.max_pages = 1
    with pytest.raises(IncompleteInventory, match="pagination bound"):
        collect_current_failure(c, as_of=NOW)


def test_protected_issue_not_used_as_duplicate_evidence():
    first = collect_current_failure(Stub(), as_of=NOW)
    marker = first["issue_draft"]["body"].splitlines()[2]
    out = collect_current_failure(Stub(issues=[{"number": 79, "body": marker}]), as_of=NOW)
    assert out["decision"] == "ISSUE_DRAFT_ELIGIBLE"


def test_no_current_failure_skips_issue_inventory():
    c = Stub(runs=[run("success")])
    assert collect_current_failure(c, as_of=NOW)["decision"] == "NO_CURRENT_OPEN_PR_FAILURE"
    assert all(endpoint != "issues" for endpoint, _ in c.calls)


@pytest.mark.parametrize("endpoint,key", [("actions/runs", "workflow_runs"), ("actions/runs/100/jobs", "jobs")])
@pytest.mark.parametrize("size", [0, 1, 100, 101])
def test_counted_inventory_complete_pages(endpoint, key, size):
    c = GitHubReadOnlyClient("acme/repo", "test-token")
    items = [{"id": i + 1} for i in range(size)]
    c.get_json = lambda endpoint, params: {"total_count": size, key: items[(params["page"]-1)*100:params["page"]*100]}
    assert c.all_pages(endpoint, key, {}) == items


@pytest.mark.parametrize("payload", [
    {"workflow_runs": []},
    {"total_count": True, "workflow_runs": []},
    {"total_count": -1, "workflow_runs": []},
    {"total_count": "0", "workflow_runs": []},
    {"total_count": 1, "workflow_runs": []},
    {"total_count": 0, "workflow_runs": [{"id": 1}]},
    {"total_count": 2, "workflow_runs": [{"id": 1}]},
    {"total_count": 2, "workflow_runs": [{"id": 1}, {"id": 1}]},
    {"total_count": 1, "workflow_runs": [{"id": True}]},
    {"total_count": 1, "workflow_runs": [{}]},
])
def test_counted_inventory_rejects_uncertainty(payload):
    c = GitHubReadOnlyClient("acme/repo", "test-token")
    c.get_json = lambda *_: payload
    with pytest.raises(IncompleteInventory):
        c.all_pages("actions/runs", "workflow_runs", {})


@pytest.mark.parametrize("change", ["count", "duplicate", "empty", "limit"])
def test_counted_inventory_rejects_page_drift_or_truncation(change):
    c = GitHubReadOnlyClient("acme/repo", "test-token", max_pages=1 if change == "limit" else 10)
    def response(endpoint, params):
        if params["page"] == 1:
            return {"total_count": 101, "jobs": [{"id": i+1} for i in range(100)]}
        return {"total_count": 102 if change == "count" else 101,
                "jobs": [] if change == "empty" else [{"id": 1 if change == "duplicate" else 101}]}
    c.get_json = response
    with pytest.raises(IncompleteInventory):
        c.all_pages("actions/runs/100/jobs", "jobs", {})


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
def test_counted_inventory_http_failure_stays_incomplete(status):
    from urllib.error import HTTPError
    from unittest.mock import patch
    c = GitHubReadOnlyClient("acme/repo", "test-token")
    with patch("scripts.actions_failure_collector.urlopen", side_effect=HTTPError("https://example.invalid", status, "test", {}, None)):
        with pytest.raises(IncompleteInventory):
            c.all_pages("actions/runs", "workflow_runs", {})
