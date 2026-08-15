from pathlib import Path

import pytest

from scripts.copilot_patch_promotion import (
    acceptance_test_argv,
    evaluate_promotion,
    run_acceptance_tests,
)


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


def test_run_acceptance_tests_rejects_missing_contract_tests(tmp_path: Path):
    diagnostic = tmp_path / "contract.json"
    diagnostic.write_text('{"contract": {"acceptance_tests": []}}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="ISSUE_CONTRACT_INVALID"):
        run_acceptance_tests(diagnostic)
