from scripts.queue_auto_promotion import select_next_work


def candidate(issue, *, worker="sora", priority=1, risk="GREEN", **overrides):
    value = {
        "issue_number": issue,
        "priority": priority,
        "risk": risk,
        "owner_slice": f"slice-{issue}",
        "allowed_paths": [f"scripts/{issue}.py"],
        "dependencies_satisfied": True,
        "preflight_valid": True,
        "preferred_worker": worker,
    }
    value.update(overrides)
    return value


def test_selects_one_safe_candidate_deterministically():
    items = [candidate(539, priority=2), candidate(444, priority=1)]
    first = select_next_work(items, worker_states={"sora": "available"})
    second = select_next_work(items, worker_states={"sora": "available"})
    assert first == second
    assert first["status"] == "SELECTED"
    assert first["selected"]["issue_number"] == 444


def test_quota_blocked_worker_is_not_selected():
    result = select_next_work(
        [candidate(539, worker="kai")],
        worker_states={"kai": "quota_blocked"},
    )
    assert result["status"] == "WORKER_BLOCKED"
    assert result["selected"] is None


def test_owner_and_path_conflicts_are_excluded_and_counted():
    result = select_next_work(
        [candidate(539, owner_slice="busy", allowed_paths=["scripts/shared.py"])],
        worker_states={"sora": "available"},
        active_owner_slices={"busy"},
        active_paths={"scripts/shared.py"},
    )
    assert result["status"] == "OWNER_CONFLICT"
    assert result["metrics"]["duplicate_start_prevented_count"] == 1


def test_dependency_and_invalid_preflight_fail_closed():
    dep = select_next_work(
        [candidate(539, dependencies_satisfied=False)],
        worker_states={"sora": "available"},
    )
    invalid = select_next_work(
        [candidate(539, preflight_valid=False)],
        worker_states={"sora": "available"},
    )
    assert dep["status"] == "DEPENDENCY_BLOCKED"
    assert invalid["status"] == "PREFLIGHT_INVALID"


def test_green_is_preferred_before_priority_and_copilot_metric_is_exposed():
    result = select_next_work(
        [
            candidate(444, worker="sora", priority=1, risk="AMBER"),
            candidate(539, worker="copilot", priority=9, risk="GREEN"),
        ],
        worker_states={"sora": "available", "copilot": "available"},
    )
    assert result["selected"]["issue_number"] == 539
    assert result["metrics"]["routed_to_copilot_count"] == 1


def test_no_candidates_returns_no_safe_candidate():
    result = select_next_work([], worker_states={"sora": "available"})
    assert result["status"] == "NO_SAFE_CANDIDATE"
    assert result["metrics"]["no_safe_candidate_count"] == 1


def test_glob_prefix_conflict_active_glob_vs_concrete_candidate():
    """Active path scripts/** should conflict with candidate path scripts/shared.py"""
    result = select_next_work(
        [candidate(539, allowed_paths=["scripts/shared.py"])],
        worker_states={"sora": "available"},
        active_paths={"scripts/**"},
    )
    assert result["status"] == "OWNER_CONFLICT"
    assert result["metrics"]["duplicate_start_prevented_count"] == 1


def test_glob_prefix_conflict_concrete_active_vs_glob_candidate():
    """Active path scripts/shared.py should conflict with candidate path scripts/**"""
    result = select_next_work(
        [candidate(539, allowed_paths=["scripts/**"])],
        worker_states={"sora": "available"},
        active_paths={"scripts/shared.py"},
    )
    assert result["status"] == "OWNER_CONFLICT"
    assert result["metrics"]["duplicate_start_prevented_count"] == 1


def test_unrelated_paths_no_conflict():
    """Unrelated paths should not conflict"""
    result = select_next_work(
        [candidate(539, allowed_paths=["scripts/shared.py"])],
        worker_states={"sora": "available"},
        active_paths={"data/**"},
    )
    assert result["status"] == "SELECTED"
    assert result["selected"]["issue_number"] == 539


def test_blank_active_paths_no_conflict():
    """Empty active paths should not cause false conflicts"""
    result = select_next_work(
        [candidate(539, allowed_paths=["scripts/shared.py"])],
        worker_states={"sora": "available"},
        active_paths=set(),
    )
    assert result["status"] == "SELECTED"
    assert result["selected"]["issue_number"] == 539


def test_blank_candidate_paths_no_conflict():
    """Empty candidate paths should not cause false conflicts"""
    result = select_next_work(
        [candidate(539, allowed_paths=[])],
        worker_states={"sora": "available"},
        active_paths={"scripts/**"},
    )
    assert result["status"] == "SELECTED"
    assert result["selected"]["issue_number"] == 539


def test_empty_string_paths_no_conflict():
    """Empty string paths should be ignored"""
    result = select_next_work(
        [candidate(539, allowed_paths=["scripts/shared.py", ""])],
        worker_states={"sora": "available"},
        active_paths={""},
    )
    assert result["status"] == "SELECTED"
    assert result["selected"]["issue_number"] == 539


def test_deep_nested_glob_conflict():
    """Deep nesting: scripts/monitoring/** vs scripts/monitoring/status.py"""
    result = select_next_work(
        [candidate(539, allowed_paths=["scripts/monitoring/status.py"])],
        worker_states={"sora": "available"},
        active_paths={"scripts/monitoring/**"},
    )
    assert result["status"] == "OWNER_CONFLICT"
    assert result["metrics"]["duplicate_start_prevented_count"] == 1


def test_exact_match_still_conflicts():
    """Exact path match should still be detected as conflict (regression)"""
    result = select_next_work(
        [candidate(539, allowed_paths=["scripts/shared.py"])],
        worker_states={"sora": "available"},
        active_paths={"scripts/shared.py"},
    )
    assert result["status"] == "OWNER_CONFLICT"
    assert result["metrics"]["duplicate_start_prevented_count"] == 1


def test_multiple_candidates_with_partial_conflicts():
    """When multiple candidates exist with some conflicts, select the safe one"""
    result = select_next_work(
        [
            candidate(444, priority=1, allowed_paths=["scripts/shared.py"]),  # Conflicts
            candidate(539, priority=2, allowed_paths=["data/config.json"]),  # Safe
        ],
        worker_states={"sora": "available"},
        active_paths={"scripts/**"},
    )
    assert result["status"] == "SELECTED"
    assert result["selected"]["issue_number"] == 539
    assert result["metrics"]["duplicate_start_prevented_count"] == 1
