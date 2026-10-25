"""Regression tests for #873 read-only scheduled observation gate.

No external API calls. The writer must stay manual-only even if the CLI POST flag is set.
"""
import io
import json
import os
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

import pytest

from scripts.actions_failure_issue_orchestrator import main


@pytest.mark.parametrize(
    ("event", "confirmation", "expect_post"),
    [
        ("schedule", "", False),
        ("schedule", "ISSUE873_CREATE_ONE", False),
        ("workflow_dispatch", "", False),
        ("workflow_dispatch", "ISSUE873_CREATE_ONE", True),
        ("pull_request", "ISSUE873_CREATE_ONE", False),
    ],
)
def test_issue_post_requires_manual_dispatch_and_exact_confirmation(event, confirmation, expect_post):
    env = {
        "GITHUB_REPOSITORY": "acme/repo",
        "GH_TOKEN": "fake-test-token",
        "GITHUB_EVENT_NAME": event,
        "GITHUB_REF": "refs/heads/main",
        "ISSUE_POST_CONFIRM": confirmation,
    }
    result = {
        "decision": "ISSUE_DRAFT_ELIGIBLE",
        "analysis": {"request_id": "actions-failure-" + "a" * 20},
    }
    fake_client = MagicMock()
    stdout = io.StringIO()
    with (
        patch.dict(os.environ, env),
        patch("scripts.actions_failure_issue_orchestrator.GitHubReadOnlyClient", return_value=fake_client) as client_factory,
        patch("scripts.actions_failure_issue_orchestrator.collect_current_failure", return_value=result),
        patch("scripts.actions_failure_issue_orchestrator.post_validated_issue", return_value={"number": 100}) as writer,
    ):
        with redirect_stdout(stdout):
            assert main(["--enable-post"]) == 0
        client_factory.assert_called_once_with("acme/repo", "fake-test-token")
        output = json.loads(stdout.getvalue())
        assert output["request_id"] == result["analysis"]["request_id"]
        if expect_post:
            writer.assert_called_once()
            fake_client.all_pages.assert_called_once()
        else:
            writer.assert_not_called()
            fake_client.all_pages.assert_not_called()
            assert output == {
                "decision": "ISSUE_DRAFT_ELIGIBLE",
                "issue_post": "SKIPPED" if event == "schedule" else "DISABLED",
                "request_id": result["analysis"]["request_id"],
            }


def test_schedule_default_cli_cannot_post():
    with (
        patch.dict(os.environ, {
            "GITHUB_REPOSITORY": "acme/repo",
            "GH_TOKEN": "fake-test-token",
            "GITHUB_EVENT_NAME": "schedule",
            "GITHUB_REF": "refs/heads/main",
            "ISSUE_POST_CONFIRM": "ISSUE873_CREATE_ONE",
        }),
        patch("scripts.actions_failure_issue_orchestrator.GitHubReadOnlyClient"),
        patch("scripts.actions_failure_issue_orchestrator.collect_current_failure", return_value={"decision": "ISSUE_DRAFT_ELIGIBLE"}),
        patch("scripts.actions_failure_issue_orchestrator.post_validated_issue") as writer,
    ):
        with redirect_stdout(io.StringIO()):
            assert main([]) == 0
        writer.assert_not_called()


def test_scheduled_preview_exposes_only_auditable_failure_identifiers():
    analysis = {
        "source_run_id": 123,
        "job_id": 456,
        "error_class": "TEST_FAILURE",
        "request_id": "actions-failure-" + "a" * 20,
        "candidate_root_cause": "HYPOTHESIS: private diagnostic detail",
    }
    result = {
        "decision": "ISSUE_DRAFT_ELIGIBLE",
        "analysis": analysis,
        "issue_draft": {"title": "sensitive title", "body": "sensitive body"},
    }
    env = {
        "GITHUB_REPOSITORY": "acme/repo",
        "GH_TOKEN": "fake-test-token",
        "GITHUB_EVENT_NAME": "schedule",
        "GITHUB_REF": "refs/heads/main",
        "ISSUE_POST_CONFIRM": "",
    }
    stdout = io.StringIO()
    with (
        patch.dict(os.environ, env),
        patch("scripts.actions_failure_issue_orchestrator.GitHubReadOnlyClient"),
        patch("scripts.actions_failure_issue_orchestrator.collect_current_failure", return_value=result),
        patch("scripts.actions_failure_issue_orchestrator.post_validated_issue") as writer,
        redirect_stdout(stdout),
    ):
        assert main([]) == 0
    output = json.loads(stdout.getvalue())
    assert output == {
        "decision": "ISSUE_DRAFT_ELIGIBLE",
        "error_class": "TEST_FAILURE",
        "issue_post": "SKIPPED",
        "job_id": 456,
        "request_id": "actions-failure-" + "a" * 20,
        "source_run_id": 123,
    }
    assert "candidate_root_cause" not in output
    assert "issue_draft" not in output
    writer.assert_not_called()


def test_scheduled_preview_omits_malformed_identifiers():
    result = {
        "decision": "ISSUE_DRAFT_ELIGIBLE",
        "analysis": {
            "source_run_id": True,
            "job_id": -1,
            "error_class": "TEST_FAILURE\nINJECTED",
            "request_id": "actions-failure-invalid",
        },
    }
    env = {
        "GITHUB_REPOSITORY": "acme/repo",
        "GH_TOKEN": "fake-test-token",
        "GITHUB_EVENT_NAME": "schedule",
        "GITHUB_REF": "refs/heads/main",
        "ISSUE_POST_CONFIRM": "",
    }
    stdout = io.StringIO()
    with (
        patch.dict(os.environ, env),
        patch("scripts.actions_failure_issue_orchestrator.GitHubReadOnlyClient"),
        patch("scripts.actions_failure_issue_orchestrator.collect_current_failure", return_value=result),
        patch("scripts.actions_failure_issue_orchestrator.post_validated_issue") as writer,
        redirect_stdout(stdout),
    ):
        assert main([]) == 0
    assert json.loads(stdout.getvalue()) == {
        "decision": "ISSUE_DRAFT_ELIGIBLE",
        "issue_post": "SKIPPED",
    }
    writer.assert_not_called()


@pytest.mark.parametrize("case,expected,rc", [
    ("success", "NO_CURRENT_OPEN_PR_FAILURE", 0),
    ("failure", "ISSUE_DRAFT_ELIGIBLE", 0),
    ("pending", "HOLD_PENDING_CURRENT_HEAD_RUN", 2),
    ("missing_prs", "HOLD_ERROR", 2),
    ("partial_pages", "HOLD_ERROR", 2),
    ("missing_jobs", "HOLD_NO_VERIFIED_FAILED_JOB", 2),
    ("unlinked", "HOLD_UNVERIFIED_PR_ASSOCIATION", 2),
    ("duplicate", "DUPLICATE_SUPPRESSED", 0),
])
def test_schedule_real_collector_boundaries_never_post(case, expected, rc):
    from datetime import datetime, timezone
    from scripts.actions_failure_collector import GitHubReadOnlyClient
    from scripts.actions_failure_analyzer import analyze_completed_failure
    sha = "a" * 40
    prs = [{"number": 870, "head": {"sha": sha, "ref": "feature/870"}}]
    run = {"id": 123, "name": "PR Preflight", "workflow_id": 10,
           "event": "pull_request", "status": "completed", "conclusion": "failure",
           "head_branch": "feature/870", "head_sha": sha,
           "created_at": datetime.now(timezone.utc).isoformat(), "pull_requests": [{"number": 870}]}
    jobs = [{"id": 456, "name": "preflight", "conclusion": "failure",
             "steps": [{"name": "pytest", "conclusion": "failure"}]}]
    if case == "success":
        run["conclusion"] = "success"
    if case == "pending":
        run.update(status="in_progress", conclusion=None)
    if case == "unlinked":
        run["pull_requests"] = []
    if case == "missing_jobs":
        jobs = []
    issues = []
    if case == "duplicate":
        analysis = analyze_completed_failure("acme/repo", run, jobs)
        issues = [{"number": 90, "body": "<!-- " + analysis["request_id"] + " -->"}]
    def response(endpoint, params):
        if endpoint == "pulls":
            if case == "missing_prs":
                return {}
            if case == "partial_pages":
                return prs * 100
            return prs
        if endpoint == "actions/runs":
            return {"workflow_runs": [run]}
        if endpoint.endswith("/jobs"):
            return {"jobs": jobs}
        if endpoint == "issues":
            return issues
        raise AssertionError(endpoint)
    client = GitHubReadOnlyClient("acme/repo", "test-token", max_pages=1)
    out = io.StringIO()
    with (patch.dict(os.environ, {"GITHUB_REPOSITORY": "acme/repo", "GH_TOKEN": "test-token",
          "GITHUB_EVENT_NAME": "schedule", "GITHUB_REF": "refs/heads/main",
          "ISSUE_POST_CONFIRM": "ISSUE873_CREATE_ONE"}),
          patch("scripts.actions_failure_issue_orchestrator.GitHubReadOnlyClient", return_value=client),
          patch.object(client, "get_json", side_effect=response),
          patch("scripts.actions_failure_issue_orchestrator.post_validated_issue") as writer,
          redirect_stdout(out)):
        assert main(["--enable-post"]) == rc
    data = json.loads(out.getvalue())
    assert data["decision"] == expected
    assert data["issue_post"] == "SKIPPED"
    if case == "missing_jobs":
        assert data["source_run_id"] == 123
        assert "job_id" not in data
    writer.assert_not_called()


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
def test_schedule_http_failure_is_hold_without_payload(status):
    from urllib.error import HTTPError
    out = io.StringIO()
    with (patch.dict(os.environ, {"GITHUB_REPOSITORY": "acme/repo", "GH_TOKEN": "test-token",
          "GITHUB_EVENT_NAME": "schedule", "GITHUB_REF": "refs/heads/main"}),
          patch("scripts.actions_failure_collector.urlopen",
                side_effect=HTTPError("https://example.invalid", status, "private payload", {}, None)),
          patch("scripts.actions_failure_issue_orchestrator.post_validated_issue") as writer,
          redirect_stdout(out)):
        assert main(["--enable-post"]) == 2
    assert json.loads(out.getvalue()) == {"decision": "HOLD_ERROR", "error_type": "IncompleteInventory", "issue_post": "SKIPPED"}
    assert "private payload" not in out.getvalue()
    writer.assert_not_called()


def test_observable_hold_rejects_injected_decision_and_identifiers():
    from scripts.actions_failure_issue_orchestrator import _observable_result
    assert _observable_result({"decision": "HOLD\nsecret", "source_run_id": True}, issue_post="SKIPPED") == {
        "decision": "HOLD_INVALID_DECISION", "issue_post": "SKIPPED"}


def test_protected_issue_body_is_not_inspected_by_collector():
    from scripts.actions_failure_analyzer import decide_issue_action
    class ForbiddenBody:
        def __str__(self):
            raise AssertionError("protected issue body inspected")
    assert decide_issue_action({"request_id": "actions-failure-" + "a" * 20},
        [{"number": 79, "body": ForbiddenBody()}], inventory_complete=True) == "ISSUE_DRAFT_ELIGIBLE"
