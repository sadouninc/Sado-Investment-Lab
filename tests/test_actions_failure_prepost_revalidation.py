"""#873 D2: GET-only pre-POST boundary tests (no GitHub POST)."""
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest

from scripts.actions_failure_analyzer import analyze_completed_failure, build_issue_draft
from scripts.actions_failure_collector import IncompleteInventory
from scripts.actions_failure_issue_orchestrator import _RecordingClient, _revalidate_before_post
from scripts.actions_failure_selection import select_open_pr_failure

NOW = datetime(2026, 11, 5, 16, 0, tzinfo=timezone.utc)


def fixture():
    run_id = 123
    sha = "a" * 40
    pull = {"number": 5, "head": {"sha": sha, "ref": "feature/5"}}
    run = {
        "id": run_id,
        "name": "PR Preflight",
        "workflow_id": 10,
        "run_attempt": 1,
        "event": "pull_request",
        "status": "completed",
        "conclusion": "failure",
        "head_branch": "feature/5",
        "head_sha": sha,
        "created_at": "2026-11-05T15:30:00Z",
        "pull_requests": [{"number": 5}],
    }
    jobs = [{
        "id": 456,
        "name": "preflight",
        "conclusion": "failure",
        "steps": [{"name": "pytest", "conclusion": "failure"}],
    }]
    calls = [
        ("pulls", None, {"state": "open"}, [pull]),
        ("actions/runs", "workflow_runs", {"event": "pull_request"}, [run]),
        ("actions/runs/123/jobs", "jobs", {}, jobs),
        ("issues", None, {"state": "all"}, []),
    ]
    analysis = analyze_completed_failure("acme/repo", run, jobs)
    result = {
        "decision": "ISSUE_DRAFT_ELIGIBLE",
        "analysis": analysis,
        "issue_draft": build_issue_draft(analysis),
    }
    client = MagicMock()
    client.repository = "acme/repo"
    client.all_pages.side_effect = lambda endpoint, key, params: next(
        value for ep, k, p, value in calls if (ep, k, p) == (endpoint, key, params))
    return calls, result, client


def test_eight_logical_gets_revalidated_before_writer(monkeypatch):
    calls, result, client = fixture()
    monkeypatch.setattr("scripts.actions_failure_analyzer.decide_issue_action",
                        lambda analysis, issues, inventory_complete: "ISSUE_DRAFT_ELIGIBLE")
    assert _revalidate_before_post(client, calls, result, as_of=NOW) == []
    assert [x.args[0] for x in client.all_pages.call_args_list] == [
        "issues", "pulls", "actions/runs", "actions/runs/123/jobs"]


def test_production_recording_client_keeps_first_pass_log_immutable(monkeypatch):
    calls, result, inner = fixture()
    recorder = _RecordingClient(inner)
    recorder.calls = deepcopy(calls)

    assert recorder.repository == "acme/repo"
    assert _revalidate_before_post(
        recorder.client, deepcopy(recorder.calls), result, as_of=NOW
    ) == []
    assert recorder.calls == calls
    assert len(recorder.calls) == 4


@pytest.mark.parametrize("changed", ["issues", "pulls", "actions/runs", "actions/runs/123/jobs"])
def test_changed_source_holds_without_writer(changed):
    calls, result, client = fixture()
    original = client.all_pages.side_effect
    def altered(endpoint, key, params):
        value = original(endpoint, key, params)
        return [{"id": 999}] if endpoint == changed else value
    client.all_pages.side_effect = altered
    with pytest.raises(IncompleteInventory, match="source changed"):
        _revalidate_before_post(client, calls, result, as_of=NOW)


def test_missing_initial_binding_holds():
    calls, result, client = fixture()
    with pytest.raises(IncompleteInventory, match="initial GET"):
        _revalidate_before_post(client, calls[:-1], result, as_of=NOW)


def test_duplicate_found_on_fresh_snapshot_holds(monkeypatch):
    calls, result, client = fixture()
    monkeypatch.setattr("scripts.actions_failure_analyzer.decide_issue_action",
                        lambda analysis, issues, inventory_complete: "DUPLICATE_SUPPRESSED")
    with pytest.raises(IncompleteInventory, match="no longer eligible"):
        _revalidate_before_post(client, calls, result, as_of=NOW)


def test_get_error_holds():
    calls, result, client = fixture()
    client.all_pages.side_effect = IncompleteInventory("API unavailable")
    with pytest.raises(IncompleteInventory):
        _revalidate_before_post(client, calls, result, as_of=NOW)


@pytest.mark.parametrize(
    ("inventory", "message"),
    [("pulls", "duplicate pull request"), ("issues", "duplicate issue")],
)
def test_duplicate_numbered_inventory_holds(inventory, message):
    calls, result, client = fixture()
    index = 0 if inventory == "pulls" else 3
    values = calls[index][3] if inventory == "pulls" else [{"number": 90, "body": ""}]
    calls[index] = (*calls[index][:3], values * 2)
    with pytest.raises(IncompleteInventory, match=message):
        _revalidate_before_post(client, calls, result, as_of=NOW)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("run_attempt", 0, "run_attempt"),
        ("workflow_id", True, "workflow_id"),
        ("pull_requests", [{"number": 5}, {"number": 6}], "PR binding ambiguous"),
        ("head_sha", "b" * 40, "head binding changed"),
    ],
)
def test_source_run_binding_must_be_exact(field, value, message):
    calls, result, client = fixture()
    calls[1][3][0][field] = value
    with pytest.raises(IncompleteInventory, match=message):
        _revalidate_before_post(client, calls, result, as_of=NOW)


@pytest.mark.parametrize("ticks", [(10.0, 131.0), (10.0, 9.0)])
def test_revalidation_duration_is_bounded_and_monotonic(ticks):
    calls, result, client = fixture()
    values = iter(ticks)
    with pytest.raises(IncompleteInventory, match="duration invalid"):
        _revalidate_before_post(
            client,
            calls,
            result,
            as_of=NOW,
            monotonic_clock=lambda: next(values),
        )


def test_revalidation_duration_includes_semantic_checks(monkeypatch):
    calls, result, client = fixture()
    semantic_checks_started = False
    real_selector = select_open_pr_failure

    def delayed_selector(*args, **kwargs):
        nonlocal semantic_checks_started
        semantic_checks_started = True
        return real_selector(*args, **kwargs)

    monkeypatch.setattr(
        "scripts.actions_failure_selection.select_open_pr_failure",
        delayed_selector,
    )

    with pytest.raises(IncompleteInventory, match="duration invalid"):
        _revalidate_before_post(
            client,
            calls,
            result,
            as_of=NOW,
            monotonic_clock=lambda: 121.0 if semantic_checks_started else 0.0,
        )


def test_stale_source_run_holds_after_fresh_semantic_reselection():
    calls, result, client = fixture()
    with pytest.raises(IncompleteInventory, match="semantic selection"):
        _revalidate_before_post(
            client,
            calls,
            result,
            as_of=datetime(2026, 11, 7, tzinfo=timezone.utc),
        )


def test_semantic_identity_change_holds(monkeypatch):
    calls, result, client = fixture()
    changed = deepcopy(result["analysis"])
    changed["job_id"] = 999
    monkeypatch.setattr(
        "scripts.actions_failure_selection.select_open_pr_failure",
        lambda *args, **kwargs: {
            "decision": "ISSUE_DRAFT_ELIGIBLE",
            "analysis": changed,
        },
    )
    with pytest.raises(IncompleteInventory, match="semantic identity changed"):
        _revalidate_before_post(client, calls, result, as_of=NOW)

