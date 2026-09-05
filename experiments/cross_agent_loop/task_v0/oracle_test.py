"""Oracle test suite for Cross-Agent Loop Phase 1 Task v0.

This test suite implements the 7 minimum oracle checks:
1. syntax/import succeeds
2. required public function/signature exists
3. valid fixture normalized exactly
4. malformed required field rejected
5. unknown field/state does not become normal success
6. deterministic repeated run
7. only allowed solver path changed

Oracle results: PASS | SYNTAX_FAIL | SEMANTIC_FAIL | SCOPE_FAIL | 
                NO_OUTPUT | HARNESS_ERROR | CONTROL_PLANE_FAIL
"""

import importlib
import json
import os
import sys
from pathlib import Path

import pytest


class OracleResult:
    """Oracle result classification."""
    PASS = "PASS"
    SYNTAX_FAIL = "SYNTAX_FAIL"
    SEMANTIC_FAIL = "SEMANTIC_FAIL"
    SCOPE_FAIL = "SCOPE_FAIL"
    NO_OUTPUT = "NO_OUTPUT"
    HARNESS_ERROR = "HARNESS_ERROR"
    CONTROL_PLANE_FAIL = "CONTROL_PLANE_FAIL"


@pytest.fixture
def solution_module():
    """Import solution module - Oracle Check 1: syntax/import succeeds."""
    try:
        # Ensure the module is fresh
        if 'experiments.cross_agent_loop.task_v0.solution' in sys.modules:
            importlib.reload(sys.modules['experiments.cross_agent_loop.task_v0.solution'])
        else:
            import experiments.cross_agent_loop.task_v0.solution
        return sys.modules['experiments.cross_agent_loop.task_v0.solution']
    except (ImportError, SyntaxError) as e:
        pytest.fail(f"Oracle Check 1 FAILED (SYNTAX_FAIL): {e}")


@pytest.fixture
def normalize_records(solution_module):
    """Get normalize_records function - Oracle Check 2: required function signature exists."""
    if not hasattr(solution_module, 'normalize_records'):
        pytest.fail("Oracle Check 2 FAILED (SEMANTIC_FAIL): normalize_records function not found")
    
    func = getattr(solution_module, 'normalize_records')
    if not callable(func):
        pytest.fail("Oracle Check 2 FAILED (SEMANTIC_FAIL): normalize_records is not callable")
    
    return func


@pytest.fixture
def input_fixture():
    """Load input fixture."""
    fixture_path = Path(__file__).parent / "input_fixture.json"
    if not fixture_path.exists():
        pytest.fail(f"HARNESS_ERROR: input_fixture.json not found at {fixture_path}")
    
    with open(fixture_path) as f:
        return json.load(f)


def test_oracle_check_1_syntax_import(solution_module):
    """Oracle Check 1: syntax/import succeeds."""
    assert solution_module is not None
    assert hasattr(solution_module, '__name__')


def test_oracle_check_2_function_signature(normalize_records):
    """Oracle Check 2: required public function/signature exists."""
    assert callable(normalize_records)
    # Check it accepts at least 1 argument (records list)
    import inspect
    sig = inspect.signature(normalize_records)
    assert len(sig.parameters) >= 1, "normalize_records must accept at least 1 parameter"


def test_oracle_check_3_valid_fixture_normalized(normalize_records, input_fixture):
    """Oracle Check 3: valid fixture normalized exactly."""
    # Test valid_complete
    result = normalize_records(input_fixture["test_cases"]["valid_complete"])
    assert "normalized" in result, "Output must have 'normalized' key"
    assert "rejected" in result, "Output must have 'rejected' key"
    
    normalized = result["normalized"]
    assert len(normalized) == 1, "Should normalize exactly 1 valid_complete record"
    
    rec = normalized[0]
    assert rec["id"] == "rec001", "id should be preserved"
    assert rec["name"] == "alpha", "name should be lowercased"
    assert rec["value"] == 100, "value should be preserved"
    assert rec["status"] == "pending", "status should be preserved"
    assert len(result["rejected"]) == 0, "No records should be rejected"
    
    # Test valid_minimal with defaults
    result = normalize_records(input_fixture["test_cases"]["valid_minimal"])
    normalized = result["normalized"]
    assert len(normalized) == 1, "Should normalize exactly 1 valid_minimal record"
    
    rec = normalized[0]
    assert rec["id"] == "rec002", "id should be preserved"
    assert rec["name"] == "beta", "name should be lowercased"
    assert rec["value"] == 0, "value should default to 0"
    assert rec["status"] == "active", "status should default to 'active'"
    assert len(result["rejected"]) == 0, "No records should be rejected"


def test_oracle_check_4_malformed_required_field_rejected(normalize_records, input_fixture):
    """Oracle Check 4: malformed required field rejected."""
    # Test missing id
    result = normalize_records(input_fixture["test_cases"]["invalid_missing_id"])
    assert len(result["normalized"]) == 0, "Record with missing id should not be normalized"
    assert len(result["rejected"]) == 1, "Record with missing id should be rejected"
    
    rejected = result["rejected"][0]
    assert "record" in rejected, "Rejected item must have 'record' field"
    assert "reason" in rejected, "Rejected item must have 'reason' field"
    assert "id" in rejected["reason"].lower() or "required" in rejected["reason"].lower(), \
        "Rejection reason should mention missing id or required field"
    
    # Test missing name
    result = normalize_records(input_fixture["test_cases"]["invalid_missing_name"])
    assert len(result["normalized"]) == 0, "Record with missing name should not be normalized"
    assert len(result["rejected"]) == 1, "Record with missing name should be rejected"
    
    rejected = result["rejected"][0]
    assert "record" in rejected, "Rejected item must have 'record' field"
    assert "reason" in rejected, "Rejected item must have 'reason' field"
    assert "name" in rejected["reason"].lower() or "required" in rejected["reason"].lower(), \
        "Rejection reason should mention missing name or required field"


def test_oracle_check_5_unknown_field_rejected(normalize_records, input_fixture):
    """Oracle Check 5: unknown field/state does not become normal success."""
    result = normalize_records(input_fixture["test_cases"]["invalid_unknown_field"])
    assert len(result["normalized"]) == 0, \
        "Record with unknown field should not be normalized (fail-closed)"
    assert len(result["rejected"]) == 1, "Record with unknown field should be rejected"
    
    rejected = result["rejected"][0]
    assert "record" in rejected, "Rejected item must have 'record' field"
    assert "reason" in rejected, "Rejected item must have 'reason' field"
    assert "unknown" in rejected["reason"].lower() or "unexpected" in rejected["reason"].lower() or \
           "field" in rejected["reason"].lower(), \
        "Rejection reason should mention unknown/unexpected field"


def test_oracle_check_6_deterministic_repeated_run(normalize_records, input_fixture):
    """Oracle Check 6: deterministic repeated run."""
    test_input = input_fixture["test_cases"]["valid_mixed"]
    
    # Run twice
    result1 = normalize_records(test_input)
    result2 = normalize_records(test_input)
    
    # Results should be identical
    assert result1 == result2, \
        "Deterministic invariant violated: same input must produce identical output"
    
    # Check ordering is preserved
    assert len(result1["normalized"]) == len(test_input), \
        "All valid_mixed records should be normalized"
    
    # Verify order matches input order
    for i, rec in enumerate(result1["normalized"]):
        expected_id = test_input[i]["id"]
        assert rec["id"] == expected_id, \
            f"Record ordering not preserved: expected id {expected_id} at position {i}, got {rec['id']}"


def test_oracle_check_7_only_solution_path_modified():
    """Oracle Check 7: only allowed solver path changed.
    
    This is a meta-check that would be performed by the harness infrastructure.
    In a real benchmark run, the harness would verify git diff shows only
    experiments/cross_agent_loop/task_v0/solution.py was modified.
    
    For this self-test, we verify the solution module exists at expected path.
    """
    solution_path = Path(__file__).parent / "solution.py"
    assert solution_path.exists(), f"Solution file must exist at {solution_path}"
    
    # Verify no forbidden paths exist in solution
    forbidden_imports = [
        "00_Framework",
        "01_Portfolio", 
        "data/portfolio",
        "data/market",
        "TEAM_RULES",
        "TEAM_STATE"
    ]
    
    with open(solution_path) as f:
        content = f.read()
        for forbidden in forbidden_imports:
            assert forbidden not in content, \
                f"SCOPE_FAIL: Solution must not reference forbidden path '{forbidden}'"


def test_integration_mixed_valid_invalid(normalize_records, input_fixture):
    """Integration test: mixed valid and invalid records."""
    result = normalize_records(input_fixture["test_cases"]["mixed_valid_invalid"])
    
    # Should have 2 valid, 2 invalid
    assert len(result["normalized"]) == 2, "Should normalize exactly 2 valid records"
    assert len(result["rejected"]) == 2, "Should reject exactly 2 invalid records"
    
    # Verify valid records maintain order
    assert result["normalized"][0]["id"] == "rec007"
    assert result["normalized"][1]["id"] == "rec008"

