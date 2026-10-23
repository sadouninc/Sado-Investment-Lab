"""Regression tests for the jq Lease Reader embedded in the queue workflow.

These tests exercise the actual workflow expression, not a reimplementation.
Requires jq (available on ubuntu-latest).
"""
import json
import subprocess
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/queue-auto-promotion-consumer.yml"


def lease_state(comments, issue="828"):
    source = WORKFLOW.read_text(encoding="utf-8")
    prefix = 'LEASE_STATE="$(jq -r --arg n "$number" ' + chr(39) + "\n"
    suffix = chr(39) + ' /tmp/comments.json)"'
    assert prefix in source and suffix in source, "Cannot find canonical jq Lease Reader"
    expression = source.split(prefix, 1)[1].split(suffix, 1)[0]
    try:
        result = subprocess.run(
            ["jq", "-r", "--arg", "n", issue, expression],
            input=json.dumps(comments),
            text=True,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise AssertionError(
            f"Canonical jq Lease Reader failed (exit={exc.returncode}): "
            f"{(exc.stderr or '').strip()}"
        ) from exc
    return result.stdout.strip()


def comment(body):
    return {"body": body}


def event(status, issue="828", **kwargs):
    return json.dumps({"work_ref": f"issue:{issue}", "status": status, **kwargs})


def test_multiline_active_lease():
    body = "<!-- AUTO_ROUTER_DISPATCH -->\n" + event(
        "ASSIGNED", lease_expires_at="2999-01-01T00:00:00Z"
    ) + "\n担当: 🌊ナギ"
    assert lease_state([comment(body)]) == "ACTIVE"


def test_multiline_acknowledged_lease():
    body = "<!-- flow-dispatch-lease -->\n" + event(
        "ACKNOWLEDGED", lease_expires_at="2999-01-01T00:00:00Z"
    ) + "\n担当: 🤖カイ"
    assert lease_state([comment(body)]) == "ACTIVE"


def test_unrelated_json_before_relevant_lease():
    body = '{"unrelated":true}\n' + event(
        "ACKNOWLEDGED", lease_expires_at="2999-01-01T00:00:00Z"
    )
    assert lease_state([comment(body)]) == "ACTIVE"


def test_later_terminal_event_wins():
    comments = [
        comment(event("ASSIGNED", lease_expires_at="2999-01-01T00:00:00Z")),
        comment(event("PROMOTION_DISPATCHED")),
    ]
    assert lease_state(comments) == "TERMINALIZING"


@pytest.mark.parametrize(
    "status",
    [
        "PROMOTION_DISPATCHED",
        "PROMOTION_BRANCH_READY",
        "PR_CREATE_REQUIRED",
        "DUPLICATE_SUPERSEDED",
        "PR_ALREADY_EXISTS",
        "PR_ALREADY_EXISTS_RACE_RESOLVED",
    ],
)
def test_terminal_events(status):
    assert lease_state([comment(event(status))]) == "TERMINALIZING"


def test_expired_lease():
    assert lease_state([comment(event(
        "ASSIGNED", lease_expires_at="2000-01-01T00:00:00Z"
    ))]) == "EXPIRED"


def test_canonical_expired_event_is_retryable():
    assert lease_state([comment(event("DISPATCH_LEASE_EXPIRED"))]) == "RETRYABLE"


def test_malformed_dispatch_marker_fails_closed():
    assert lease_state([comment("<!-- AUTO_ROUTER_DISPATCH broken -->")]) == "AMBIGUOUS"


def test_malformed_canonical_json_fails_closed():
    body = '<!-- flow-dispatch-lease -->\n{"work_ref":"issue:828","status":'
    assert lease_state([comment(body)]) == "AMBIGUOUS"


def test_malformed_target_json_without_marker_fails_closed():
    body = '{"work_ref":"issue:828","status":'
    assert lease_state([comment(body)]) == "AMBIGUOUS"


@pytest.mark.parametrize(
    "body",
    [
        '{"work_ref": "issue:828", "status":',
        '{ "work_ref" :\n "issue:828", "status":',
        '{"owner_slice" : "issue-828", "status":',
        '{"work_ref": "issue:828',
    ],
)
def test_malformed_target_whitespace_and_truncation_fail_closed(body):
    assert lease_state([comment(body)]) == "AMBIGUOUS"


@pytest.mark.parametrize(
    "body",
    [
        '{"work_ref": "issue:8289", "status":',
        '{"work_ref": "issue:827", "status":',
        '{"owner_slice": "issue-8289", "status":',
        '{"not_work_ref": "issue:828", "status":',
        "Unrelated update without a canonical lease event",
    ],
)
def test_unrelated_malformed_or_plain_comments_do_not_claim_target(body):
    assert lease_state([comment(body)]) == "NONE"


def test_ambiguous_lease_followed_by_unrelated_comment_remains_ambiguous():
    comments = [
        comment('{"work_ref": "issue:828", "status":'),
        comment("Routine update; no lease event"),
        comment(event("ASSIGNED", issue="827", lease_expires_at="2999-01-01T00:00:00Z")),
    ]
    assert lease_state(comments) == "AMBIGUOUS"



@pytest.mark.parametrize(
    "body, expected",
    [
        ('Lease update: {"work_ref": "issue:828", "status":', "AMBIGUOUS"),
        ('Lease update: {"work_ref": "issue:828", "status":"ASSIGNED"}', "AMBIGUOUS"),
        ('Lease update: {"work_ref": "issue:8289", "status":', "NONE"),
        ('Lease update: {"work_ref": "issue:827", "status":', "NONE"),
    ],
)
def test_prose_prefixed_target_fragment_fails_closed(body, expected):
    """Target-bearing inline fragments must not be mistaken for no lease."""
    assert lease_state([comment(body)]) == expected


def test_multiline_fallback_assigned_lease():
    body = "<!-- flow-dispatch-lease -->\n" + event(
        "FALLBACK_ASSIGNED", lease_expires_at="2999-01-01T00:00:00Z"
    ) + "\n担当: 🪐ソラ"
    assert lease_state([comment(body)]) == "ACTIVE"


def test_empty_comment_list_has_no_lease():
    assert lease_state([]) == "NONE"


def test_valid_event_plus_malformed_json_fails_closed():
    body = "<!-- flow-dispatch-lease -->\n" + event(
        "ASSIGNED", lease_expires_at="2999-01-01T00:00:00Z"
    ) + '\n{"work_ref":"issue:828","status":'
    assert lease_state([comment(body)]) == "AMBIGUOUS"


def test_multiple_competing_events_in_one_comment_fail_closed():
    body = "<!-- flow-dispatch-lease -->\n" + event(
        "ASSIGNED", lease_expires_at="2999-01-01T00:00:00Z"
    ) + "\n" + event("DISPATCH_LEASE_EXPIRED")
    assert lease_state([comment(body)]) == "AMBIGUOUS"


def test_expired_then_active_events_in_one_comment_fail_closed():
    """Amazon Q regression: event order must not select the later ACTIVE lease."""
    body = event("DISPATCH_LEASE_EXPIRED") + "\n" + event(
        "ASSIGNED", lease_expires_at="2999-01-01T00:00:00Z"
    )
    assert lease_state([comment(body)]) == "AMBIGUOUS"


def test_unknown_status_fails_closed():
    assert lease_state([comment(event("UNKNOWN_NEW_STATUS"))]) == "AMBIGUOUS"


def test_unrelated_issue_does_not_count_as_lease():
    assert lease_state([comment(event(
        "ASSIGNED", issue="827", lease_expires_at="2999-01-01T00:00:00Z"
    ))]) == "NONE"


def test_protected_issue_79_has_no_authority_from_other_issue():
    assert lease_state([comment(event(
        "ASSIGNED", issue="828", lease_expires_at="2999-01-01T00:00:00Z"
    ))], issue="79") == "NONE"



def test_jq_failure_reports_stderr(monkeypatch):
    def failing_run(*args, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=3, cmd=args[0], stderr="jq: syntax error in canonical reader"
        )

    monkeypatch.setattr(subprocess, "run", failing_run)
    with pytest.raises(AssertionError, match="jq: syntax error in canonical reader"):
        lease_state([comment(event("ASSIGNED"))])
