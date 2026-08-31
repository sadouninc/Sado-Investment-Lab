"""Seven-check oracle for task v0 record normalization."""
import json
from pathlib import Path


class OracleValidator:
    """Validates solver implementations against 7 minimum requirements."""
    
    def __init__(self, solution_file, fixture_file):
        self.solution_file = Path(solution_file)
        self.fixture_file = Path(fixture_file)
        self.results = {}
        self.messages = []
    
    def validate(self):
        """Run all validation steps."""
        if not self._validate_import():
            return "SYNTAX_FAIL"
        if not self._validate_signature():
            return "SEMANTIC_FAIL"
        if not self._load_fixture():
            return "HARNESS_ERROR"
        if not self._validate_normalization():
            return "SEMANTIC_FAIL"
        if not self._validate_rejection():
            return "SEMANTIC_FAIL"
        if not self._validate_unknown_handling():
            return "SEMANTIC_FAIL"
        if not self._validate_determinism():
            return "SEMANTIC_FAIL"
        if not self._validate_scope():
            return "SCOPE_FAIL"
        return "PASS"
    
    def _validate_import(self):
        """Validation step 1: import and syntax."""
        try:
            import importlib.util
            loader = importlib.util.spec_from_file_location("candidate", self.solution_file)
            if not loader or not loader.loader:
                self.messages.append("Cannot create module loader")
                return False
            self.module = importlib.util.module_from_spec(loader)
            loader.loader.exec_module(self.module)
            self.results["import"] = True
            return True
        except SyntaxError as err:
            self.messages.append(f"Syntax issue: {err}")
            return False
        except ImportError as err:
            self.messages.append(f"Import issue: {err}")
            return False
    
    def _validate_signature(self):
        """Validation step 2: function signature."""
        if not hasattr(self.module, "normalize_records"):
            self.messages.append("Missing normalize_records function")
            return False
        self.func = getattr(self.module, "normalize_records")
        if not callable(self.func):
            self.messages.append("normalize_records is not callable")
            return False
        self.results["signature"] = True
        return True
    
    def _load_fixture(self):
        """Load test fixture data from file."""
        try:
            with open(self.fixture_file) as fh:
                self.fixture = json.load(fh)
            return True
        except Exception as err:
            self.messages.append(f"Fixture error: {err}")
            return False
    
    def _validate_normalization(self):
        """Validation step 3: correct normalization."""
        sample = [{"id": "  test  ", "value": 5.555, "category": "BETA"}]
        try:
            output = self.func(sample)
        except Exception as err:
            self.messages.append(f"Execution error: {err}")
            return False
        
        if not isinstance(output, dict):
            self.messages.append("Output must be dict")
            return False
        if "accepted" not in output or "rejected" not in output:
            self.messages.append("Output must have accepted and rejected")
            return False
        if len(output["accepted"]) != 1:
            self.messages.append("Should accept valid record")
            return False
        
        actual = output["accepted"][0]
        expected = {"id": "TEST", "value": 5.56, "category": "beta"}
        if actual != expected:
            self.messages.append(f"Normalization mismatch: {actual} vs {expected}")
            return False
        
        self.results["normalization"] = True
        return True
    
    def _validate_rejection(self):
        """Validation step 4: reject malformed input."""
        bad_sample = [{"id": "test", "category": "alpha"}]  # no value
        try:
            output = self.func(bad_sample)
        except Exception as err:
            self.messages.append(f"Rejection test error: {err}")
            return False
        
        if len(output["rejected"]) != 1:
            self.messages.append("Should reject incomplete record")
            return False
        if output["rejected"][0]["reason"] != "missing_required_field":
            self.messages.append("Wrong rejection reason")
            return False
        
        self.results["rejection"] = True
        return True
    
    def _validate_unknown_handling(self):
        """Validation step 5: reject unknown categories."""
        unknown_sample = [{"id": "test", "value": 1.0, "category": "unknown"}]
        try:
            output = self.func(unknown_sample)
        except Exception as err:
            self.messages.append(f"Unknown category test error: {err}")
            return False
        
        if len(output["rejected"]) != 1:
            self.messages.append("Should reject unknown category")
            return False
        if output["rejected"][0]["reason"] != "unknown_category":
            self.messages.append("Wrong unknown category reason")
            return False
        
        self.results["unknown_handling"] = True
        return True
    
    def _validate_determinism(self):
        """Validation step 6: deterministic execution."""
        try:
            first = self.func(self.fixture)
            second = self.func(self.fixture)
            if first != second:
                self.messages.append("Non-deterministic behavior")
                return False
            self.results["determinism"] = True
            return True
        except Exception as err:
            self.messages.append(f"Determinism test error: {err}")
            return False
    
    def _validate_scope(self):
        """Validation step 7: no forbidden imports."""
        content = self.solution_file.read_text()
        forbidden_libs = ["requests", "urllib", "boto3", "socket"]
        for lib in forbidden_libs:
            if f"import {lib}" in content or f"from {lib}" in content:
                self.messages.append(f"Forbidden library: {lib}")
                return False
        self.results["scope"] = True
        return True


def test_oracle_passes_on_reference_solution():
    """Test case for pytest."""
    base = Path(__file__).parent
    validator = OracleValidator(base / "solution.py", base / "input_fixture.json")
    result = validator.validate()
    assert result == "PASS", f"Failed: {validator.messages}"


if __name__ == "__main__":
    base = Path(__file__).parent
    validator = OracleValidator(base / "solution.py", base / "input_fixture.json")
    result = validator.validate()
    print(f"Oracle: {result}")
    for msg in validator.messages:
        print(f"  {msg}")
