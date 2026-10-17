"""Regression tests for the jq Lease Reader embedded in the queue workflow.

These tests exercise the actual workflow expression, not a reimplementation.
Requires jq (available on ubuntu-latest).
"""
import json
import subprocess
from pathlib import Path

import pytest

WORKFLOW = Path(".github/workflows/queue-auto-promotion-consumer.yml")


def lease_state(comments, issue="828"):
    source = WORKFLOW.read_text(encoding="utf-8")
    prefix = 'LEASE_STATE="$(jq -r --arg n "$number" ' + chr(39) + "\n"
    suffix = chr(39) + ' /tmp/comments.json)"'
    assert prefix in source and suffix in source, "Cannot find canonical jq Lease Reader"
    expression = source.split(prefix, 1)[1].split(suffix, 1)[0]
    result = subprocess.run(
        ["jq", "-r", "--arg", "n", issue, expression],
        input=json.dumps(comments),
        text=True,
        capture_output=True,
        check=True,
    )
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
