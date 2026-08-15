from scripts.work_contract_validator import validate_issue_body


def body(**overrides):
    values = {
        "version": "1",
        "goal": '"deterministic work"',
        "status": "READY_FOR_IMPLEMENTATION",
        "owner_slice": '"contract-v1"',
        "risk": "GREEN",
        "authority": "STANDARD",
        "dependencies": '["#479"]',
        "allowed_paths": '["scripts/**", "tests/**"]',
        "forbidden_paths": '["TEAM_RULES.md", "TEAM_STATE.md", ".github/**"]',
        "acceptance_tests": '["pytest tests/test_work_contract_validator.py"]',
        "expected_outputs": '["PR"]',
        "human_gate": '["merge"]',
        "non_goals": '["automatic dispatch"]',
    }
    values.update(overrides)
    lines = ["```yaml", "work_contract:"]
    lines.extend(f"  {key}: {value}" for key, value in values.items())
    lines.append("```")
    return "\n".join(lines)


def test_valid_green_contract_is_executable():
    result = validate_issue_body(body())
    assert result.valid is True
    assert result.executable is True
    assert result.errors == ()


def test_missing_required_field_fails_closed():
    text = body().replace('  goal: "deterministic work"\n', "")
    result = validate_issue_body(text)
    assert "MISSING_FIELD:goal" in result.errors
    assert result.executable is False


def test_invalid_enum_and_non_ready_fail_closed():
    result = validate_issue_body(body(risk="BLUE", status="DESIGNING"))
    assert "INVALID_RISK" in result.errors
    assert "NOT_READY" in result.errors


def test_allowed_forbidden_overlap_is_invalid():
    result = validate_issue_body(body(forbidden_paths='["scripts/private/**"]'))
    assert "ALLOWED_FORBIDDEN_OVERLAP" in result.errors


def test_mid_pattern_wildcard_overlap_is_detected_not_silently_passed():
    result = validate_issue_body(
        body(
            allowed_paths='["scripts/*.py", "tests/*.py"]',
            forbidden_paths='["scripts/operational_state_guard.py", "tests/test_operational_state_guard.py"]',
        )
    )
    assert "ALLOWED_FORBIDDEN_OVERLAP" in result.errors
    assert result.valid is False


def test_mid_pattern_wildcard_without_real_overlap_stays_valid():
    result = validate_issue_body(
        body(
            allowed_paths='["scripts/*.py"]',
            forbidden_paths='["docs/private_notes.py"]',
        )
    )
    assert "ALLOWED_FORBIDDEN_OVERLAP" not in result.errors
    assert result.valid is True


def test_green_contract_cannot_allow_protected_path():
    result = validate_issue_body(body(allowed_paths='[".github/workflows/**"]'))
    assert any(error.startswith("GREEN_PROTECTED_PATH") for error in result.errors)


def test_empty_acceptance_tests_is_invalid():
    result = validate_issue_body(body(acceptance_tests="[]"))
    assert "EMPTY_ACCEPTANCE_TESTS" in result.errors


def test_malformed_or_missing_contract_does_not_silently_execute():
    result = validate_issue_body("ordinary issue body without contract")
    assert result.valid is False
    assert result.executable is False
    assert result.errors[0].startswith("PARSE_ERROR:")


def test_green_issue_79_path_is_blocked():
    result = validate_issue_body(body(allowed_paths='["issues/79/**"]'))
    assert any(error.startswith("GREEN_ISSUE_79_PATH") for error in result.errors)
