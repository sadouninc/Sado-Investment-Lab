from scripts.away_queue_policy import select_away_work, should_replenish_away_queue


def candidate(issue=600, worker="sora"):
    return {
        "issue_number": issue,
        "priority": 1,
        "risk": "GREEN",
        "owner_slice": f"slice-{issue}",
        "allowed_paths": [f"scripts/{issue}.py"],
        "dependencies_satisfied": True,
        "preflight_valid": True,
        "preferred_worker": worker,
    }


def test_awake_worker_with_zero_open_pr_triggers_replenishment():
    assert should_replenish_away_queue(
        user_mode="AWAY", open_pr_count=0, worker_state="idle"
    ) is True


def test_active_mode_does_not_use_away_replenishment_policy():
    assert should_replenish_away_queue(
        user_mode="ACTIVE", open_pr_count=0, worker_state="idle"
    ) is False


def test_open_pr_prevents_new_away_queue_fill():
    result = select_away_work(
        [candidate()],
        user_mode="AWAY",
        open_pr_count=1,
        worker="sora",
        worker_states={"sora": "idle"},
    )
    assert result["status"] == "NO_REPLENISH_TRIGGER"


def test_away_queue_reuses_pure_selector_and_excludes_quota_worker():
    result = select_away_work(
        [candidate(worker="kai")],
        user_mode="AWAY",
        open_pr_count=0,
        worker="kai",
        worker_states={"kai": "quota_blocked"},
    )
    assert result["status"] == "NO_REPLENISH_TRIGGER"


def test_away_queue_selects_one_safe_candidate():
    result = select_away_work(
        [candidate(issue=582, worker="copilot")],
        user_mode="AWAY",
        open_pr_count=0,
        worker="copilot",
        worker_states={"copilot": "idle"},
    )
    assert result["status"] == "SELECTED"
    assert result["selected"]["issue_number"] == 582
    assert result["metrics"]["away_replenish_triggered"] == 1
