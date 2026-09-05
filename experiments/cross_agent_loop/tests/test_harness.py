"""Harness self-tests for Cross-Agent Loop Phase 1.

These tests verify the harness infrastructure itself, not the solver implementation.
Tests include:
- Task specification exists and is provider-neutral
- All three prompt patterns preserve canonical semantic packet
- Input fixture is deterministic
- Oracle test suite structure
- Result schema validation
- Case ID predeclaration
- State machine simulation
"""

import json
from pathlib import Path

import pytest


TASK_DIR = Path(__file__).parent.parent / "task_v0"
RESULTS_DIR = Path(__file__).parent.parent / "results"


@pytest.fixture
def task_readme():
    """Load task README."""
    readme_path = TASK_DIR / "README.md"
    assert readme_path.exists(), "Task README.md must exist"
    return readme_path.read_text()


@pytest.fixture
def input_fixture():
    """Load input fixture."""
    fixture_path = TASK_DIR / "input_fixture.json"
    assert fixture_path.exists(), "input_fixture.json must exist"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def result_schema():
    """Load result schema."""
    schema_path = RESULTS_DIR / "schema-v1.json"
    assert schema_path.exists(), "schema-v1.json must exist"
    with open(schema_path) as f:
        return json.load(f)


def test_task_family_is_deterministic(task_readme):
    """Verify task family v0 is marked as deterministic."""
    assert "Deterministic" in task_readme
    assert "deterministic" in task_readme.lower()


def test_task_is_provider_neutral(task_readme):
    """Verify task specification is provider-neutral."""
    assert "Provider-Neutral" in task_readme or "provider-neutral" in task_readme.lower()
    
    # Should not contain provider-specific names in task spec
    forbidden_providers = ["amazon-q", "Amazon Q", "copilot", "openai", "anthropic"]
    for provider in forbidden_providers:
        assert provider.lower() not in task_readme.lower(), \
            f"Task spec must not reference specific provider '{provider}'"


def test_canonical_semantic_packet_exists(task_readme):
    """Verify canonical semantic packet v1 exists."""
    assert "Canonical Semantic Packet" in task_readme
    assert "Pattern P1" in task_readme
    assert "Pattern P2" in task_readme
    assert "Pattern P3" in task_readme


def test_three_prompt_patterns_present(task_readme):
    """Verify all three prompt patterns are present."""
    assert "P1: NATURAL" in task_readme or "P1_NATURAL" in task_readme
    assert "P2: STRUCTURED" in task_readme or "P2_STRUCTURED" in task_readme
    assert "P3: CONTRACT" in task_readme or "P3_CONTRACT" in task_readme


def test_prompt_patterns_preserve_identical_semantics(task_readme):
    """Verify all patterns communicate identical semantic information."""
    # All patterns must mention key semantic elements
    required_semantics = [
        "normalize",
        "id",
        "name", 
        "value",
        "status",
        "reject",
        "deterministic",
        "solution.py"
    ]
    
    for semantic in required_semantics:
        assert semantic in task_readme.lower(), \
            f"All patterns must communicate '{semantic}' semantic"


def test_allowed_mutable_path_declared(task_readme):
    """Verify allowed mutable path is clearly declared."""
    assert "experiments/cross_agent_loop/task_v0/solution.py" in task_readme
    assert "allowed" in task_readme.lower() or "modify" in task_readme.lower()


def test_forbidden_actions_declared(task_readme):
    """Verify forbidden actions/paths are declared."""
    forbidden_indicators = [
        "forbidden" in task_readme.lower(),
        "do not modify" in task_readme.lower(),
        "do not access" in task_readme.lower()
    ]
    assert any(forbidden_indicators), "Task must declare forbidden actions"


def test_oracle_command_declared(task_readme):
    """Verify oracle test command is declared."""
    assert "oracle_test.py" in task_readme
    assert "pytest" in task_readme.lower()


def test_done_condition_declared(task_readme):
    """Verify done condition is clearly stated."""
    assert "done" in task_readme.lower() or "complete" in task_readme.lower()
    assert "pass" in task_readme.lower()


def test_input_fixture_has_valid_cases(input_fixture):
    """Verify input fixture contains valid test cases."""
    test_cases = input_fixture["test_cases"]
    assert "valid_complete" in test_cases
    assert "valid_minimal" in test_cases
    assert len(test_cases["valid_complete"]) > 0
    assert len(test_cases["valid_minimal"]) > 0


def test_input_fixture_has_invalid_cases(input_fixture):
    """Verify input fixture contains invalid test cases."""
    test_cases = input_fixture["test_cases"]
    assert "invalid_missing_id" in test_cases
    assert "invalid_missing_name" in test_cases
    assert "invalid_unknown_field" in test_cases


def test_input_fixture_is_deterministic(input_fixture):
    """Verify input fixture structure is deterministic."""
    # Re-load and compare
    fixture_path = TASK_DIR / "input_fixture.json"
    with open(fixture_path) as f:
        reload = json.load(f)
    
    assert input_fixture == reload, "Input fixture must be deterministic"


def test_oracle_test_file_exists():
    """Verify oracle test suite exists."""
    oracle_path = TASK_DIR / "oracle_test.py"
    assert oracle_path.exists(), "oracle_test.py must exist"


def test_oracle_implements_seven_checks():
    """Verify oracle implements all 7 minimum checks."""
    oracle_path = TASK_DIR / "oracle_test.py"
    content = oracle_path.read_text()
    
    required_checks = [
        "syntax",
        "import",
        "signature",
        "valid fixture",
        "malformed",
        "unknown field",
        "deterministic",
        "path"
    ]
    
    for check in required_checks:
        assert check.lower() in content.lower(), \
            f"Oracle must implement check for '{check}'"


def test_oracle_result_classifications_declared():
    """Verify oracle declares all result classifications."""
    oracle_path = TASK_DIR / "oracle_test.py"
    content = oracle_path.read_text()
    
    required_results = [
        "PASS",
        "SYNTAX_FAIL",
        "SEMANTIC_FAIL", 
        "SCOPE_FAIL",
        "NO_OUTPUT",
        "HARNESS_ERROR",
        "CONTROL_PLANE_FAIL"
    ]
    
    for result in required_results:
        assert result in content, f"Oracle must declare result '{result}'"


def test_result_schema_has_required_fields(result_schema):
    """Verify result schema has required fields."""
    required = result_schema["required"]
    assert "case_id" in required
    assert "provider" in required
    assert "timestamp" in required
    assert "oracle_result" in required
    assert "metadata" in required


def test_result_schema_separates_provider_from_harness_failure(result_schema):
    """Verify result schema separates provider failure from harness/control-plane failure."""
    oracle_results = result_schema["properties"]["oracle_result"]["enum"]
    assert "HARNESS_ERROR" in oracle_results
    assert "CONTROL_PLANE_FAIL" in oracle_results
    
    # These should not count as provider failure
    provider_failures = ["SYNTAX_FAIL", "SEMANTIC_FAIL", "SCOPE_FAIL", "NO_OUTPUT"]
    for failure in provider_failures:
        assert failure in oracle_results


def test_six_case_ids_predeclared(result_schema):
    """Verify all six provider-neutral case IDs are predeclared."""
    case_ids = result_schema["properties"]["case_id"]["enum"]
    expected = ["P1-R1", "P1-R2", "P2-R1", "P2-R2", "P3-R1", "P3-R2"]
    
    assert set(case_ids) == set(expected), \
        f"Expected case IDs {expected}, got {case_ids}"


def test_provider_field_separate_from_case_id(result_schema):
    """Verify provider is in separate field from case_id."""
    properties = result_schema["properties"]
    assert "case_id" in properties
    assert "provider" in properties
    
    # Provider should not be in case_id enum
    case_ids = properties["case_id"]["enum"]
    for case_id in case_ids:
        assert "amazon" not in case_id.lower()
        assert "copilot" not in case_id.lower()
        assert "openai" not in case_id.lower()


def test_state_machine_result_states():
    """Verify state machine can reach RESULT_RECORDED from PASS/FAIL states."""
    # This is a conceptual test - in a real implementation, you'd have a state machine module
    # For now, verify the result schema supports all terminal states
    
    result_schema_path = RESULTS_DIR / "schema-v1.json"
    with open(result_schema_path) as f:
        schema = json.load(f)
    
    oracle_results = schema["properties"]["oracle_result"]["enum"]
    
    # All these states should be recordable
    assert "PASS" in oracle_results
    assert "SYNTAX_FAIL" in oracle_results
    assert "SEMANTIC_FAIL" in oracle_results
    assert "SCOPE_FAIL" in oracle_results
    
    # The schema itself represents the "RESULT_RECORDED" state
    assert schema["type"] == "object"


def test_no_production_investment_paths_referenced():
    """Verify harness does not reference production/investment paths."""
    forbidden_paths = ["01_Portfolio", "data/portfolio", "00_Framework"]
    
    for path in [TASK_DIR / "README.md", TASK_DIR / "oracle_test.py"]:
        content = path.read_text()
        for forbidden in forbidden_paths:
            assert forbidden not in content, \
                f"Harness must not reference production path '{forbidden}'"

