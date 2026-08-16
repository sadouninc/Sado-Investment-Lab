import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPATCH = ROOT / ".github/workflows/ai-production-dispatch.yml"
PROMOTION = ROOT / ".github/workflows/copilot-patch-promotion.yml"


def _dispatch_status_set(name: str) -> set[str]:
    text = DISPATCH.read_text(encoding="utf-8")
    match = re.search(rf"{name}\s*=\s*(\{{.*?\}})", text, re.DOTALL)
    assert match, f"missing {name}"
    return set(ast.literal_eval(match.group(1)))


def _replay_dispatch_state(statuses: list[str]) -> tuple[bool, bool]:
    """Replay the workflow's ordered terminal/retry state contract."""
    retryable_statuses = _dispatch_status_set("retryable_statuses")
    terminalizing_statuses = _dispatch_status_set("terminalizing_statuses")
    terminalizing = False
    retryable = False
    for status in statuses:
        if status in retryable_statuses:
            retryable = True
            terminalizing = False
            continue
        if status in terminalizing_statuses:
            terminalizing = True
            retryable = False
    return terminalizing, retryable


def test_ai_copilot_command_is_exact_after_outer_whitespace_and_crlf_normalization():
    text = DISPATCH.read_text(encoding="utf-8")
    assert "startsWith(github.event.comment.body, '/ai copilot')" not in text
    assert "tr -d '\\r'" in text
    assert "sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'" in text
    assert "[[ \"$normalized\" == '/ai copilot' ]]" in text
    assert "COMMAND_EXACT_ACCEPTED" in text
    assert "COMMAND_NOT_EXACT_SKIP" in text
    assert 'echo "accepted=true" >> "$GITHUB_OUTPUT"' in text
    assert 'echo "accepted=false" >> "$GITHUB_OUTPUT"' in text
    assert "exit 78" not in text.split("- name: Fail closed and validate READY issue", 1)[0]


def test_dispatcher_suppresses_duplicate_redispatch_during_promotion_terminalization():
    text = DISPATCH.read_text(encoding="utf-8")
    # Regression for #666: a second exact command after PROMOTION_DISPATCHED must
    # terminate successfully before a second paid Copilot source run is started.
    assert "PROMOTION_DISPATCHED" in text
    assert "PROMOTION_BRANCH_READY" in text
    assert "PR_CREATE_REQUIRED" in text
    assert "DUPLICATE_SUPERSEDED" in text
    assert "DUPLICATE_PROMOTION_TERMINALIZATION_SKIP" in text
    assert "DUPLICATE_EXISTING_PR_SKIP" in text
    assert "DUPLICATE_ACTIVE_DISPATCH_SKIP" in text
    assert 'echo "dispatch_allowed=false" >> "$GITHUB_OUTPUT"' in text
    assert "steps.gate.outputs.dispatch_allowed == 'true'" in text


def test_base_drift_reopens_prior_promotion_for_fresh_dispatch():
    terminalizing, retryable = _replay_dispatch_state(
        ["PROMOTION_DISPATCHED", "BLOCKED_BASE_DRIFT"]
    )
    assert retryable is True
    assert terminalizing is False


def test_pr_handoff_after_promotion_remains_non_redispatchable():
    terminalizing, retryable = _replay_dispatch_state(
        ["PROMOTION_DISPATCHED", "PR_CREATE_REQUIRED"]
    )
    assert retryable is False
    assert terminalizing is True


def test_retryable_reset_is_ordered_before_later_terminal_evidence():
    # A fresh terminal state after a retry reset must close the lane again.
    terminalizing, retryable = _replay_dispatch_state(
        ["PROMOTION_DISPATCHED", "BLOCKED_BASE_DRIFT", "PROMOTION_DISPATCHED"]
    )
    assert retryable is False
    assert terminalizing is True


def test_dispatcher_keeps_expired_and_explicit_retryable_paths_redispatchable():
    text = DISPATCH.read_text(encoding="utf-8")
    retryable_statuses = _dispatch_status_set("retryable_statuses")
    assert "lease_expires_at" in text
    assert "expiry > now" in text
    assert {
        "DISPATCH_LEASE_EXPIRED",
        "COPILOT_RETRYABLE_FAILURE",
        "RETRYABLE_FAILURE",
        "FALLBACK_RETRYABLE_FAILURE",
        "BLOCKED_BASE_DRIFT",
    } <= retryable_statuses
    assert "retryable = True" in text
    assert "terminalizing = False" in text
    assert "active_lease = False" in text
    assert "recorded_branch = ''" in text
    assert "fallback_owner:\"amazon_q_free\"" in text


def test_active_lease_guard_precedes_terminalization_and_dispatch():
    text = DISPATCH.read_text(encoding="utf-8")
    active_guard = text.index("DUPLICATE_ACTIVE_DISPATCH_SKIP")
    terminal_guard = text.index("DUPLICATE_PROMOTION_TERMINALIZATION_SKIP")
    dispatch = text.index("Dispatch Copilot and explicitly hand off completion")
    assert active_guard < terminal_guard < dispatch


def test_promotion_persists_only_known_policy_block_with_provenance():
    text = PROMOTION.read_text(encoding="utf-8")
    assert "issues: write" in text
    assert "GitHub Actions is not permitted to create or approve pull requests" in text
    assert "PROMOTION_BRANCH_READY" in text
    assert "PR_CREATE_REQUIRED" in text
    assert "source_run_id" in text
    assert 'git push origin "$PROMOTION_BRANCH"\n          promotion_commit="$(git rev-parse HEAD)"' in text
    assert "HARNESS_OUTCOME" in text
    assert "UNEXPECTED_PR_CREATE_FAILURE" in text


def test_promotion_keeps_duplicate_pr_idempotency_before_and_after_create_race():
    text = PROMOTION.read_text(encoding="utf-8")
    assert text.count('gh pr list --state all --head "$PROMOTION_BRANCH"') >= 2
    assert "PR_ALREADY_EXISTS" in text
    assert "PR_ALREADY_EXISTS_RACE_RESOLVED" in text
    assert "group: copilot-patch-promotion-${{ inputs.issue_number }}-${{ inputs.source_run_id }}" in text
    assert "exit 0" in text
