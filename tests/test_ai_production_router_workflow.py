from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPATCH = ROOT / ".github/workflows/ai-production-dispatch.yml"
FOLLOWUP = ROOT / ".github/workflows/ai-production-followup.yml"
COPILOT = ROOT / ".github/workflows/copilot-poc1.yml"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dispatch_is_owner_authenticated_ready_only_and_protects_79():
    text = _read(DISPATCH)
    assert "issue_comment:" in text
    assert "github.event.issue.pull_request == null" in text
    assert "github.event.comment.user.login == github.repository_owner" in text
    assert "startsWith(github.event.comment.body, '/ai copilot')" in text
    assert "READY_FOR_IMPLEMENTATION" in text
    assert '[[ "$issue" == "79" ]]' in text
    assert "DUPLICATE_ACTIVE_DISPATCH" in text
    assert "lease_expires_at" in text
    assert "'+60 minutes'" in text
    assert "gh workflow run copilot-poc1.yml" in text


def test_followup_reuses_promotion_and_policy_core_with_fail_closed_split():
    text = _read(FOLLOWUP)
    assert "workflow_run:" in text
    assert 'workflows: ["Copilot PoC1 — safe implementation lane"]' in text
    assert "NO_ACTIVE_PRODUCTION_COPILOT_LEASE" in text
    assert "scripts.ai_dispatch_policy import evaluate_dispatch_result" in text
    assert "PROMOTE_PATCH" in text
    assert "gh workflow run copilot-patch-promotion.yml" in text
    assert "FALLBACK_AMAZON_Q_FREE" in text
    assert 'engine:"amazon_q_free"' in text
    assert "/q dev Implement Issue #${ISSUE_NUMBER}" in text
    assert "BLOCKED_CONTRACT_PREFLIGHT" in text
    assert "BLOCKED_FORBIDDEN_PATH" in text
    assert "BLOCKED_ISSUE_PATH_CONTRACT" in text


def test_manual_poc_identity_is_explicit_and_auto_green_is_not_enabled():
    copilot = _read(COPILOT)
    dispatch = _read(DISPATCH)
    followup = _read(FOLLOWUP)
    assert "run-name: Copilot PoC1 — issue ${{ inputs.issue_number }}" in copilot
    combined = dispatch + followup
    assert "enable-auto-merge" not in combined
    assert "gh pr merge" not in combined
    assert "pull-requests: write" not in combined
