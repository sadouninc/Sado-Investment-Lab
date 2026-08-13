from __future__ import annotations

from pathlib import Path

import pytest

import scripts.copilot_poc_prepare as prepare


def test_issue_79_is_rejected_before_github_access(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare, "_github_get", lambda *_args, **_kwargs: pytest.fail("GitHub must not be queried"))
    with pytest.raises(ValueError, match="Issue #79"):
        prepare.prepare("sadouninc/Sado-Investment-Lab", 79, "token", tmp_path / "prompt.md")


def test_non_ready_issue_fails_closed(tmp_path, monkeypatch):
    def fake_get(path, _token):
        if path.endswith("/issues/12"):
            return {"state": "open", "title": "Not ready", "body": "## Goal\nSmall change"}
        if "/issues/12/comments" in path:
            return []
        raise AssertionError(path)

    monkeypatch.setattr(prepare, "_github_get", fake_get)
    with pytest.raises(ValueError, match="not explicitly READY"):
        prepare.prepare("sadouninc/Sado-Investment-Lab", 12, "token", tmp_path / "prompt.md")


def test_ready_comment_builds_bounded_prompt(tmp_path, monkeypatch):
    def fake_get(path, _token):
        if path.endswith("/issues/12"):
            return {
                "state": "open",
                "title": "Pilot fixture",
                "body": "## Goal\nAdd a small read-only helper.\n## Acceptance Criteria\n- tests green\n## Non-goal\n- no workflow change",
            }
        if "/issues/12/comments" in path:
            return [{"body": "Status: READY_FOR_IMPLEMENTATION\nAutonomy: STANDARD"}]
        if path.endswith("/issues/431"):
            return {"state": "closed", "body": "## Ask-only conditions\n- RED operations require approval"}
        raise AssertionError(path)

    monkeypatch.setattr(prepare, "_github_get", fake_get)
    monkeypatch.chdir(tmp_path)
    Path("TEAM_RULES.md").write_text("Issue #79 untouched", encoding="utf-8")
    output = Path("prompt.md")
    prepare.prepare("sadouninc/Sado-Investment-Lab", 12, "token", output)
    text = output.read_text(encoding="utf-8")
    assert "TARGET ISSUE: #12" in text
    assert "READY_FOR_IMPLEMENTATION" in text
    assert "Do not modify .github/workflows" in text
    assert "Do not run git commit, git push" in text
    assert "CONFIRMATION_COUNT=0" in text


def test_workflow_is_manual_and_remote_read_only():
    workflow = Path(".github/workflows/copilot-agentic-poc.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "pull_request:" not in workflow
    assert "push:" not in workflow
    assert "contents: read" in workflow
    assert "issues: read" in workflow
    assert "copilot-requests: write" in workflow
    assert "contents: write" not in workflow
    assert "issues: write" not in workflow
    assert "git push" not in workflow
    assert "git commit" not in workflow
    assert "--no-ask-user" in workflow
    assert "shell(python3:*)" in workflow
    assert "shell(git diff:*)" in workflow
