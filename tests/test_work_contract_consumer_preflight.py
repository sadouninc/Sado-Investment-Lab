import tempfile
from pathlib import Path

from scripts.work_contract_consumer_preflight import evaluate_issue, write_outputs


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "copilot-poc1.yml"


def body(**overrides):
    values = {
        "version": "1",
        "goal": '"deterministic work"',
        "status": "READY_FOR_IMPLEMENTATION",
        "owner_slice": '"consumer-preflight"',
        "risk": "GREEN",
        "authority": "STANDARD",
        "dependencies": '["#479"]',
        "allowed_paths": '["scripts/**", "tests/**"]',
        "forbidden_paths": '["TEAM_RULES.md", "TEAM_STATE.md", ".github/**"]',
        "acceptance_tests": '["pytest tests/test_work_contract_consumer_preflight.py"]',
        "expected_outputs": '["PR"]',
        "human_gate": '["merge"]',
        "non_goals": '["automatic dispatch"]',
    }
    values.update(overrides)
    lines = ["```yaml", "work_contract:"]
    lines.extend(f"  {key}: {value}" for key, value in values.items())
    lines.append("```")
    return "\n".join(lines)


def issue(text=None, **overrides):
    value = {"number": 490, "title": "pilot", "state": "open", "body": text or body()}
    value.update(overrides)
    return value


def test_valid_contract_is_execution_eligible():
    result = evaluate_issue(issue())
    assert result["status"] == "ELIGIBLE"
    assert result["executable"] is True
    assert result["reason_codes"] == []


def test_validator_reason_codes_pass_through_unchanged_and_deterministically():
    invalid = issue(body(status="DESIGNING", risk="BLUE"))
    first = evaluate_issue(invalid)
    second = evaluate_issue(invalid)
    assert first == second
    assert first["reason_codes"] == ["INVALID_RISK", "NOT_READY"]
    assert first["executable"] is False


def test_missing_and_malformed_contracts_fail_closed():
    missing = evaluate_issue(issue("ordinary issue body"))
    malformed = evaluate_issue(issue("```yaml\nwork_contract:\n invalid\n```"))
    assert missing["status"] == "BLOCKED"
    assert missing["reason_codes"][0].startswith("PARSE_ERROR:")
    assert malformed["status"] == "BLOCKED"
    assert malformed["reason_codes"][0].startswith("PARSE_ERROR:")


def test_non_ready_protected_path_invalid_enum_and_empty_tests_are_blocked():
    cases = (
        (body(status="DESIGNING"), "NOT_READY"),
        (body(allowed_paths='[".github/workflows/**"]'), "GREEN_PROTECTED_PATH"),
        (body(authority="UNKNOWN"), "INVALID_AUTHORITY"),
        (body(acceptance_tests="[]"), "EMPTY_ACCEPTANCE_TESTS"),
    )
    for text, expected in cases:
        reasons = evaluate_issue(issue(text))["reason_codes"]
        assert any(code.startswith(expected) for code in reasons)


def test_closed_issue_and_pull_request_fail_before_execution():
    assert evaluate_issue(issue(state="closed"))["reason_codes"] == ["ISSUE_NOT_OPEN"]
    assert evaluate_issue(issue(pull_request={"url": "unused"}))["reason_codes"] == [
        "INPUT_IS_PULL_REQUEST"
    ]


def test_blocked_preflight_writes_diagnostic_but_no_worker_inputs():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        outputs = {
            "diagnostic_output": root / "diagnostic.json",
            "contract_output": root / "contract.md",
            "allowed_paths_output": root / "allowed.txt",
            "forbidden_paths_output": root / "forbidden.txt",
        }
        value = issue("ordinary issue body")
        write_outputs(value, evaluate_issue(value), **outputs)

        assert outputs["diagnostic_output"].exists()
        assert not outputs["contract_output"].exists()
        assert not outputs["allowed_paths_output"].exists()
        assert not outputs["forbidden_paths_output"].exists()


def test_blocked_preflight_removes_stale_worker_input_outputs():
    """Regression test: blocked run removes pre-existing worker input files."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        outputs = {
            "diagnostic_output": root / "diagnostic.json",
            "contract_output": root / "contract.md",
            "allowed_paths_output": root / "allowed.txt",
            "forbidden_paths_output": root / "forbidden.txt",
        }
        # Simulate pre-existing worker input files from previous ELIGIBLE run
        outputs["contract_output"].write_text("stale contract", encoding="utf-8")
        outputs["allowed_paths_output"].write_text("stale/paths", encoding="utf-8")
        outputs["forbidden_paths_output"].write_text("stale/forbidden", encoding="utf-8")

        # Run BLOCKED preflight
        value = issue("ordinary issue body")
        write_outputs(value, evaluate_issue(value), **outputs)

        assert outputs["diagnostic_output"].exists()
        assert not outputs["contract_output"].exists()
        assert not outputs["allowed_paths_output"].exists()
        assert not outputs["forbidden_paths_output"].exists()


def test_workflow_runs_preflight_before_install_and_worker():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    preflight = workflow.index("Validate Contract v1 before worker execution")
    install = workflow.index("Install Copilot CLI")
    worker = workflow.index("Run one non-interactive Copilot implementation pass")

    assert "python -m scripts.work_contract_consumer_preflight" in workflow
    assert preflight < install < worker
    assert "HARNESS_OUTCOME=BLOCKED_CONTRACT_PREFLIGHT" in workflow
    assert "if 'READY_FOR_IMPLEMENTATION' not in body" not in workflow
