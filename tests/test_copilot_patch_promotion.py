from pathlib import Path

import pytest

from scripts.copilot_patch_promotion import (
    acceptance_test_argv,
    evaluate_promotion,
    run_acceptance_tests,
)


ROOT = Path(__file__).resolve().parents[1]
PROMOTION_WORKFLOW = ROOT / ".github" / "workflows" / "copilot-patch-promotion.yml"


def base(**overrides):
    values = dict(
        issue_number=603,
        source_run_success=True,
        harness_outcome="REVIEW_READY_VALIDATED",
        source_base_sha="abc",
        current_base_sha="abc",
        changed_paths=["scripts/example.py"],
        allowed_paths=["scripts/*.py"],
        forbidden_paths=["scripts/private/**"],
    )
    values.update(overrides)
    return evaluate_promotion(**values)


def test_validated_same_base_allowed_path_is_eligible():
    assert base().reason == "ELIGIBLE"
    assert base().eligible is True


def test_non_validated_outcome_blocks():
    assert base(harness_outcome="BLOCKED").reason == "SOURCE_NOT_REVIEW_READY_VALIDATED"


def test_base_drift_blocks():
    assert base(current_base_sha="def").reason == "BASE_SHA_MISMATCH"


def test_outside_allowed_blocks():
    assert base(changed_paths=["docs/x.md"]).reason == "OUTSIDE_ALLOWED_PATHS"


def test_forbidden_path_blocks():
    assert base(changed_paths=["scripts/private/x.py"], allowed_paths=["scripts/**"]).reason == "FORBIDDEN_PATH"


def test_issue_79_blocks():
    assert base(issue_number=79).reason == "PROTECTED_ISSUE_79"


def test_missing_metadata_never_passes():
    assert base(source_base_sha=None).reason == "MALFORMED_METADATA"


def test_duplicate_pr_blocks():
    assert base(duplicate_pr_exists=True).reason == "PR_ALREADY_EXISTS"


def test_already_applied_blocks():
    assert base(already_applied=True).reason == "ALREADY_APPLIED"


def test_empty_changed_path_blocks():
    assert base(changed_paths=[""]).reason == "ISSUE_CONTRACT_INVALID"


def test_whitespace_only_changed_path_blocks():
    assert base(changed_paths=[" "]).reason == "ISSUE_CONTRACT_INVALID"
    assert base(changed_paths=["  "]).reason == "ISSUE_CONTRACT_INVALID"
    assert base(changed_paths=["\t"]).reason == "ISSUE_CONTRACT_INVALID"
    assert base(changed_paths=["\n"]).reason == "ISSUE_CONTRACT_INVALID"
    assert base(changed_paths=["   \t  \n  "]).reason == "ISSUE_CONTRACT_INVALID"


def test_mixed_valid_and_blank_changed_paths_blocks():
    assert base(changed_paths=["scripts/valid.py", ""]).reason == "ISSUE_CONTRACT_INVALID"
    assert base(changed_paths=["scripts/valid.py", "  "]).reason == "ISSUE_CONTRACT_INVALID"


def test_empty_allowed_path_blocks():
    assert base(allowed_paths=[""]).reason == "ISSUE_CONTRACT_INVALID"


def test_whitespace_only_allowed_path_blocks():
    assert base(allowed_paths=[" "]).reason == "ISSUE_CONTRACT_INVALID"
    assert base(allowed_paths=["  "]).reason == "ISSUE_CONTRACT_INVALID"
    assert base(allowed_paths=["\t"]).reason == "ISSUE_CONTRACT_INVALID"
    assert base(allowed_paths=["\n"]).reason == "ISSUE_CONTRACT_INVALID"
    assert base(allowed_paths=["   \t  \n  "]).reason == "ISSUE_CONTRACT_INVALID"


def test_mixed_valid_and_blank_allowed_paths_blocks():
    assert base(allowed_paths=["scripts/*.py", ""]).reason == "ISSUE_CONTRACT_INVALID"
    assert base(allowed_paths=["scripts/*.py", "  "]).reason == "ISSUE_CONTRACT_INVALID"


def test_valid_only_allowed_paths_passes():
    assert base(allowed_paths=["scripts/*.py"]).eligible is True
    assert base(allowed_paths=["scripts/*.py", "tests/*.py"]).eligible is True


def test_acceptance_command_allowlist_accepts_pytest_variants():
    assert acceptance_test_argv("python -m pytest -q tests/test_x.py") == [
        "python",
        "-m",
        "pytest",
        "-q",
        "tests/test_x.py",
    ]
    assert acceptance_test_argv("pytest -q") == ["pytest", "-q"]


def test_acceptance_command_allowlist_rejects_shell_or_other_commands():
    with pytest.raises(ValueError, match="UNSUPPORTED_ACCEPTANCE_TEST"):
        acceptance_test_argv("bash -c 'echo unsafe'")


def test_declarative_acceptance_is_not_executed(tmp_path: Path):
    diagnostic = tmp_path / "contract.json"
    diagnostic.write_text(
        '{"contract": {"acceptance_tests": ["Sony #403 fixtureを10-factor schemaへlosslessに表現できる"]}}',
        encoding="utf-8",
    )
    run_acceptance_tests(diagnostic)


def test_explicit_executable_acceptance_uses_pytest_allowlist(tmp_path: Path, monkeypatch):
    diagnostic = tmp_path / "contract.json"
    diagnostic.write_text(
        '{"contract": {"acceptance_tests": ["declarative"], "executable_acceptance_tests": ["python -m pytest -q tests/test_x.py"]}}',
        encoding="utf-8",
    )
    seen = []

    class Completed:
        returncode = 0

    monkeypatch.setattr("scripts.copilot_patch_promotion.subprocess.run", lambda argv, check=False: seen.append(argv) or Completed())
    run_acceptance_tests(diagnostic)
    assert seen == [["python", "-m", "pytest", "-q", "tests/test_x.py"]]


def test_executable_acceptance_rejects_arbitrary_command(tmp_path: Path):
    diagnostic = tmp_path / "contract.json"
    diagnostic.write_text(
        '{"contract": {"acceptance_tests": ["declarative"], "executable_acceptance_tests": ["bash -c \\\"echo unsafe\\\""]}}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="UNSUPPORTED_ACCEPTANCE_TEST"):
        run_acceptance_tests(diagnostic)


def test_malformed_executable_acceptance_fails_closed(tmp_path: Path):
    diagnostic = tmp_path / "contract.json"
    diagnostic.write_text(
        '{"contract": {"acceptance_tests": ["declarative"], "executable_acceptance_tests": "pytest -q"}}',
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="ISSUE_CONTRACT_INVALID"):
        run_acceptance_tests(diagnostic)


def test_promotion_workflow_allows_terminal_escape_sequences_but_keeps_harness_gate():
    workflow = PROMOTION_WORKFLOW.read_text(encoding="utf-8")
    assert (
        'gh api --allow-escape-sequences "repos/${GITHUB_REPOSITORY}/actions/jobs/${job_id}/logs"'
        in workflow
    )
    assert "grep -q 'HARNESS_OUTCOME=REVIEW_READY_VALIDATED' /tmp/source.log" in workflow
    assert "SOURCE_NOT_REVIEW_READY_VALIDATED" in workflow


def test_promotion_policy_fallback_requires_validated_branch_and_known_error_only():
    workflow = PROMOTION_WORKFLOW.read_text(encoding="utf-8")
    assert "issues: write" in workflow
    assert 'promotion_commit="$(git rev-parse HEAD)"' in workflow
    assert 'git push origin "$PROMOTION_BRANCH"' in workflow
    assert "GitHub Actions is not permitted to create or approve pull requests" in workflow
    assert "PROMOTION_BRANCH_READY" in workflow
    assert "PR_CREATE_REQUIRED" in workflow
    assert "UNEXPECTED_PR_CREATE_FAILURE" in workflow
    assert 'exit "$pr_rc"' in workflow
