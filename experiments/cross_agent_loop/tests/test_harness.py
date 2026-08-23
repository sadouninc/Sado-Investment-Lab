"""Harness self-tests for cross-agent loop Phase 1."""
import json
import tempfile
from pathlib import Path
from datetime import datetime


def test_task_specification_exists():
    """Task README exists and contains all required sections."""
    base = Path(__file__).parent.parent / "task_v0"
    readme = base / "README.md"
    
    assert readme.exists(), "Task README must exist"
    
    content = readme.read_text()
    
    # Check for canonical semantic packet
    assert "Canonical Semantic Packet" in content
    assert "Goal" in content
    assert "Input Behavior" in content
    assert "Output Behavior" in content
    assert "Normalization Rules" in content
    assert "Rejection Rules" in content
    assert "Invariants" in content
    assert "Allowed Mutable Path" in content
    assert "Forbidden Actions" in content
    
    # Check for all three pattern renderings
    assert "P1: NATURAL" in content
    assert "P2: STRUCTURED" in content
    assert "P3: CONTRACT" in content
    
    # Check for all six case IDs
    assert "P1-R1" in content
    assert "P1-R2" in content
    assert "P2-R1" in content
    assert "P2-R2" in content
    assert "P3-R1" in content
    assert "P3-R2" in content


def test_input_fixture_is_deterministic():
    """Input fixture is valid JSON with deterministic test cases."""
    base = Path(__file__).parent.parent / "task_v0"
    fixture = base / "input_fixture.json"
    
    assert fixture.exists(), "Input fixture must exist"
    
    with open(fixture) as f:
        data = json.load(f)
    
    assert isinstance(data, list), "Fixture must be a list"
    assert len(data) > 0, "Fixture must have test records"
    
    # Should have mix of valid and invalid records
    has_valid = False
    has_invalid = False
    
    for record in data:
        if isinstance(record, dict):
            if "id" in record and "value" in record and "category" in record:
                has_valid = True
            else:
                has_invalid = True
    
    assert has_valid, "Fixture should have valid records"
    assert has_invalid, "Fixture should have invalid records"


def test_reference_solution_exists():
    """Reference solution file exists and is importable."""
    base = Path(__file__).parent.parent / "task_v0"
    solution = base / "solution.py"
    
    assert solution.exists(), "Solution file must exist"
    
    # Check it's valid Python
    import importlib.util
    spec = importlib.util.spec_from_file_location("ref_solution", solution)
    assert spec is not None, "Solution must be valid Python module"
    
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    assert hasattr(module, "normalize_records"), "Must have normalize_records function"
    assert callable(module.normalize_records), "normalize_records must be callable"


def test_reference_solution_is_deterministic():
    """Reference solution produces consistent results."""
    base = Path(__file__).parent.parent / "task_v0"
    solution = base / "solution.py"
    fixture = base / "input_fixture.json"
    
    import importlib.util
    spec = importlib.util.spec_from_file_location("ref_solution", solution)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    with open(fixture) as f:
        data = json.load(f)
    
    result1 = module.normalize_records(data)
    result2 = module.normalize_records(data)
    
    assert result1 == result2, "Reference solution must be deterministic"


def test_reference_solution_preserves_order():
    """Reference solution preserves input order for accepted records."""
    base = Path(__file__).parent.parent / "task_v0"
    solution = base / "solution.py"
    
    import importlib.util
    spec = importlib.util.spec_from_file_location("ref_solution", solution)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # Three valid records in specific order
    test_data = [
        {"id": "first", "value": 1.0, "category": "alpha"},
        {"id": "second", "value": 2.0, "category": "beta"},
        {"id": "third", "value": 3.0, "category": "gamma"}
    ]
    
    result = module.normalize_records(test_data)
    
    assert len(result["accepted"]) == 3
    assert result["accepted"][0]["id"] == "FIRST"
    assert result["accepted"][1]["id"] == "SECOND"
    assert result["accepted"][2]["id"] == "THIRD"


def test_oracle_test_exists():
    """Oracle test file exists and is executable."""
    base = Path(__file__).parent.parent / "task_v0"
    oracle = base / "oracle_test.py"
    
    assert oracle.exists(), "Oracle test must exist"
    
    # Check it's valid Python
    import importlib.util
    spec = importlib.util.spec_from_file_location("oracle", oracle)
    assert spec is not None, "Oracle must be valid Python module"
    
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


def test_oracle_validates_reference_solution():
    """Oracle correctly validates the reference solution."""
    base = Path(__file__).parent.parent / "task_v0"
    oracle = base / "oracle_test.py"
    
    import importlib.util
    spec = importlib.util.spec_from_file_location("oracle", oracle)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # Run oracle validation
    validator = module.OracleValidator(
        base / "solution.py",
        base / "input_fixture.json"
    )
    result = validator.validate()
    
    assert result == "PASS", f"Oracle should pass reference solution: {validator.messages}"


def test_oracle_detects_syntax_error():
    """Oracle detects syntax errors in solution."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("def normalize_records(records):\n")
        f.write("    invalid syntax here\n")
        bad_solution = Path(f.name)
    
    try:
        base = Path(__file__).parent.parent / "task_v0"
        oracle = base / "oracle_test.py"
        
        import importlib.util
        spec = importlib.util.spec_from_file_location("oracle", oracle)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        validator = module.OracleValidator(bad_solution, base / "input_fixture.json")
        result = validator.validate()
        
        assert result == "SYNTAX_FAIL", "Oracle should detect syntax errors"
    finally:
        bad_solution.unlink()


def test_oracle_detects_missing_function():
    """Oracle detects missing normalize_records function."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("# Valid Python but no normalize_records function\n")
        f.write("def other_function():\n")
        f.write("    pass\n")
        bad_solution = Path(f.name)
    
    try:
        base = Path(__file__).parent.parent / "task_v0"
        oracle = base / "oracle_test.py"
        
        import importlib.util
        spec = importlib.util.spec_from_file_location("oracle", oracle)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        validator = module.OracleValidator(bad_solution, base / "input_fixture.json")
        result = validator.validate()
        
        assert result == "SEMANTIC_FAIL", "Oracle should detect missing function"
    finally:
        bad_solution.unlink()


def test_oracle_detects_wrong_normalization():
    """Oracle detects incorrect normalization logic."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("def normalize_records(records):\n")
        f.write("    # Wrong: doesn't normalize correctly\n")
        f.write("    return {'accepted': records, 'rejected': []}\n")
        bad_solution = Path(f.name)
    
    try:
        base = Path(__file__).parent.parent / "task_v0"
        oracle = base / "oracle_test.py"
        
        import importlib.util
        spec = importlib.util.spec_from_file_location("oracle", oracle)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        validator = module.OracleValidator(bad_solution, base / "input_fixture.json")
        result = validator.validate()
        
        assert result == "SEMANTIC_FAIL", "Oracle should detect wrong normalization"
    finally:
        bad_solution.unlink()


def test_result_schema_is_valid_json():
    """Result schema is valid JSON and well-formed."""
    base = Path(__file__).parent.parent / "results"
    schema_file = base / "schema-v1.json"
    
    assert schema_file.exists(), "Result schema must exist"
    
    with open(schema_file) as f:
        schema = json.load(f)
    
    assert "$schema" in schema or "type" in schema, "Must be valid JSON Schema"
    assert schema["type"] == "object", "Root must be object type"
    
    # Check required provider-neutral structure
    required = schema.get("required", [])
    assert "case_id" in required
    assert "provider" in required
    assert "oracle_result" in required
    
    # Check case_id enum has all 6 cases
    case_enum = schema["properties"]["case_id"]["enum"]
    assert len(case_enum) == 6
    assert "P1-R1" in case_enum
    assert "P1-R2" in case_enum
    assert "P2-R1" in case_enum
    assert "P2-R2" in case_enum
    assert "P3-R1" in case_enum
    assert "P3-R2" in case_enum
    
    # Check oracle_result enum has all classifications
    result_enum = schema["properties"]["oracle_result"]["enum"]
    assert "PASS" in result_enum
    assert "SYNTAX_FAIL" in result_enum
    assert "SEMANTIC_FAIL" in result_enum
    assert "SCOPE_FAIL" in result_enum
    assert "NO_OUTPUT" in result_enum
    assert "HARNESS_ERROR" in result_enum
    assert "CONTROL_PLANE_FAIL" in result_enum


def test_state_machine_simulation():
    """Simulate PASS/FAIL/TIMEOUT state machine reaching RESULT_RECORDED."""
    
    # State machine: READY → EXECUTING → (PASS|FAIL|TIMEOUT) → RESULT_RECORDED
    
    def simulate_execution(oracle_outcome):
        """Simulate one execution through state machine."""
        state = "READY"
        
        # Transition to executing
        state = "EXECUTING"
        assert state == "EXECUTING"
        
        # Transition based on oracle outcome
        if oracle_outcome in ["PASS", "SYNTAX_FAIL", "SEMANTIC_FAIL", "SCOPE_FAIL"]:
            state = oracle_outcome
        elif oracle_outcome == "TIMEOUT":
            state = "TIMEOUT"
        else:
            state = "HARNESS_ERROR"
        
        # All terminal states lead to RESULT_RECORDED
        state = "RESULT_RECORDED"
        assert state == "RESULT_RECORDED"
        
        return state
    
    # Test all oracle outcomes reach RESULT_RECORDED
    outcomes = ["PASS", "SYNTAX_FAIL", "SEMANTIC_FAIL", "SCOPE_FAIL", 
                "TIMEOUT", "HARNESS_ERROR"]
    
    for outcome in outcomes:
        final_state = simulate_execution(outcome)
        assert final_state == "RESULT_RECORDED", f"{outcome} should reach RESULT_RECORDED"


def test_provider_neutrality():
    """Verify harness is provider-neutral."""
    base = Path(__file__).parent.parent / "task_v0"
    readme = base / "README.md"
    
    content = readme.read_text()
    
    # Task spec should not mention specific providers
    provider_names = ["Amazon Q", "Copilot", "Cursor", "Claude"]
    for name in provider_names:
        assert name not in content, f"Task spec should not mention {name}"
    
    # Should explicitly state provider-neutral
    assert "provider-neutral" in content.lower() or "provider neutral" in content.lower()
