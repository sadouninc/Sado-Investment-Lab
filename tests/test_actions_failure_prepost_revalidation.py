"""#873 D2: GET-only pre-POST boundary tests (no GitHub POST)."""
from unittest.mock import MagicMock
import pytest

from scripts.actions_failure_collector import IncompleteInventory
from scripts.actions_failure_issue_orchestrator import _revalidate_before_post


def fixture():
    run_id = 123
    calls = [
        ("pulls", None, {"state": "open"}, [{"number": 5, "head": {"sha": "a" * 40}}]),
        ("actions/runs", "workflow_runs", {"event": "pull_request"}, [{"id": run_id}]),
        ("actions/runs/123/jobs", "jobs", {}, [{"id": 456}]),
        ("issues", None, {"state": "all"}, []),
    ]
    result = {"analysis": {"source_run_id": run_id, "request_id": "actions-failure-" + "a" * 20},
              "issue_draft": {"title": "bounded test"}}
    client = MagicMock()
    client.all_pages.side_effect = lambda endpoint, key, params: next(
        value for ep, k, p, value in calls if (ep, k, p) == (endpoint, key, params))
    return calls, result, client


def test_eight_logical_gets_revalidated_before_writer(monkeypatch):
    calls, result, client = fixture()
    monkeypatch.setattr("scripts.actions_failure_analyzer.decide_issue_action",
                        lambda analysis, issues, inventory_complete: "ISSUE_DRAFT_ELIGIBLE")
    assert _revalidate_before_post(client, calls, result) == []
    assert [x.args[0] for x in client.all_pages.call_args_list] == [
        "issues", "pulls", "actions/runs", "actions/runs/123/jobs"]


@pytest.mark.parametrize("changed", ["issues", "pulls", "actions/runs", "actions/runs/123/jobs"])
def test_changed_source_holds_without_writer(changed):
    calls, result, client = fixture()
    original = client.all_pages.side_effect
    def altered(endpoint, key, params):
        value = original(endpoint, key, params)
        return [{"id": 999}] if endpoint == changed else value
    client.all_pages.side_effect = altered
    with pytest.raises(IncompleteInventory, match="source changed"):
        _revalidate_before_post(client, calls, result)


def test_missing_initial_binding_holds():
    calls, result, client = fixture()
    with pytest.raises(IncompleteInventory, match="initial GET"):
        _revalidate_before_post(client, calls[:-1], result)


def test_duplicate_found_on_fresh_snapshot_holds(monkeypatch):
    calls, result, client = fixture()
    monkeypatch.setattr("scripts.actions_failure_analyzer.decide_issue_action",
                        lambda analysis, issues, inventory_complete: "DUPLICATE_SUPPRESSED")
    with pytest.raises(IncompleteInventory, match="no longer eligible"):
        _revalidate_before_post(client, calls, result)


def test_get_error_holds():
    calls, result, client = fixture()
    client.all_pages.side_effect = IncompleteInventory("API unavailable")
    with pytest.raises(IncompleteInventory):
        _revalidate_before_post(client, calls, result)
