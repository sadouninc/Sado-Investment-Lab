from scripts.flow_health_guard import (
    active_implementation_wip,
    evaluate_flow_health,
    waiting_work_count,
)


def test_review_and_ci_wait_do_not_consume_active_implementation_wip():
    states = ("REVIEW_WAIT", "CI_WAIT", "RESEARCH_GATE_WAIT", "MERGE_READY")
    assert active_implementation_wip(states) == 0
    assert waiting_work_count(states) == 4


def test_implementing_and_revision_required_consume_wip():
    states = ("IMPLEMENTING", "REVISION_REQUIRED", "REVIEW_WAIT")
    assert active_implementation_wip(states) == 2


def test_ready_plus_zero_active_wip_is_queue_starvation_even_with_waiting_prs():
    result = evaluate_flow_health(
        {
            "user_mode": "AWAY",
            "worker_state": "idle",
            "work_states": ["REVIEW_WAIT", "RESEARCH_GATE_WAIT"],
            "ready_nonconflicting_count": 1,
            "last_durable_output_age_minutes": 30,
        }
    )
    assert result["status"] == "CRITICAL"
    assert result["active_implementation_wip"] == 0
    assert "QUEUE_STARVATION" in result["reasons"]
    assert "ROUTE_READY_WORK" in result["actions"]
    assert "WAITING_WORK_RELEASES_IMPLEMENTATION_CAPACITY" in result["reasons"]


def test_two_hour_durable_output_stall_warns_when_ready_work_exists():
    result = evaluate_flow_health(
        {
            "user_mode": "AWAY",
            "worker_state": "idle",
            "work_states": ["IMPLEMENTING"],
            "ready_nonconflicting_count": 1,
            "last_durable_output_age_minutes": 120,
        }
    )
    assert result["status"] == "WARN"
    assert "FLOW_STALL_WARNING" in result["reasons"]


def test_four_hour_durable_output_stall_is_critical_and_requires_same_run_reroute():
    result = evaluate_flow_health(
        {
            "user_mode": "AWAY",
            "worker_state": "idle",
            "work_states": ["IMPLEMENTING"],
            "ready_nonconflicting_count": 2,
            "last_durable_output_age_minutes": 240,
        }
    )
    assert result["status"] == "CRITICAL"
    assert "FLOW_STALL_CRITICAL" in result["reasons"]
    assert "REROUTE_SAME_RUN" in result["actions"]


def test_legacy_last_new_pr_age_is_accepted_but_marked_as_legacy_signal():
    result = evaluate_flow_health(
        {
            "user_mode": "AWAY",
            "worker_state": "idle",
            "work_states": ["IMPLEMENTING"],
            "ready_nonconflicting_count": 1,
            "last_new_pr_age_minutes": 120,
        }
    )
    assert result["status"] == "WARN"
    assert result["durable_signal_source"] == "legacy:last_new_pr_age_minutes"


def test_agent_dispatch_unacked_for_60_minutes_expires_lease():
    result = evaluate_flow_health(
        {
            "user_mode": "AWAY",
            "worker_state": "idle",
            "work_states": ["IMPLEMENTING"],
            "ready_nonconflicting_count": 0,
            "last_durable_output_age_minutes": 20,
            "dispatch_unacked_age_minutes": 60,
        }
    )
    assert result["status"] == "CRITICAL"
    assert "DISPATCH_LEASE_EXPIRED" in result["reasons"]
    assert "EXPIRE_OR_REROUTE_DISPATCH" in result["actions"]


def test_same_blocker_two_runs_requires_blocked_escape():
    result = evaluate_flow_health(
        {
            "user_mode": "AWAY",
            "worker_state": "idle",
            "work_states": ["REVIEW_WAIT"],
            "ready_nonconflicting_count": 0,
            "last_durable_output_age_minutes": 10,
            "same_blocker_run_count": 2,
        }
    )
    assert result["status"] == "CRITICAL"
    assert "BLOCKED_ESCAPE_OVERDUE" in result["reasons"]
    assert "BLOCKED_ESCAPE" in result["actions"]


def test_unknown_durable_output_age_is_not_silently_passed_when_ready_exists():
    result = evaluate_flow_health(
        {
            "user_mode": "AWAY",
            "worker_state": "idle",
            "work_states": ["IMPLEMENTING"],
            "ready_nonconflicting_count": 1,
            "last_durable_output_age_minutes": None,
        }
    )
    assert result["status"] == "WARN"
    assert "DURABLE_OUTPUT_AGE_UNKNOWN" in result["reasons"]
    assert "COLLECT_DURABLE_OUTPUT_AGE" in result["actions"]


def test_unknown_durable_age_never_downgrades_existing_critical_status():
    result = evaluate_flow_health(
        {
            "user_mode": "AWAY",
            "worker_state": "idle",
            "work_states": ["REVIEW_WAIT"],
            "ready_nonconflicting_count": 1,
            "last_durable_output_age_minutes": None,
            "dispatch_unacked_age_minutes": 60,
        }
    )
    assert result["status"] == "CRITICAL"
    assert "QUEUE_STARVATION" in result["reasons"]
    assert "DISPATCH_LEASE_EXPIRED" in result["reasons"]
    assert "DURABLE_OUTPUT_AGE_UNKNOWN" in result["reasons"]


def test_stale_unknown_worker_state_does_not_hide_zero_wip_starvation():
    result = evaluate_flow_health(
        {
            "user_mode": "AWAY",
            "worker_state": "unknown",
            "work_states": ["REVIEW_WAIT"],
            "ready_nonconflicting_count": 1,
            "last_durable_output_age_minutes": 20,
        }
    )
    assert result["status"] == "CRITICAL"
    assert "QUEUE_STARVATION" in result["reasons"]


def test_explicitly_blocked_worker_triggers_reroute_instead_of_silent_noop():
    result = evaluate_flow_health(
        {
            "user_mode": "AWAY",
            "worker_state": "quota_blocked",
            "work_states": ["REVIEW_WAIT"],
            "ready_nonconflicting_count": 1,
            "last_durable_output_age_minutes": 20,
        }
    )
    assert result["status"] == "CRITICAL"
    assert "WORKER_CAPACITY_BLOCKED" in result["reasons"]
    assert "REROUTE_TO_AVAILABLE_WORKER" in result["actions"]
