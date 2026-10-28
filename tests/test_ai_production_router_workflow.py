from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPATCH = ROOT / ".github/workflows/ai-production-dispatch.yml"
FOLLOWUP = ROOT / ".github/workflows/ai-production-followup.yml"
COPILOT = ROOT / ".github/workflows/copilot-poc1.yml"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dispatch_is_dual_ingress_ready_only_and_protects_79():
    text = _read(DISPATCH)
    assert "issue_comment:" in text
    assert "workflow_dispatch:" in text
    assert "github.event.issue.pull_request == null" in text
    assert "github.event.comment.user.login == github.repository_owner" in text
    assert "Validate dispatch ingress" in text
    assert "tr -d '\\r'" in text
    assert "[[ \"$normalized\" == '/ai copilot' ]]" in text
    assert "startsWith(github.event.comment.body, '/ai copilot')" not in text
    assert "COMMAND_NOT_EXACT_SKIP" in text
    assert 'echo "accepted=false" >> "$GITHUB_OUTPUT"' in text
    assert text.count("if: steps.command.outputs.accepted == 'true'") >= 2
    assert "READY_FOR_IMPLEMENTATION" in text
    assert '[[ "$ROUTED_ISSUE" != "79" ]]' in text
    assert '[[ "$issue" != "79" ]]' in text
    assert "PROTECTED_ISSUE_79" in text
    assert "CANONICAL_LEASE_EVIDENCE_MISSING" in text
    assert "AUTO_ROUTER_DISPATCH lease_id=${LEASE_ID} executor=COPILOT target_issue=${issue}" in text
    assert "DUPLICATE_ACTIVE_DISPATCH" in text
    assert "DUPLICATE_EXISTING_PR_SKIP" in text
    assert "DUPLICATE_PROMOTION_TERMINALIZATION_SKIP" in text
    assert "lease_expires_at" in text
    assert "'+60 minutes'" in text
    assert "gh workflow run copilot-poc1.yml" in text


def test_dispatch_serializes_same_issue_for_both_ingress_paths():
    text = _read(DISPATCH)
    assert "concurrency:" in text
    assert "group: ai-production-dispatch-${{ github.event_name == 'workflow_dispatch' && inputs.issue_number || github.event.issue.number }}" in text
    assert "cancel-in-progress: false" in text


def test_dispatch_explicitly_waits_for_source_and_dispatches_followup():
    text = _read(DISPATCH)
    assert "timeout-minutes: 30" in text
    assert "COPILOT_SOURCE_RUN_NOT_FOUND" in text
    assert 'gh run watch "$source_run_id"' in text
    assert "source_conclusion=" in text
    assert "gh workflow run ai-production-followup.yml" in text
    assert '-f source_run_id="$source_run_id"' in text
    assert '-f source_conclusion="$source_conclusion"' in text


def test_source_run_resolution_uses_jq_args_and_tolerates_api_delay():
    text = _read(DISPATCH)
    assert "for _ in {1..60}; do" in text
    assert '> /tmp/copilot-runs.json' in text
    assert '--arg title "$source_title"' in text
    assert '--arg started "$request_started"' in text
    assert '.display_title == $title' in text
    assert '.created_at >= $started' in text
    assert '.display_title == \\"${source_title}\\"' not in text


def test_dispatch_and_followup_build_valid_json_across_comment_pagination():
    dispatch = _read(DISPATCH)
    followup = _read(FOLLOWUP)
    for text in (dispatch, followup):
        assert "/comments?per_page=100&page=${page}" in text
        assert "jq -c '.' /tmp/comment-page.json" in text
        assert "jq -s 'add // []'" in text
        assert "gh api --paginate" not in text


def test_followup_is_explicit_dispatch_not_workflow_run_only():
    text = _read(FOLLOWUP)
    assert "workflow_dispatch:" in text
    assert "source_run_id:" in text
    assert "source_conclusion:" in text
    assert "workflow_run:" not in text
    assert "group: ai-production-followup-${{ inputs.source_run_id }}" in text
    assert "RUN_ID: ${{ inputs.source_run_id }}" in text
    assert "ISSUE_HINT: ${{ inputs.issue_number }}" in text
    assert "RUN_CONCLUSION: ${{ inputs.source_conclusion }}" in text


def test_followup_reuses_promotion_and_policy_core_with_fail_closed_split():
    text = _read(FOLLOWUP)
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


def test_followup_ignores_manual_or_duplicate_run_without_active_lease():
    text = _read(FOLLOWUP)
    assert "No active production Copilot lease; ignore manual/duplicate source run." in text
    assert 'reason=NO_ACTIVE_PRODUCTION_COPILOT_LEASE' in text
    assert "steps.classify.outputs.reason != 'NO_ACTIVE_PRODUCTION_COPILOT_LEASE'" in text


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
    assert "RUN_ID: ${{ steps.classify.outputs.source_run_id }}" in text


def test_manual_poc_identity_is_explicit_and_auto_green_is_not_enabled():
    copilot = _read(COPILOT)
    dispatch = _read(DISPATCH)
    followup = _read(FOLLOWUP)
    assert "run-name: Copilot PoC1 — issue ${{ inputs.issue_number }}" in copilot
    combined = dispatch + followup
    assert "enable-auto-merge" not in combined
    assert "gh pr merge" not in combined
    assert "pull-requests: write" not in combined


def _verify_assigned_comment_fixture(comment: dict, *, predicate_override: str | None = None) -> bool:
    """Exercise the workflow's actual jq filter, not a second Python parser."""
    import json
    import shutil
    import subprocess

    import pytest

    if shutil.which("jq") is None:
        pytest.skip("jq is required by the production workflow")
    workflow = _read(DISPATCH)
    start = workflow.index("'(.id == $cid) and") + 1
    end = workflow.index("' >/dev/null", start)
    predicate = predicate_override if predicate_override is not None else workflow[start:end]
    result = subprocess.run(
        [
            "jq", "-e", "--arg", "repository", "sadouninc/Sado-Investment-Lab",
            "--arg", "issue", "859",
            "--arg", "lease", "lease-" + "a" * 32,
            "--argjson", "run_id", "12345",
            "--argjson", "cid", "67890",
            predicate,
        ],
        input=json.dumps(comment),
        text=True,
        capture_output=True,
        check=False,
    )
    # jq -e returns 1 for a genuine false result; syntax/runtime failures
    # must fail the test rather than masquerade as a negative fixture.
    if result.stderr.strip() or result.returncode not in (0, 1):
        raise AssertionError(
            f"jq predicate execution failed (rc={result.returncode}): {result.stderr.strip()}"
        )
    return result.returncode == 0


def test_assigned_linkage_validates_comment_identity_with_jq():
    import json

    event = {
        "work_ref": "issue:859",
        "status": "ASSIGNED",
        "canonical_lease_id": "lease-" + "a" * 32,
        "writer_run_id": 12345,
    }
    comment = {
        "id": 67890,
        "issue_url": "https://api.github.com/repos/sadouninc/Sado-Investment-Lab/issues/859",
        "user": {"login": "github-actions[bot]"},
        "body": "<!-- flow-dispatch-lease -->\n" + json.dumps(event)
                + "\n\n担当: ソラ / Copilot Lease",
    }
    assert _verify_assigned_comment_fixture(comment)

    for key, wrong in (
        ("id", 67891),
        ("issue_url", "https://api.github.com/repos/sadouninc/Sado-Investment-Lab/issues/860"),
        ("user", {"login": "other-user"}),
        ("body", "<!-- flow-dispatch-lease -->\n{not-json}"),
    ):
        bad = dict(comment)
        bad[key] = wrong
        assert not _verify_assigned_comment_fixture(bad), key

    for key, wrong in (
        ("work_ref", "issue:860"),
        ("status", "ACKNOWLEDGED"),
        ("canonical_lease_id", "lease-" + "b" * 32),
        ("writer_run_id", 12346),
    ):
        bad = dict(comment)
        bad["body"] = "<!-- flow-dispatch-lease -->\n" + json.dumps({**event, key: wrong})
        assert not _verify_assigned_comment_fixture(bad), key


def test_assigned_linkage_schema_and_comment_id_are_run_bound():
    text = _read(DISPATCH)
    assert '--argjson writer_run_id "$GITHUB_RUN_ID"' in text
    assert 'writer_run_id:$writer_run_id' in text
    assert 'comment_id="$(jq -er' in text
    assert "select(type == \"number\" and . > 0)" in text
    assert 'gh api "repos/${GITHUB_REPOSITORY}/issues/comments/${comment_id}"' in text
    assert "schema_version:2,comment_id:$comment_id,writer_run_id:$writer_run_id" in text
    assert "issue_number:($issue|tonumber)" in text
    assert "issue_number:$issue" not in text
    assert 'workflow_path:".github/workflows/ai-production-dispatch.yml"' in text
    assert "ai-production-assigned-linkage.json" in text
    assert 'echo "lease_id=owner-command"' in text  # Historical command != canonical lease.


def test_assigned_linkage_upload_failure_blocks_copilot_dispatch():
    text = _read(DISPATCH)
    upload = text.index("- name: Preserve run-owned Copilot assignment linkage")
    dispatch = text.index("- name: Dispatch Copilot and explicitly hand off completion")
    assert upload < dispatch
    assert "id: assigned_linkage" in text[upload:dispatch]
    assert "uses: actions/upload-artifact@v4" in text[upload:dispatch]
    assert "name: ai-production-assigned-linkage-" + "$" + "{{ github.run_id }}" in text[upload:dispatch]
    assert "if-no-files-found: error" in text[upload:dispatch]
    assert "continue-on-error:" not in text[upload:dispatch]
    assert "steps.assigned_linkage.outcome == 'success'" in text[dispatch:]
    assert "gh workflow run copilot-poc1.yml" in text[dispatch:]
    assert "pull-requests: write" not in text
    assert "gh pr merge" not in text


def test_assigned_linkage_jq_predicate_error_is_not_a_negative_match():
    import pytest

    with pytest.raises(AssertionError, match="jq predicate execution failed"):
        _verify_assigned_comment_fixture({"id": 67890}, predicate_override="invalid jq syntax !!!")


def test_assigned_linkage_issue_number_is_numeric_in_actual_jq_schema():
    import json
    import shutil
    import subprocess

    import pytest

    if shutil.which("jq") is None:
        pytest.skip("jq is required by the production workflow")
    workflow = _read(DISPATCH)
    start = workflow.index("'{schema_version:2,comment_id:$comment_id") + 1
    end = workflow.index("}' \\\n", start) + 1
    predicate = workflow[start:end]
    result = subprocess.run(
        ["jq", "-nc", "--argjson", "comment_id", "67890",
         "--argjson", "writer_run_id", "12345", "--arg", "issue", "859",
         "--arg", "lease", "lease-" + "a" * 32,
         "--arg", "repository", "sadouninc/Sado-Investment-Lab", predicate],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["issue_number"] == 859
    assert type(payload["issue_number"]) is int
    assert type(payload["comment_id"]) is int
    assert type(payload["writer_run_id"]) is int


def test_assigned_comment_without_artifact_remains_duplicate_hold():
    workflow = _read(DISPATCH)
    assert "DUPLICATE_ACTIVE_DISPATCH_SKIP" in workflow
    assert "date -u -d '+60 minutes'" in workflow
    assert "remains visible to the duplicate gate until its 60-minute expiry" in workflow
    assert "steps.assigned_linkage.outcome == 'success'" in workflow
    assert "Never treat comment-only evidence as authenticated" in workflow
