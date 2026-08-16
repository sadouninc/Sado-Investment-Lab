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


def test_dispatch_serializes_same_issue_before_lease_check_and_creation():
    text = _read(DISPATCH)
    assert "concurrency:" in text
    assert "group: ai-production-dispatch-${{ github.event.issue.number }}" in text
    assert "cancel-in-progress: false" in text


def test_dispatch_and_followup_build_valid_json_across_comment_pagination():
    dispatch = _read(DISPATCH)
    followup = _read(FOLLOWUP)
    for text in (dispatch, followup):
        assert "/comments?per_page=100&page=${page}" in text
        assert "jq -c '.' /tmp/comment-page.json" in text
        assert "jq -s 'add // []'" in text
        assert "gh api --paginate" not in text


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
    assert "BLOCKED_NO_REPO_DIFF" in text


def test_followup_fails_closed_when_source_logs_are_unavailable():
    text = _read(FOLLOWUP)
    assert '[[ ! -s /tmp/run.log ]]' in text
    assert "FAILED_TO_RETRIEVE_LOGS" in text
    assert 'echo "action=NONE" >> "$GITHUB_OUTPUT"' in text


def test_followup_passes_classifier_data_through_environment():
    text = _read(FOLLOWUP)
    assert 'ISSUE_NUMBER="$issue" OUTCOME="$outcome" RETRYABLE="$retryable"' in text
    assert 'RUN_CONCLUSION_VALUE="$RUN_CONCLUSION" python' in text
    assert "int(os.environ['ISSUE_NUMBER'])" in text
    assert "os.environ['OUTCOME']" in text
    assert "int('$issue')" not in text


def test_terminal_copilot_results_close_active_lease_lifecycle():
    text = _read(FOLLOWUP)
    assert 'status:"PROMOTION_DISPATCHED"' in text
    assert 'status:"FAIL_CLOSED"' in text
    assert "source_run_id" in text


def test_manual_poc_identity_is_explicit_and_auto_green_is_not_enabled():
    copilot = _read(COPILOT)
    dispatch = _read(DISPATCH)
    followup = _read(FOLLOWUP)
    assert "run-name: Copilot PoC1 — issue ${{ inputs.issue_number }}" in copilot
    combined = dispatch + followup
    assert "enable-auto-merge" not in combined
    assert "gh pr merge" not in combined
    assert "pull-requests: write" not in combined
