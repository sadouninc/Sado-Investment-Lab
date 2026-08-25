from __future__ import annotations

import json
from pathlib import Path
import pytest

from scripts.copilot_poc1_harness_result import (
    build_harness_result,
    classify_outcome,
    parse_copilot_result,
    render_step_summary,
)


def test_parse_copilot_result_normal():
    content = """
outcome: REVIEW_READY
changed_files: scripts/foo.py, tests/test_foo.py
validation: python -m pytest -q
blocked_reason: NONE
confirmation_count: 0
"""
    res = parse_copilot_result(content)
    assert res["outcome"] == "REVIEW_READY"
    assert res["changed_files"] == ["scripts/foo.py", "tests/test_foo.py"]
    assert res["validation"] == "python -m pytest -q"
    assert res["blocked_reason"] is None
    assert res["confirmation_count"] == 0


def test_parse_copilot_result_blocked():
    content = """
outcome: BLOCKED
changed_files: NONE
validation: DEFERRED_TO_HARNESS
blocked_reason: ALREADY_IMPLEMENTED_OR_NO_DIFF
confirmation_count: 0
"""
    res = parse_copilot_result(content)
    assert res["outcome"] == "BLOCKED"
    assert res["changed_files"] == []
    assert res["validation"] == "DEFERRED_TO_HARNESS"
    assert res["blocked_reason"] == "ALREADY_IMPLEMENTED_OR_NO_DIFF"
    assert res["confirmation_count"] == 0


def test_classify_outcome_scenarios():
    # Preflight fail -> CONTROL_PLANE_FAIL
    assert classify_outcome("BLOCKED_CONTRACT_PREFLIGHT", "BLOCKED", False, []) == "CONTROL_PLANE_FAIL"

    # Scope fail -> SCOPE_FAIL
    assert classify_outcome("BLOCKED_ISSUE_PATH_CONTRACT", "ELIGIBLE", True, ["OUTSIDE_ALLOWED_PATHS bad.py"]) == "SCOPE_FAIL"

    # No diff -> NO_OUTPUT
    assert classify_outcome("BLOCKED_NO_REPO_DIFF", "ELIGIBLE", True, []) == "NO_OUTPUT"

    # Success -> SUCCESS
    assert classify_outcome("REVIEW_READY_VALIDATED", "ELIGIBLE", True, []) == "SUCCESS"

    # Missing result / Agent error -> HARNESS_ERROR
    assert classify_outcome("BLOCKED_RESULT_MISSING", "ELIGIBLE", True, []) == "HARNESS_ERROR"


def test_exit_78_fixture_preflight_blocked(tmp_path: Path):
    issue_file = tmp_path / "issue.json"
    issue_file.write_text(json.dumps({"number": 780, "title": "Test Issue"}), encoding="utf-8")

    preflight_file = tmp_path / "work-contract-preflight.json"
    preflight_file.write_text(json.dumps({"status": "BLOCKED", "reason_codes": ["CONTRACT_SCHEMA_MISSING"]}), encoding="utf-8")

    res = build_harness_result(
        issue_file=issue_file,
        work_contract_preflight_file=preflight_file,
        harness_outcome="BLOCKED_CONTRACT_PREFLIGHT",
        contract_preflight_outcome="BLOCKED",
    )

    assert res["schema_version"] == "1.0"
    assert res["issue_number"] == 780
    assert res["harness_outcome"] == "BLOCKED_CONTRACT_PREFLIGHT"
    assert res["contract_preflight_outcome"] == "BLOCKED"
    assert res["provider_execution_reached"] is False
    assert res["classification"] == "CONTROL_PLANE_FAIL"


def test_exit_85_fixture_scope_violations(tmp_path: Path):
    issue_file = tmp_path / "issue.json"
    issue_file.write_text(json.dumps({"number": 785}), encoding="utf-8")

    allowed_file = tmp_path / "allowed.txt"
    allowed_file.write_text("scripts/allowed.py\n", encoding="utf-8")

    forbidden_file = tmp_path / "forbidden.txt"
    forbidden_file.write_text("experiments/forbidden.py\n", encoding="utf-8")

    changed_file = tmp_path / "changed.txt"
    changed_file.write_text("experiments/forbidden.py\n", encoding="utf-8")

    scope_violations_file = tmp_path / "violations.txt"
    scope_violations_file.write_text("ISSUE_FORBIDDEN_PATH experiments/forbidden.py\n", encoding="utf-8")

    res = build_harness_result(
        issue_file=issue_file,
        allowed_paths_file=allowed_file,
        forbidden_paths_file=forbidden_file,
        changed_paths_file=changed_file,
        scope_violations_file=scope_violations_file,
        harness_outcome="BLOCKED_ISSUE_PATH_CONTRACT",
        contract_preflight_outcome="ELIGIBLE",
    )

    assert res["issue_number"] == 785
    assert res["harness_outcome"] == "BLOCKED_ISSUE_PATH_CONTRACT"
    assert res["contract_preflight_outcome"] == "ELIGIBLE"
    assert res["provider_execution_reached"] is True
    assert res["changed_files"] == ["experiments/forbidden.py"]
    assert res["scope_violations"] == ["ISSUE_FORBIDDEN_PATH experiments/forbidden.py"]
    assert res["classification"] == "SCOPE_FAIL"


def test_exit_87_fixture_no_diff(tmp_path: Path):
    issue_file = tmp_path / "issue.json"
    issue_file.write_text(json.dumps({"number": 787}), encoding="utf-8")

    copilot_result = tmp_path / "copilot-result.md"
    copilot_result.write_text("""
outcome: BLOCKED
changed_files: NONE
validation: DEFERRED_TO_HARNESS
blocked_reason: ALREADY_IMPLEMENTED_OR_NO_DIFF
confirmation_count: 0
""", encoding="utf-8")

    res = build_harness_result(
        issue_file=issue_file,
        copilot_result_file=copilot_result,
        harness_outcome="BLOCKED_NO_REPO_DIFF",
        contract_preflight_outcome="ELIGIBLE",
    )

    assert res["issue_number"] == 787
    assert res["harness_outcome"] == "BLOCKED_NO_REPO_DIFF"
    assert res["provider_execution_reached"] is True
    assert res["changed_files"] == []
    assert res["agent_declared_outcome"] == "BLOCKED"
    assert res["agent_blocked_reason"] == "ALREADY_IMPLEMENTED_OR_NO_DIFF"
    assert res["classification"] == "NO_OUTPUT"


def test_render_step_summary():
    data = {
        "issue_number": 790,
        "harness_outcome": "BLOCKED_ISSUE_PATH_CONTRACT",
        "classification": "SCOPE_FAIL",
        "contract_preflight_outcome": "ELIGIBLE",
        "provider_execution_reached": True,
        "changed_files": ["bad/path.py"],
        "scope_violations": ["OUTSIDE_ALLOWED_PATHS bad/path.py"],
        "agent_blocked_reason": None,
        "agent_declared_outcome": "REVIEW_READY",
    }

    summary = render_step_summary(data)
    assert "### Harness Diagnostic Evidence (v1)" in summary
    assert "#790" in summary
    assert "SCOPE_FAIL" in summary
    assert "OUTSIDE_ALLOWED_PATHS bad/path.py" in summary
