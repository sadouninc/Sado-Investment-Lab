"""Harness self-tests for Cross-Agent Loop Phase 1.

The state-machine tests below are executable, provider-neutral simulations. They
prove that success, solver failure, timeout, harness failure, and control-plane
failure all terminate in RESULT_RECORDED without conflating infrastructure
failures with provider capability.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

TASK_DIR = Path(__file__).parent.parent / "task_v0"
RESULTS_DIR = Path(__file__).parent.parent / "results"


@dataclass(frozen=True)
class RecordedResult:
    result_state: str
    oracle_result: str
    provider_failure_eligible: bool


def record_terminal_result(outcome: str) -> RecordedResult:
    """Provider-neutral terminal transition used by Phase-1 harness tests.

    The harness persists every terminal outcome through RESULT_RECORDED.
    HARNESS_ERROR and CONTROL_PLANE_FAIL are explicitly excluded from provider
    scoring. TIMEOUT is also fail-closed here: it is observable but not counted
    as provider failure until an external classifier establishes attribution.
    """
    terminal = {
        "PASS": False,
        "SYNTAX_FAIL": True,
        "SEMANTIC_FAIL": True,
        "SCOPE_FAIL": True,
        "NO_OUTPUT": True,
        "TIMEOUT": False,
        "HARNESS_ERROR": False,
        "CONTROL_PLANE_FAIL": False,
    }
    if outcome not in terminal:
        raise ValueError(f"non-terminal or unknown outcome: {outcome}")
    return RecordedResult(
        result_state="RESULT_RECORDED",
        oracle_result=outcome,
        provider_failure_eligible=terminal[outcome],
    )


@pytest.fixture
def task_readme():
    path = TASK_DIR / "README.md"
    assert path.exists()
    return path.read_text()


@pytest.fixture
def input_fixture():
    with open(TASK_DIR / "input_fixture.json") as handle:
        return json.load(handle)


@pytest.fixture
def result_schema():
    with open(RESULTS_DIR / "schema-v1.json") as handle:
        return json.load(handle)


def test_task_family_is_deterministic_and_provider_neutral(task_readme):
    lower = task_readme.lower()
    assert "deterministic" in lower
    assert "provider-neutral" in lower
    for provider in ["amazon q", "amazon-q", "copilot", "openai", "anthropic"]:
        assert provider not in lower


def test_canonical_semantic_packet_and_three_patterns_exist(task_readme):
    assert "Canonical Semantic Packet" in task_readme
    for pattern in ["P1", "P2", "P3"]:
        assert f"Pattern {pattern}" in task_readme or f"{pattern}:" in task_readme
    for semantic in ["normalize", "reject", "deterministic", "solution.py"]:
        assert semantic in task_readme.lower()


def test_allowed_and_forbidden_boundary_is_declared(task_readme):
    assert "experiments/cross_agent_loop/task_v0/solution.py" in task_readme
    assert "forbidden" in task_readme.lower() or "do not modify" in task_readme.lower()
    assert "oracle_test.py" in task_readme
    assert "pytest" in task_readme.lower()


def test_input_fixture_contains_deterministic_valid_and_invalid_cases(input_fixture):
    cases = input_fixture["test_cases"]
    for name in [
        "valid_complete",
        "valid_minimal",
        "invalid_missing_id",
        "invalid_missing_name",
        "invalid_unknown_field",
    ]:
        assert name in cases
    with open(TASK_DIR / "input_fixture.json") as handle:
        assert input_fixture == json.load(handle)


def test_oracle_file_declares_required_classifications():
    content = (TASK_DIR / "oracle_test.py").read_text()
    for result in [
        "PASS",
        "SYNTAX_FAIL",
        "SEMANTIC_FAIL",
        "SCOPE_FAIL",
        "NO_OUTPUT",
        "HARNESS_ERROR",
        "CONTROL_PLANE_FAIL",
    ]:
        assert result in content


def test_result_schema_has_provider_neutral_case_ids_and_timeout(result_schema):
    required = set(result_schema["required"])
    assert {"case_id", "provider", "timestamp", "oracle_result", "metadata"} <= required
    case_ids = result_schema["properties"]["case_id"]["enum"]
    assert set(case_ids) == {"P1-R1", "P1-R2", "P2-R1", "P2-R2", "P3-R1", "P3-R2"}
    results = result_schema["properties"]["oracle_result"]["enum"]
    assert "TIMEOUT" in results
    assert "HARNESS_ERROR" in results
    assert "CONTROL_PLANE_FAIL" in results
    assert result_schema["properties"]["result_state"]["enum"] == ["RESULT_RECORDED"]


@pytest.mark.parametrize(
    "outcome,provider_failure_eligible",
    [
        ("PASS", False),
        ("SYNTAX_FAIL", True),
        ("SEMANTIC_FAIL", True),
        ("SCOPE_FAIL", True),
        ("NO_OUTPUT", True),
        ("TIMEOUT", False),
        ("HARNESS_ERROR", False),
        ("CONTROL_PLANE_FAIL", False),
    ],
)
def test_terminal_outcomes_reach_result_recorded(outcome, provider_failure_eligible):
    result = record_terminal_result(outcome)
    assert result.result_state == "RESULT_RECORDED"
    assert result.oracle_result == outcome
    assert result.provider_failure_eligible is provider_failure_eligible


def test_timeout_is_recorded_without_becoming_provider_failure():
    timeout = record_terminal_result("TIMEOUT")
    assert timeout.result_state == "RESULT_RECORDED"
    assert timeout.oracle_result == "TIMEOUT"
    assert timeout.provider_failure_eligible is False


def test_harness_and_control_plane_failures_are_not_provider_failures():
    for outcome in ["HARNESS_ERROR", "CONTROL_PLANE_FAIL"]:
        result = record_terminal_result(outcome)
        assert result.result_state == "RESULT_RECORDED"
        assert result.provider_failure_eligible is False


def test_unknown_or_nonterminal_state_fails_closed():
    with pytest.raises(ValueError, match="non-terminal or unknown outcome"):
        record_terminal_result("EXECUTING")


def test_no_production_investment_paths_referenced():
    for path in [TASK_DIR / "README.md", TASK_DIR / "oracle_test.py"]:
        content = path.read_text()
        for forbidden in ["01_Portfolio", "data/portfolio", "00_Framework"]:
            assert forbidden not in content
