from scripts.pr_rescue_diagnostics import authorize_mutation, diagnose


def snapshot(**overrides):
    value = {
        "repository": "sadouninc/Sado-Investment-Lab",
        "pr_number": 472,
        "state": "OPEN",
        "head_sha": "head-472",
        "base_sha_at_scan": "base-before-471",
        "checks": [{"name": "PR Preflight", "conclusion": "SUCCESS"}],
        "base_advanced": True,
        "changed_paths": ["TEAM_STATE.md"],
        "overlapping_paths": ["TEAM_STATE.md"],
        "owner_scope_conflict": True,
        "unresolved_review_threads": 1,
    }
    value.update(overrides)
    return value


def test_pr_472_historical_replay_is_deterministic_and_read_only():
    first = diagnose(snapshot(), trigger="STALE_BASE")
    second = diagnose(snapshot(), trigger="STALE_BASE")

    assert first == second
    assert first.status == "OWNER_LEASE_REQUIRED"
    assert {"STALE_BASE", "PATH_OVERLAP", "OWNER_SCOPE_CONFLICT"} <= set(first.classes)
    assert first.mutation_performed is False
    assert first.diagnosis_key == second.diagnosis_key


def test_current_closed_pr_is_not_applicable():
    result = diagnose(snapshot(state="CLOSED", superseded=True))
    assert result.status == "NOT_APPLICABLE"
    assert result.classes == ("SUPERSEDED",)
    assert result.mutation_performed is False


def test_missing_check_status_and_freshness_are_unknown_not_pass():
    result = diagnose(
        snapshot(
            checks=None,
            base_advanced=None,
            overlapping_paths=[],
            owner_scope_conflict=False,
            unresolved_review_threads=None,
        )
    )
    assert result.status == "UNKNOWN"
    assert "CHECK_STATUS_UNAVAILABLE" in result.unknowns
    assert "BASE_FRESHNESS_UNKNOWN" in result.unknowns
    assert "CI_FAILURE" not in result.classes


def test_failed_check_is_classified_without_attempting_fix():
    result = diagnose(
        snapshot(
            checks=[{"name": "unit tests", "conclusion": "FAILURE"}],
            base_advanced=False,
            overlapping_paths=[],
            owner_scope_conflict=False,
            unresolved_review_threads=0,
        ),
        trigger="CI_FAILURE",
    )
    assert result.classes == ("CI_FAILURE",)
    assert result.status == "OWNER_LEASE_REQUIRED"
    assert result.mutation_performed is False


def lease(**overrides):
    value = {
        "expected_head_sha": "head-1",
        "allowed_actions": ["FIX", "TEST", "REBASE"],
        "allowed_paths": ["scripts/", "tests/"],
    }
    value.update(overrides)
    return value


def request(**overrides):
    value = {
        "action": "FIX",
        "current_head_sha": "head-1",
        "paths": ["scripts/example.py", "tests/test_example.py"],
    }
    value.update(overrides)
    return value


def test_mutation_requires_lease_and_exact_head():
    assert authorize_mutation(None, request()) == "LEASE_MISSING"
    assert authorize_mutation(lease(), request(current_head_sha="head-2")) == "LEASE_STALE"


def test_allowed_paths_and_actions_fail_closed():
    assert authorize_mutation(lease(), request(paths=["TEAM_STATE.md"])) == "SCOPE_DENIED"
    assert authorize_mutation(lease(), request(action="COMMENT")) == "SCOPE_DENIED"
    assert authorize_mutation(lease(), request()) == "AUTHORIZED"


def test_red_actions_and_issue_79_are_always_blocked():
    for action in ("MERGE", "MAIN_PUSH", "FORCE_PUSH", "SCOPE_CHANGE"):
        assert authorize_mutation(lease(), request(action=action)) == "RED_BLOCKED"
    assert authorize_mutation(lease(), request(issue_number=79)) == "RED_BLOCKED"

