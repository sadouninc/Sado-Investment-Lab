from datetime import datetime, timedelta, timezone

import pytest

from scripts.multi_executor_router import evaluate_lease, issue_lease, select_queue_starvation_route, select_route

NOW = datetime(2026, 8, 19, 0, 0, tzinfo=timezone.utc)

def healthy_providers(**overrides):
    base = {"AMAZON_Q": {"state": "HEALTHY", "consecutive_activation_failures": 0}, "JULES": {"state": "HEALTHY", "consecutive_activation_failures": 0}, "COPILOT": {"state": "HEALTHY", "consecutive_activation_failures": 0}, "SORA": {"state": "AVAILABLE", "consecutive_activation_failures": 0}}
    base.update(overrides)
    return base

def candidate(**overrides):
    data = {"work_ref": "#900", "task_class": "CODE", "priority": 1, "risk": "GREEN", "allowed_paths": ["scripts/example.py"], "forbidden_paths": [".github/**", "TEAM_RULES.md"], "base_sha": "abc123", "eligible_executors": ["AMAZON_Q", "JULES", "COPILOT", "SORA"], "preflight_valid": True, "dependencies_satisfied": True, "owner_conflict": False, "path_conflict": False, "authority": "EXECUTOR", "broadcast_sync_verified": True}
    data.update(overrides)
    return data

def test_free_first_prefers_amazon_q_when_healthy():
    result = select_route([candidate()], provider_health=healthy_providers())
    assert result["status"] == "SELECTED" and result["executor"] == "AMAZON_Q" and result["fallback_order"] == ("JULES", "COPILOT", "SORA")

def test_provider_with_two_activation_failures_is_skipped():
    providers = healthy_providers(AMAZON_Q={"state": "HEALTHY", "consecutive_activation_failures": 2})
    assert select_route([candidate()], provider_health=providers)["executor"] == "JULES"

def test_malformed_provider_health_fails_closed_and_falls_back():
    providers = healthy_providers(AMAZON_Q={"state": "HEALTHY", "consecutive_activation_failures": "two"})
    assert select_route([candidate()], provider_health=providers)["executor"] == "JULES"

def test_cooldown_without_provider_clock_fails_closed_and_falls_back():
    providers = healthy_providers(AMAZON_Q={"state": "HEALTHY", "consecutive_activation_failures": 0, "cooldown_until": "2026-08-19T00:30:00+00:00"})
    assert select_route([candidate()], provider_health=providers)["executor"] == "JULES"

def test_provider_unavailable_falls_back_to_sora():
    providers = healthy_providers(AMAZON_Q={"state": "BLOCKED", "consecutive_activation_failures": 0}, JULES={"state": "BLOCKED", "consecutive_activation_failures": 0}, COPILOT={"state": "BLOCKED", "consecutive_activation_failures": 0})
    assert select_route([candidate()], provider_health=providers)["executor"] == "SORA"

def test_conflict_fails_closed():
    assert select_route([candidate(owner_conflict=True)], provider_health=healthy_providers()) == {"status": "ROUTING_CONFLICT", "selected": None}

def test_invalid_preflight_fails_closed():
    assert select_route([candidate(preflight_valid=False)], provider_health=healthy_providers()) == {"status": "PREFLIGHT_INVALID", "selected": None}

def test_missing_work_ref_fails_closed_not_crash():
    raw = candidate(); raw.pop("work_ref")
    assert select_route([raw], provider_health=healthy_providers()) == {"status": "PREFLIGHT_INVALID", "selected": None}

def test_broadcast_sync_must_be_explicit_true():
    assert select_route([candidate(broadcast_sync_verified=False)], provider_health=healthy_providers())["status"] == "BROADCAST_SYNC_UNVERIFIED"

def test_missing_authority_fails_closed():
    raw = candidate(); raw.pop("authority")
    assert select_route([raw], provider_health=healthy_providers())["status"] == "AUTHORITY_UNKNOWN"

def test_owner_authority_is_distinct_block():
    assert select_route([candidate(authority="OWNER_AUTHORITY")], provider_health=healthy_providers())["status"] == "OWNER_AUTHORITY"

def test_selection_is_deterministic_by_priority_then_work_ref():
    result = select_route([candidate(work_ref="#902", priority=2), candidate(work_ref="#901", priority=1)], provider_health=healthy_providers())
    assert result["work_ref"] == "#901"

def test_issue_lease_has_canonical_deadlines_and_stable_id():
    selection = select_route([candidate()], provider_health=healthy_providers()); first = issue_lease(selection, assigned_at=NOW); second = issue_lease(selection, assigned_at=NOW)
    assert first["lease_id"] == second["lease_id"]
    assert first["lease_id"].startswith("lease-") and len(first["lease_id"]) == 38
    assert first["ack_deadline"] == (NOW + timedelta(minutes=10)).isoformat() and first["execution_evidence_deadline"] is None

def test_issue_lease_rejects_incomplete_selected_structure():
    with pytest.raises(ValueError, match="invalid selection structure"):
        issue_lease({"status": "SELECTED", "work_ref": "#900"}, assigned_at=NOW)

def test_no_ack_expires_at_ten_minutes():
    lease = issue_lease(select_route([candidate()], provider_health=healthy_providers()), assigned_at=NOW); result = evaluate_lease(lease, now=NOW + timedelta(minutes=10))
    assert result["status"] == "DISPATCH_ACK_EXPIRED" and result["terminal"] is True

def test_ack_without_evidence_stalls_after_twenty_minutes():
    lease = issue_lease(select_route([candidate()], provider_health=healthy_providers()), assigned_at=NOW); ack = NOW + timedelta(minutes=5); result = evaluate_lease(lease, now=ack + timedelta(minutes=20), acknowledged_at=ack)
    assert result["status"] == "ACK_STALLED" and result["terminal"] is True

def test_execution_evidence_wins_before_expiry():
    lease = issue_lease(select_route([candidate()], provider_health=healthy_providers()), assigned_at=NOW)
    assert evaluate_lease(lease, now=NOW + timedelta(minutes=7), acknowledged_at=NOW + timedelta(minutes=2), execution_evidence_at=NOW + timedelta(minutes=6)) == {"status": "EXECUTION_EVIDENCE", "terminal": False}

def test_late_ack_never_revives_expired_lease():
    lease = issue_lease(select_route([candidate()], provider_health=healthy_providers()), assigned_at=NOW); result = evaluate_lease(lease, now=NOW + timedelta(minutes=12), acknowledged_at=NOW + timedelta(minutes=11))
    assert result["status"] == "DISPATCH_ACK_EXPIRED" and result["late_ack"] is True

def test_naive_assigned_at_rejected():
    with pytest.raises(ValueError):
        issue_lease(select_route([candidate()], provider_health=healthy_providers()), assigned_at=datetime(2026, 8, 19, 0, 0))

def test_naive_stored_lease_timestamp_rejected():
    lease = issue_lease(select_route([candidate()], provider_health=healthy_providers()), assigned_at=NOW); lease["assigned_at"] = "2026-08-19T00:00:00"
    with pytest.raises(ValueError, match="assigned_at must be timezone-aware"):
        evaluate_lease(lease, now=NOW + timedelta(minutes=1))


def queue_candidate(**overrides):
    data = candidate(labels=["READY_FOR_IMPLEMENTATION"], ready_observed_at=NOW.isoformat(), live_lease=False, implementation_owner="")
    data.update(overrides)
    return data


def test_queue_starvation_selects_fresh_ready_work_when_capacity_is_free():
    result = select_queue_starvation_route([queue_candidate()], provider_health=healthy_providers(), now=NOW, implementation_capacity_free=True)
    assert result["status"] == "SELECTED" and result["work_ref"] == "#900"


def test_queue_starvation_fails_closed_without_safe_candidate():
    result = select_queue_starvation_route([queue_candidate(labels=[])], provider_health=healthy_providers(), now=NOW, implementation_capacity_free=True)
    assert result == {"status": "READY_REQUIRED", "selected": None}


def test_queue_starvation_suppresses_live_lease_and_owner_duplicates():
    live = select_queue_starvation_route([queue_candidate(live_lease=True)], provider_health=healthy_providers(), now=NOW, implementation_capacity_free=True)
    owned = select_queue_starvation_route([queue_candidate(implementation_owner="SORA")], provider_health=healthy_providers(), now=NOW, implementation_capacity_free=True)
    assert live["status"] == "DUPLICATE_IMPLEMENTATION"
    assert owned["status"] == "DUPLICATE_IMPLEMENTATION"


def test_queue_starvation_hard_denies_issue_79():
    result = select_queue_starvation_route([queue_candidate(work_ref="#79")], provider_health=healthy_providers(), now=NOW, implementation_capacity_free=True)
    assert result == {"status": "ISSUE_79_HARD_DENY", "selected": None}


def test_queue_starvation_does_not_consume_nonimplementation_capacity():
    result = select_queue_starvation_route([queue_candidate()], provider_health=healthy_providers(), now=NOW, implementation_capacity_free=False)
    assert result == {"status": "IMPLEMENTATION_CAPACITY_FULL", "selected": None}


def test_queue_starvation_stale_ready_fails_closed():
    result = select_queue_starvation_route([queue_candidate(ready_observed_at=(NOW - timedelta(hours=25)).isoformat())], provider_health=healthy_providers(), now=NOW, implementation_capacity_free=True)
    assert result == {"status": "READY_STALE_OR_UNKNOWN", "selected": None}
