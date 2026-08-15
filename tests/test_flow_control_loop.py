from datetime import datetime, timezone

from scripts.flow_control_loop import evaluate_and_select_flow_action, evaluate_dispatch_lease


def candidate(issue=642, worker="sora", owner_slice="slice-642"):
    return {
        "issue_number": issue,
        "priority": 1,
        "risk": "GREEN",
        "owner_slice": owner_slice,
        "allowed_paths": [f"scripts/{issue}.py"],
        "dependencies_satisfied": True,
        "preflight_valid": True,
        "preferred_worker": worker,
    }


def now():
    return datetime(2026, 8, 16, 0, 0, tzinfo=timezone.utc)


def test_dispatch_lease_requires_timezone_aware_timestamps():
    result = evaluate_dispatch_lease(
        {
            "work_ref": "#642",
            "fallback_owner": "sora",
            "owner_slice": "slice-642",
            "assigned_at": "2026-08-15T22:00:00",
            "lease_expires_at": "2026-08-15T23:00:00Z",
        },
        now=now(),
    )
    assert result["status"] == "INVALID"


def test_acknowledged_dispatch_never_expires_as_unacked():
    result = evaluate_dispatch_lease(
        {
            "work_ref": "#642",
            "fallback_owner": "sora",
            "owner_slice": "slice-642",
            "assigned_at": "2026-08-15T22:00:00Z",
            "lease_expires_at": "2026-08-15T23:00:00Z",
            "acknowledged_at": "2026-08-15T22:10:00Z",
        },
        now=now(),
    )
    assert result["status"] == "ACKNOWLEDGED"
    assert result["unacked_age_minutes"] is None


def test_expired_dispatch_exposes_fallback_and_age():
    result = evaluate_dispatch_lease(
        {
            "work_ref": "#642",
            "fallback_owner": "sora",
            "owner_slice": "slice-642",
            "assigned_at": "2026-08-15T22:00:00Z",
            "lease_expires_at": "2026-08-15T23:00:00Z",
        },
        now=now(),
    )
    assert result["status"] == "EXPIRED"
    assert result["fallback_owner"] == "sora"
    assert result["unacked_age_minutes"] == 120


def test_review_wait_starvation_invokes_queue_selector_same_decision():
    result = evaluate_and_select_flow_action(
        [candidate()],
        user_mode="AWAY",
        worker="sora",
        worker_states={"sora": "idle"},
        work_states=["REVIEW_WAIT", "RESEARCH_GATE_WAIT"],
        ready_nonconflicting_count=1,
        last_durable_output_age_minutes=30,
        now=now(),
    )
    assert result["health"]["status"] == "CRITICAL"
    assert "QUEUE_STARVATION" in result["health"]["reasons"]
    assert result["routing"]["status"] == "SELECTED"
    assert result["routing"]["selected"]["issue_number"] == 642
    assert result["routing"]["metrics"]["flow_routing_invoked"] == 1


def test_expired_dispatch_releases_owner_slice_before_reroute():
    result = evaluate_and_select_flow_action(
        [candidate(owner_slice="slice-642")],
        user_mode="AWAY",
        worker="sora",
        worker_states={"sora": "idle"},
        work_states=["REVIEW_WAIT"],
        ready_nonconflicting_count=1,
        last_durable_output_age_minutes=30,
        now=now(),
        dispatch_lease={
            "work_ref": "#642",
            "fallback_owner": "sora",
            "owner_slice": "slice-642",
            "assigned_at": "2026-08-15T22:00:00Z",
            "lease_expires_at": "2026-08-15T23:00:00Z",
        },
        active_owner_slices=["slice-642"],
    )
    assert result["dispatch_lease"]["status"] == "EXPIRED"
    assert "DISPATCH_LEASE_EXPIRED" in result["health"]["reasons"]
    assert result["routing"]["status"] == "SELECTED"


def test_blocked_worker_reroutes_to_another_available_worker():
    result = evaluate_and_select_flow_action(
        [candidate(issue=700, worker="copilot", owner_slice="slice-700")],
        user_mode="AWAY",
        worker="sora",
        worker_states={"sora": "quota_blocked", "copilot": "idle"},
        work_states=["REVIEW_WAIT"],
        ready_nonconflicting_count=1,
        last_durable_output_age_minutes=30,
        now=now(),
    )
    assert "WORKER_CAPACITY_BLOCKED" in result["health"]["reasons"]
    assert result["routing"]["status"] == "SELECTED"
    assert result["routing"]["selected"]["worker"] == "copilot"


def test_no_stall_does_not_invoke_selector():
    result = evaluate_and_select_flow_action(
        [candidate()],
        user_mode="AWAY",
        worker="sora",
        worker_states={"sora": "idle"},
        work_states=["IMPLEMENTING"],
        ready_nonconflicting_count=0,
        last_durable_output_age_minutes=10,
        now=now(),
    )
    assert result["health"]["status"] == "PASS"
    assert result["routing"]["status"] == "NO_ROUTING_ACTION"
    assert result["routing"]["metrics"]["flow_routing_invoked"] == 0
