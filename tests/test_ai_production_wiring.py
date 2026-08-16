from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPATCH = ROOT / ".github/workflows/ai-production-dispatch.yml"
PROMOTION = ROOT / ".github/workflows/copilot-patch-promotion.yml"


def test_ai_copilot_command_is_exact_after_outer_whitespace_and_crlf_normalization():
    text = DISPATCH.read_text(encoding="utf-8")
    assert "startsWith(github.event.comment.body, '/ai copilot')" not in text
    assert "tr -d '\\r'" in text
    assert "sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'" in text
    assert "[[ \"$normalized\" == '/ai copilot' ]]" in text
    assert "COMMAND_NOT_EXACT" in text


def test_promotion_persists_only_known_policy_block_with_provenance():
    text = PROMOTION.read_text(encoding="utf-8")
    assert "issues: write" in text
    assert "GitHub Actions is not permitted to create or approve pull requests" in text
    assert "PROMOTION_BRANCH_READY" in text
    assert "PR_CREATE_REQUIRED" in text
    assert "source_run_id" in text
    assert "promotion_commit=\"$(git rev-parse HEAD)\"" in text
    assert "HARNESS_OUTCOME" in text
    assert "UNEXPECTED_PR_CREATE_FAILURE" in text


def test_promotion_keeps_duplicate_pr_idempotency_before_fallback():
    text = PROMOTION.read_text(encoding="utf-8")
    assert 'gh pr list --state all --head "$PROMOTION_BRANCH"' in text
    assert "PR_ALREADY_EXISTS" in text
    assert "exit 0" in text
