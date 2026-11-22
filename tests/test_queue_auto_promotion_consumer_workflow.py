import json
import subprocess
from pathlib import Path

import pytest
ROOT=Path(__file__).resolve().parents[1]
CONSUMER=ROOT/".github/workflows/queue-auto-promotion-consumer.yml"
DISPATCH=ROOT/".github/workflows/ai-production-dispatch.yml"
def _read(path): return path.read_text(encoding="utf-8")
def test_triggers(): t=_read(CONSUMER); assert "schedule:" in t and "cron:" in t and "workflow_dispatch:" in t
def test_never_79(): t=_read(CONSUMER); assert ".number != 79" in t and '[[ "$ISSUE_NUMBER" != "79" ]]' in t and "PROTECTED_ISSUE_79" in t
def test_bounded_scan():
    t=_read(CONSUMER)
    assert "READY_FOR_IMPLEMENTATION" in t and "per_page=100" in t
    assert "gh api --paginate --slurp" in t and "add // []" in t
    assert '(.pull_request // null) == null' in t and "[:20]" in t
def test_reuses_adapter(): t=_read(CONSUMER); assert "python -m scripts.queue_auto_promotion_consumer" in t and "--active-owner-slices" in t and "--active-paths" in t
def test_canonical_lease_guard_uses_status_and_expiry_not_historical_marker():
    t=_read(CONSUMER)
    assert "lease_expires_at" in t and "fromdateiso8601" in t
    assert 'ACTIVE|TERMINALIZING|AMBIGUOUS' in t
    assert 'EXPIRED|RETRYABLE|NONE' in t
    assert "historical AUTO_ROUTER_DISPATCH marker alone is not an active lease" in t
    assert "already has an existing canonical lease marker" not in t

def test_retryable_and_terminal_status_contract_is_explicit():
    t=_read(CONSUMER)
    for status in ("DISPATCH_LEASE_EXPIRED","COPILOT_RETRYABLE_FAILURE","RETRYABLE_FAILURE","FALLBACK_RETRYABLE_FAILURE","BLOCKED_BASE_DRIFT","BLOCKED_CONTRACT_REPLAY","FAIL_CLOSED"):
        assert status in t
    for status in ("PROMOTION_DISPATCHED","PROMOTION_BRANCH_READY","PR_CREATE_REQUIRED","DUPLICATE_SUPERSEDED","PR_ALREADY_EXISTS","PR_ALREADY_EXISTS_RACE_RESOLVED"):
        assert status in t
def test_conflicting_pr_paths(): t=_read(CONSUMER); assert "pulls?state=open" in t and "/files?per_page=100" in t and "--active-paths /tmp/active-paths.json" in t
def test_pr_inventory_is_paginated_and_unverified_owner_inventory_always_holds():
    t=_read(CONSUMER)
    assert 'pulls?state=open&per_page=100' in t
    assert 'pulls/${pr}/files?per_page=100' in t
    assert "gh api --paginate --slurp" in t
    assert "OWNER_SLICE_INVENTORY_UNVERIFIED" in t
    assert "echo '[]' > /tmp/active-owner-slices.json" not in t
    assert 'echo "true" > /tmp/owner-inventory-blocked' in t
    assert 'if [[ -f /tmp/owner-inventory-blocked ]]' in t
    assert "authenticated complete inventory unavailable" in t
    assert "if [[ \"$(jq 'length' /tmp/open-prs.json)\" -gt 0 ]]" not in t


def test_unverified_owner_inventory_is_a_successful_no_dispatch_hold():
    t = _read(CONSUMER)
    guard = t.split('if [[ -f /tmp/owner-inventory-blocked ]]; then', 1)[1].split('fi', 1)[0]
    tick = t.split('- name: Compute one safe queue-consumer tick', 1)[1]
    assert 'status=HOLD_OWNER_INVENTORY_UNVERIFIED' in guard
    assert '>> "$GITHUB_OUTPUT"' in guard
    assert "exit 0" in guard
    assert "exit 1" not in guard
    assert tick.index('if [[ -f /tmp/owner-inventory-blocked ]]') < tick.index(
        'python -m scripts.queue_auto_promotion_consumer'
    )
    # No dispatch-ready output is emitted for unverified owner inventory.
    assert "DISPATCH_READY" not in guard
    assert "gh workflow run" not in guard
    # Unrelated runtime errors still fail instead of being classified as HOLD.
    assert 'if [[ "$rc" -gt 1 ]]' in tick
    assert "QUEUE_CONSUMER_INVALID_PACKET" in tick


def _lease_state(comments, issue="828"):
    source = _read(CONSUMER)
    prefix = 'LEASE_STATE="$(jq -r --arg n "$number" ' + chr(39) + "\n"
    suffix = chr(39) + ' /tmp/comments.json)"'
    expression = source.split(prefix, 1)[1].split(suffix, 1)[0]
    result = subprocess.run(
        ["jq", "-r", "--arg", "n", issue, expression],
        input=json.dumps(comments),
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def _comment(body):
    return {"body": body}


def _event(status, issue="828", **kwargs):
    return json.dumps({"work_ref": f"issue:{issue}", "status": status, **kwargs})


@pytest.mark.parametrize(
    "comments",
    [
        [_comment('{"work_ref":"issue:828","status":'), _comment(_event("DISPATCH_LEASE_EXPIRED"))],
        [_comment(_event("DISPATCH_LEASE_EXPIRED")), _comment('{"work_ref":"issue:828","status":')],
        [_comment('{"work_ref":"issue:828","status":'), _comment(_event("ASSIGNED", lease_expires_at="2999-01-01T00:00:00Z"))],
        [_comment(_event("ASSIGNED", lease_expires_at="2999-01-01T00:00:00Z")), _comment('{"work_ref":"issue:828","status":')],
        [_comment('{"work_ref":"issue:828","status":'), _comment("unrelated status update")],
    ],
)
def test_cross_comment_ambiguity_cannot_be_overwritten(comments):
    assert _lease_state(comments) == "AMBIGUOUS"


def test_unrelated_comment_does_not_override_valid_retryable_event():
    comments = [_comment("unrelated status update"), _comment(_event("DISPATCH_LEASE_EXPIRED"))]
    assert _lease_state(comments) == "RETRYABLE"
def test_one_lease_and_canonical_dispatch():
    t=_read(CONSUMER); d=_read(DISPATCH); assert "DISPATCH_READY" in t and "gh workflow run ai-production-dispatch.yml" in t and '-f issue_number="$ISSUE_NUMBER"' in t and '-f lease_id="$LEASE_ID"' in t and '^lease-[0-9a-f]{32}$' in d and '^lease-[0-9a-f]{32}$' in t
def test_fail_closed(): t=_read(CONSUMER); assert "No safe candidate this tick" in t and "No executor dispatch this tick (fail-closed)" in t
def test_no_duplicate_fallback_policy(): t=_read(CONSUMER); assert ("quota" not in t.lower() or "provider health are owned by the existing" in t) and "amazon_q_free" not in t and "ai-production-followup.yml" not in t
def test_attributed_evidence(): t=_read(CONSUMER); assert "担当: 🌊ナギ" in t and "種別:" in t and "-F body=@/tmp/evidence-comment.md" in t
def test_no_merge_or_team_docs(): t=_read(CONSUMER); assert "gh pr merge" not in t and "enable-auto-merge" not in t and "TEAM_RULES.md" not in t and "TEAM_STATE.md" not in t

def test_adapter_exit_codes_are_not_silenced():
    t=_read(CONSUMER)
    assert "--output /tmp/packet.json || true" not in t
    assert 'if [[ "$rc" -gt 1 ]]' in t
    assert "QUEUE_CONSUMER_FAILED" in t
    assert "QUEUE_CONSUMER_INVALID_PACKET" in t
    assert "QUEUE_CONSUMER_EXIT_STATUS_MISMATCH" in t
    assert "steps.scan.outputs.candidate_count" in t

