from datetime import datetime, timedelta, timezone

from scripts.multi_executor_reconciler import Observation, dispatch_once, reconcile_lease, reroute_after_terminal, terminal_telemetry
from scripts.multi_executor_router import issue_lease, select_route

NOW = datetime(2026, 8, 19, 0, 0, tzinfo=timezone.utc)

def candidate(**overrides):
    data = {"work_ref": "#900", "task_class": "CODE", "priority": 1, "risk": "GREEN", "allowed_paths": ["scripts/x.py"], "forbidden_paths": [".github/**", "#79"], "base_sha": "abc", "eligible_executors": ["AMAZON_Q", "JULES", "SORA"], "preflight_valid": True, "dependencies_satisfied": True, "owner_conflict": False, "path_conflict": False, "authority": "EXECUTOR", "broadcast_sync_verified": True}
    data.update(overrides); return data

def health():
    return {"AMAZON_Q": {"state": "HEALTHY", "consecutive_activation_failures": 0}, "JULES": {"state": "HEALTHY", "consecutive_activation_failures": 0}, "SORA": {"state": "AVAILABLE", "consecutive_activation_failures": 0}}

def lease():
    return issue_lease(select_route([candidate()], provider_health=health()), assigned_at=NOW)

def test_dispatch_is_idempotent_by_durable_marker():
    item = lease(); calls = []
    first = dispatch_once(item, comments=[], execute=calls.append)
    comments = [{"body": first["evidence_marker"]}]
    second = dispatch_once(item, comments=comments, execute=calls.append)
    assert first["status"] == "DISPATCHED" and second["status"] == "ALREADY_DISPATCHED" and len(calls) == 1

def test_pr_open_releases_capacity_and_suppresses_competitor():
    state = reconcile_lease(lease(), now=NOW + timedelta(minutes=3), observation=Observation(pr_open=True))
    assert state["status"] == "PR_OPEN" and state["implementation_capacity_released"] is True and state["suppress_competing_lease"] is True

def test_execution_evidence_suppresses_competing_lease():
    state = reconcile_lease(lease(), now=NOW + timedelta(minutes=5), observation=Observation(execution_evidence_at=NOW + timedelta(minutes=4)))
    assert state["status"] == "EXECUTION_EVIDENCE" and state["suppress_competing_lease"] is True

def test_expired_lease_fresh_preflights_and_reroutes_away_from_failed_provider():
    old = lease(); state = reconcile_lease(old, now=NOW + timedelta(minutes=10), observation=Observation()); seen = []
    def preflight(raw):
        seen.append(raw["work_ref"]); return dict(raw)
    result = reroute_after_terminal(lease=old, state=state, candidates=[candidate()], provider_health=health(), preflight=preflight, assigned_at=NOW + timedelta(minutes=11))
    assert seen == ["#900"] and result["status"] == "REROUTED" and result["fresh_preflight"] is True and result["lease"]["executor"] == "JULES"

def test_ack_stalled_reroutes_after_fresh_preflight():
    old = lease(); ack = NOW + timedelta(minutes=2); state = reconcile_lease(old, now=ack + timedelta(minutes=20), observation=Observation(acknowledged_at=ack))
    result = reroute_after_terminal(lease=old, state=state, candidates=[candidate()], provider_health=health(), preflight=lambda raw: dict(raw), assigned_at=NOW + timedelta(minutes=23))
    assert state["status"] == "ACK_STALLED" and result["status"] == "REROUTED"

def test_nonterminal_state_does_not_reroute():
    old = lease(); state = reconcile_lease(old, now=NOW + timedelta(minutes=1), observation=Observation())
    assert reroute_after_terminal(lease=old, state=state, candidates=[candidate()], provider_health=health(), preflight=lambda raw: raw, assigned_at=NOW)["status"] == "NO_REROUTE"

def test_issue_79_is_hard_denied_during_reroute():
    old = lease(); state = {"status": "DISPATCH_ACK_EXPIRED", "terminal": True}
    result = reroute_after_terminal(lease=old, state=state, candidates=[candidate(work_ref="#79")], provider_health=health(), preflight=lambda raw: raw, assigned_at=NOW)
    assert result["status"] == "ISSUE_79_HARD_DENY"

def test_unknown_broadcast_from_fresh_preflight_never_reroutes():
    old = lease(); state = {"status": "DISPATCH_ACK_EXPIRED", "terminal": True}
    result = reroute_after_terminal(lease=old, state=state, candidates=[candidate(broadcast_sync_verified=False)], provider_health=health(), preflight=lambda raw: raw, assigned_at=NOW)
    assert result["status"] == "BROADCAST_SYNC_UNVERIFIED"

def test_terminal_telemetry_is_machine_readable():
    old = lease(); state = {"status": "DISPATCH_ACK_EXPIRED", "terminal": True}; reroute = {"status": "REROUTED", "lease": {"executor": "JULES"}}
    row = terminal_telemetry(lease=old, state=state, reroute=reroute)
    assert row["terminal_state"] == "DISPATCH_ACK_EXPIRED" and row["rerouted"] is True and row["next_executor"] == "JULES"
