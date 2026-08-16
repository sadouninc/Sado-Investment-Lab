from scripts.work_contract_validator import validate_contract, validate_issue_body


def valid_contract(**overrides):
    values = {
        "version": 1,
        "goal": "deterministic work",
        "status": "READY_FOR_IMPLEMENTATION",
        "owner_slice": "contract-v1",
        "risk": "GREEN",
        "authority": "STANDARD",
        "dependencies": ["#479"],
        "allowed_paths": ["scripts/**", "tests/**"],
        "forbidden_paths": ["TEAM_RULES.md", "TEAM_STATE.md", ".github/**"],
        "acceptance_tests": ["pytest tests/test_work_contract_validator.py"],
        "expected_outputs": ["PR"],
        "human_gate": ["merge"],
        "non_goals": ["automatic dispatch"],
    }
    values.update(overrides)
    return values


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


def test_blank_allowed_path_does_not_cause_false_overlap():
    """Blank or whitespace-only path patterns should not be treated as meaningful paths in overlap detection."""
    result = validate_issue_body(
        body(
            allowed_paths='["", "tests/**"]',
            forbidden_paths='["TEAM_RULES.md", "TEAM_STATE.md"]',
        )
    )
    assert "ALLOWED_FORBIDDEN_OVERLAP" not in result.errors


def test_whitespace_only_allowed_path_does_not_cause_false_overlap():
    """Whitespace-only patterns should be treated as non-meaningful after stripping."""
    result = validate_issue_body(
        body(
            allowed_paths='["   ", "tests/**"]',
            forbidden_paths='["TEAM_RULES.md", "TEAM_STATE.md"]',
        )
    )
    assert "ALLOWED_FORBIDDEN_OVERLAP" not in result.errors


def test_blank_forbidden_path_does_not_cause_false_overlap():
    """Blank path in forbidden list should not trigger overlap with allowed paths."""
    result = validate_issue_body(
        body(
            allowed_paths='["scripts/**", "tests/**"]',
            forbidden_paths='["", "data/**"]',
        )
    )
    assert "ALLOWED_FORBIDDEN_OVERLAP" not in result.errors


def test_real_overlap_still_detected_with_blank_paths_present():
    """Sanity check: actual overlaps should still be detected when blank paths are also present."""
    result = validate_issue_body(
        body(allowed_paths='["", "scripts/**"]', forbidden_paths='["   ", "scripts/private/**"]')
    )
    assert "ALLOWED_FORBIDDEN_OVERLAP" in result.errors


def test_null_allowed_path_fails_closed_not_silently():
    """A null entry in allowed_paths must be rejected explicitly, not stringified."""
    result = validate_contract(valid_contract(allowed_paths=["scripts/**", None]))
    assert result.valid is False
    assert result.executable is False
    assert "NON_STRING_PATH:allowed_paths[1]" in result.errors


def test_numeric_forbidden_path_fails_closed_not_silently():
    """A numeric entry in forbidden_paths must be rejected explicitly, not stringified."""
    result = validate_contract(valid_contract(forbidden_paths=["TEAM_RULES.md", 123]))
    assert result.valid is False
    assert "NON_STRING_PATH:forbidden_paths[1]" in result.errors


def test_boolean_allowed_path_fails_closed_not_silently():
    """A boolean entry in allowed_paths must be rejected explicitly, not stringified."""
    result = validate_contract(valid_contract(allowed_paths=[True, "tests/**"]))
    assert result.valid is False
    assert "NON_STRING_PATH:allowed_paths[0]" in result.errors


def test_object_and_array_forbidden_path_fails_closed_not_silently():
    """dict/list entries in forbidden_paths must be rejected explicitly, not stringified."""
    result = validate_contract(
        valid_contract(forbidden_paths=["TEAM_RULES.md", {"path": "x"}, ["nested"]])
    )
    assert result.valid is False
    assert "NON_STRING_PATH:forbidden_paths[1]" in result.errors
    assert "NON_STRING_PATH:forbidden_paths[2]" in result.errors


def test_non_string_path_does_not_trigger_spurious_overlap_or_crash():
    """Non-string entries must not raise and must not be silently compared via str()."""
    result = validate_contract(
        valid_contract(allowed_paths=["scripts/**", None], forbidden_paths=["TEAM_RULES.md", 123])
    )
    assert "ALLOWED_FORBIDDEN_OVERLAP" not in result.errors
    assert "NON_STRING_PATH:allowed_paths[1]" in result.errors
    assert "NON_STRING_PATH:forbidden_paths[1]" in result.errors


def test_valid_string_only_contract_unaffected_by_non_string_guard():
    """Baseline: an all-string contract remains valid and unchanged in behavior."""
    result = validate_contract(valid_contract())
    assert result.valid is True
    assert result.executable is True
    assert result.errors == ()
