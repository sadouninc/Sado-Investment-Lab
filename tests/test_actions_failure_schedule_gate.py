"""Regression tests for #873 read-only scheduled observation gate.

No external API calls. The writer must stay manual-only even if the CLI POST flag is set.
"""
import io
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
        "analysis": {"request_id": "actions-failure-test"},
    }
    with (
        patch.dict(os.environ, env),
        patch("scripts.actions_failure_issue_orchestrator.GitHubReadOnlyClient"),
        patch("scripts.actions_failure_issue_orchestrator.collect_current_failure", return_value=result),
        patch("scripts.actions_failure_issue_orchestrator.post_validated_issue", return_value={"number": 100}) as writer,
    ):
        fake_client = MagicMock()
        with patch("scripts.actions_failure_issue_orchestrator.GitHubReadOnlyClient", return_value=fake_client):
            with redirect_stdout(io.StringIO()):
                assert main(["--enable-post"]) == 0
        if expect_post:
            writer.assert_called_once()
            fake_client.all_pages.assert_called_once()
        else:
            writer.assert_not_called()
            fake_client.all_pages.assert_not_called()


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
