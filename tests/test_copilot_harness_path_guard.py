from __future__ import annotations

import tempfile
from pathlib import Path
from scripts.copilot_harness_path_guard import check_generic_forbidden_paths, is_generic_forbidden, main


def test_exact_workflow_allow():
    changed = [".github/workflows/copilot-poc1.yml"]
    allowed = [".github/workflows/copilot-poc1.yml"]
    assert check_generic_forbidden_paths(changed, allowed) == []
    assert not is_generic_forbidden(".github/workflows/copilot-poc1.yml", allowed)


def test_wildcard_workflow_deny():
    changed = [".github/workflows/copilot-poc1.yml"]
    allowed = [".github/workflows/*"]
    assert check_generic_forbidden_paths(changed, allowed) == [".github/workflows/copilot-poc1.yml"]
    assert is_generic_forbidden(".github/workflows/copilot-poc1.yml", allowed)


def test_uncontracted_workflow_deny():
    changed = [".github/workflows/queue-auto-promotion-consumer.yml"]
    allowed = [".github/workflows/copilot-poc1.yml"]
    assert check_generic_forbidden_paths(changed, allowed) == [
        ".github/workflows/queue-auto-promotion-consumer.yml"
    ]
    assert is_generic_forbidden(".github/workflows/queue-auto-promotion-consumer.yml", allowed)


def test_second_uncontracted_workflow_deny():
    changed = [
        ".github/workflows/copilot-poc1.yml",
        ".github/workflows/other-workflow.yml",
    ]
    allowed = [".github/workflows/copilot-poc1.yml"]
    assert check_generic_forbidden_paths(changed, allowed) == [
        ".github/workflows/other-workflow.yml"
    ]


def test_dependency_file_deny():
    changed = ["package.json", "requirements.txt", "poetry.lock", "pyproject.toml", "uv.lock"]
    allowed = ["package.json", "requirements.txt", "poetry.lock", "pyproject.toml", "uv.lock"]
    assert check_generic_forbidden_paths(changed, allowed) == changed
    for p in changed:
        assert is_generic_forbidden(p, allowed)


def test_normal_file_allow():
    changed = ["scripts/copilot_harness_path_guard.py", "tests/test_copilot_harness_path_guard.py"]
    allowed = ["scripts/*", "tests/*"]
    assert check_generic_forbidden_paths(changed, allowed) == []


def test_cli_invocation_allow(tmp_path: Path):
    changed_file = tmp_path / "changed.txt"
    allowed_file = tmp_path / "allowed.txt"
    forbidden_out = tmp_path / "forbidden.txt"

    changed_file.write_text(".github/workflows/copilot-poc1.yml\nscripts/test.py\n")
    allowed_file.write_text(".github/workflows/copilot-poc1.yml\nscripts/*\n")

    import sys
    orig_argv = sys.argv
    try:
        sys.argv = [
            "copilot_harness_path_guard",
            "--changed-paths-file", str(changed_file),
            "--allowed-paths-file", str(allowed_file),
            "--forbidden-paths-output", str(forbidden_out),
        ]
        rc = main()
        assert rc == 0
        assert not forbidden_out.exists() or forbidden_out.read_text().strip() == ""
    finally:
        sys.argv = orig_argv


def test_cli_invocation_deny(tmp_path: Path):
    changed_file = tmp_path / "changed.txt"
    allowed_file = tmp_path / "allowed.txt"
    forbidden_out = tmp_path / "forbidden.txt"

    changed_file.write_text(".github/workflows/uncontracted.yml\npackage.json\n")
    allowed_file.write_text(".github/workflows/*\npackage.json\n")

    import sys
    orig_argv = sys.argv
    try:
        sys.argv = [
            "copilot_harness_path_guard",
            "--changed-paths-file", str(changed_file),
            "--allowed-paths-file", str(allowed_file),
            "--forbidden-paths-output", str(forbidden_out),
        ]
        rc = main()
        assert rc == 86
        assert forbidden_out.read_text().splitlines() == [
            ".github/workflows/uncontracted.yml",
            "package.json",
        ]
    finally:
        sys.argv = orig_argv
