from pathlib import Path


WORKFLOW = Path(".github/workflows/amazon-q-activation-diagnostic.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_owner_human_trigger_is_preserved():
    text = _text()
    assert "issue_comment:" in text
    assert "github.event.comment.body == '/q dev'" in text
    assert "github.actor == github.repository_owner" in text
    assert "github-actions[bot]" not in text
    assert "gh issue comment" not in text


def test_diagnostic_is_hard_scoped_to_sandbox_and_protects_79():
    text = _text()
    assert "github.event.issue.number == 700" in text
    assert '"$issue" != "700"' in text
    assert '"$issue" == "79"' in text
    assert "DIAGNOSTIC_TARGET_MUST_BE_700_AND_NEVER_79" in text


def test_workflow_is_read_only_and_records_machine_readable_result():
    text = _text()
    assert "issues: read" in text
    assert "pull-requests: read" in text
    assert "issues: write" not in text
    assert "contents: write" not in text
    assert '"amazon-q-developer[bot]"' in text
    assert 'status="TIMEOUT"' in text
    assert 'status="BOT_ACK"' in text
    assert 'status="PR_OPEN"' in text
    assert "actions/upload-artifact@v4" in text
    assert "bot_ack_latency_seconds" in text
