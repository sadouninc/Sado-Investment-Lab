from datetime import datetime, timedelta, timezone

import pytest

from scripts.multi_executor_router import evaluate_lease, issue_lease, select_route


NOW = datetime(2026, 8, 19, 0, 0, tzinfo=timezone.utc)


def healthy_providers(**overrides):
    base = {
        "AMAZON_Q": {"state": "HEALTHY", "consecutive_activation_failures": 0},
        "JULES": {"state": "HEALTHY", "consecutive_activation_failures": 0},
        "SORA": {"state": "AVAILABLE", "consecutive_activation_failures": 0},
    }
    base.update(overrides)
    return base


def candidate(**overrides):
    data = {
        "work_ref": "#900",
        "task_class": "CODE",
        "priority": 1,
        "risk": "GREEN",
        "allowed_paths": ["scripts/example.py"],
        "forbidden_paths": [".github/**", "TEAM_RULES.md"],
        "base_sha": "abc123",
        "eligible_executors": ["AMAZON_Q", "JULES", "SORA"],
        "preflight_valid": True,
        "dependencies_satisfied": True,
        "owner_conflict": False,
        "path_conflict": False,
    }
    data.update(overrides)
    return data


def test_free_first_prefers_amazon_q_when_healthy():
    result = select_route([candidate()], provider_health=healthy_providers())
    assert result["status"] == "SELECTED"
    assert result["executor"] == "AMAZON_Q"
    assert result["fallback_order"] == ("JULES", "SORA")


def test_provider_with_two_activation_failures_is_skipped():
    providers = healthy_providers(
        AMAZON_Q={"state": "HEALTHY", "consecutive_activation_failures": 2}
    )
    result = select_route([candidate()], provider_health=providers)
    assert result["executor"] == "JULES"


def test_provider_unavailable_falls_back_to_sora():
    providers = healthy_providers(
        AMAZON_Q={"state": "BLOCKED", "consecutive_activation_failures": 0},
        JULES={"state": "BLOCKED", "consecutive_activation_failures": 0},
    )
    result = select_route([candidate()], provider_health=providers)
    assert result["executor"] == "SORA"


def test_conflict_fails_closed():
    result = select_route(
        [candidate(owner_conflict=True)], provider_health=healthy_providers()
    )
    assert result == {"status": "ROUTING_CONFLICT", "selected": None}


def test_invalid_preflight_fails_closed():
    result = select_route(
        [candidate(preflight_valid=False)], provider_health=healthy_providers()
    )
    assert result == {"status": "PREFLIGHT_INVALID", "selected": None}


def test_selection_is_deterministic_by_priority_then_work_ref():
    result = select_route(
        [candidate(work_ref="#902", priority=2), candidate(work_ref="#901", priority=1)],
        provider_health=healthy_providers(),
    )
    assert result["work_ref"] == "#901"


def test_issue_lease_has_canonical_deadlines_and_stable_id():
    selection = select_route([candidate()], provider_health=healthy_providers())
    first = issue_lease(selection, assigned_at=NOW)
    second = issue_lease(selection, assigned_at=NOW)
    assert first["lease_id"] == second["lease_id"]
    assert first["ack_deadline"] == (NOW + timedelta(minutes=10)).isoformat()
    assert first["execution_evidence_deadline"] is None


def test_no_ack_expires_at_ten_minutes():
    selection = select_route([candidate()], provider_health=healthy_providers())
    lease = issue_lease(selection, assigned_at=NOW)
    result = evaluate_lease(lease, now=NOW + timedelta(minutes=10))
    assert result["status"] == "DISPATCH_ACK_EXPIRED"
    assert result["terminal"] is True


def test_ack_without_evidence_stalls_after_twenty_minutes():
    selection = select_route([candidate()], provider_health=healthy_providers())
    lease = issue_lease(selection, assigned_at=NOW)
    ack = NOW + timedelta(minutes=5)
    result = evaluate_lease(
        lease, now=ack + timedelta(minutes=20), acknowledged_at=ack
    )
    assert result["status"] == "ACK_STALLED"
    assert result["terminal"] is True


def test_execution_evidence_wins_before_expiry():
    selection = select_route([candidate()], provider_health=healthy_providers())
    lease = issue_lease(selection, assigned_at=NOW)
    result = evaluate_lease(
        lease,
        now=NOW + timedelta(minutes=7),
        acknowledged_at=NOW + timedelta(minutes=2),
        execution_evidence_at=NOW + timedelta(minutes=6),
    )
    assert result == {"status": "EXECUTION_EVIDENCE", "terminal": False}


def test_late_ack_never_revives_expired_lease():
    selection = select_route([candidate()], provider_health=healthy_providers())
    lease = issue_lease(selection, assigned_at=NOW)
    late_ack = NOW + timedelta(minutes=11)
    result = evaluate_lease(
        lease, now=NOW + timedelta(minutes=12), acknowledged_at=late_ack
    )
    assert result["status"] == "DISPATCH_ACK_EXPIRED"
    assert result["late_ack"] is True


def test_naive_assigned_at_rejected():
    selection = select_route([candidate()], provider_health=healthy_providers())
    with pytest.raises(ValueError):
        issue_lease(selection, assigned_at=datetime(2026, 8, 19, 0, 0))
