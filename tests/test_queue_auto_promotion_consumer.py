from datetime import datetime, timezone
from scripts.queue_auto_promotion_consumer import build_bounded_candidates, plan_consumer_tick

ASSIGNED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)

def candidate(issue, *, worker="copilot", priority=1, risk="GREEN", **overrides):
    value={"issue_number":issue,"priority":priority,"risk":risk,"owner_slice":f"slice-{issue}","allowed_paths":[f"scripts/{issue}.py"],"dependencies_satisfied":True,"preflight_valid":True,"preferred_worker":worker}
    value.update(overrides); return value

def contract_body(**overrides):
    values={"version":"1","goal":'"deterministic work"',"status":"READY_FOR_IMPLEMENTATION","owner_slice":'"queue-consumer-candidate"',"risk":"GREEN","authority":"STANDARD","dependencies":"[]","allowed_paths":'["scripts/queue_demo.py"]',"forbidden_paths":'["TEAM_RULES.md", "TEAM_STATE.md", ".github/**"]',"acceptance_tests":'["pytest tests/test_queue_auto_promotion_consumer.py"]',"expected_outputs":'["PR"]',"human_gate":'["merge"]',"non_goals":'["automatic merge"]'}
    values.update(overrides); return "\n".join(["```yaml","work_contract:",*[f"  {k}: {v}" for k,v in values.items()],"```"])

def raw_issue(number, *, body=None, state="open", **overrides):
    value={"number":number,"title":f"issue {number}","state":state,"body":body or contract_body()}; value.update(overrides); return value

def tick(cands, workers={"copilot":"available"}, **kw):
    return plan_consumer_tick(cands,worker_states=workers,base_sha="deadbeef",assigned_at=ASSIGNED_AT,**kw)

def test_safe_candidate_produces_a_canonical_dispatch_ready_plan():
    r=tick([candidate(600)]); assert r["status"]=="DISPATCH_READY" and r["selected"]["issue_number"]==600 and r["dispatch"]

def test_dispatch_payload_targets_existing_canonical_workflow_with_valid_lease():
    d=tick([candidate(600)])["dispatch"]; assert d["workflow_dispatch"]["workflow"]=="ai-production-dispatch.yml"; assert d["workflow_dispatch"]["ref"]=="main"; assert d["workflow_dispatch"]["inputs"]["issue_number"]=="600"; lid=d["workflow_dispatch"]["inputs"]["lease_id"]; assert lid.startswith("lease-") and len(lid)==38 and all(c in "0123456789abcdef" for c in lid[6:]); assert d["evidence_comment"]==f"<!-- AUTO_ROUTER_DISPATCH lease_id={lid} executor=COPILOT target_issue=600 -->"

def test_deterministic_safe_selection_prefers_green_then_priority():
    cs=[candidate(444,priority=2,risk="GREEN"),candidate(539,priority=1,risk="AMBER")]; assert tick(cs)["selected"]["issue_number"]==tick(cs)["selected"]["issue_number"]==444

def test_no_safe_candidate_fails_closed_without_dispatch():
    r=tick([]); assert r["status"]=="NO_SAFE_CANDIDATE" and r["dispatch"] is None

def test_blocked_dependency_and_preflight_candidates_fail_closed_without_dispatch():
    a=tick([candidate(600,dependencies_satisfied=False)]); b=tick([candidate(601,preflight_valid=False)]); assert a["status"]=="DEPENDENCY_BLOCKED" and a["dispatch"] is None; assert b["status"]=="PREFLIGHT_INVALID" and b["dispatch"] is None

def test_duplicate_active_lease_owner_slice_conflict_fails_closed_without_dispatch():
    r=tick([candidate(600,owner_slice="556-autonomous-queue-consumer")],active_owner_slices={"556-autonomous-queue-consumer"}); assert r["status"]=="OWNER_CONFLICT" and r["dispatch"] is None and r["metrics"]["duplicate_start_prevented_count"]==1

def test_active_conflicting_path_fails_closed_without_dispatch():
    r=tick([candidate(600,allowed_paths=["scripts/shared.py"])],active_paths={"scripts/shared.py"}); assert r["status"]=="OWNER_CONFLICT" and r["dispatch"] is None

def test_worker_unavailable_and_unknown_fail_closed():
    assert tick([candidate(600)],{"copilot":"quota_blocked"})["status"]=="WORKER_BLOCKED"; assert tick([candidate(600)],{})["status"]=="WORKER_BLOCKED"

def test_issue_79_is_never_selected_even_as_the_only_candidate():
    r=tick([candidate(79)]); assert r["status"]=="PROTECTED_ISSUE_79" and r["selected"] is None and r["dispatch"] is None

def test_non_copilot_worker_is_left_to_existing_dispatch_path():
    r=tick([candidate(600,worker="jules")],{"jules":"available"}); assert r["status"]=="UNSUPPORTED_WORKER" and r["dispatch"] is None

def test_each_tick_produces_one_fresh_lease_even_for_same_candidate():
    a=tick([candidate(600)]); b=plan_consumer_tick([candidate(600)],worker_states={"copilot":"available"},base_sha="deadbeef",assigned_at=datetime(2026,1,1,0,1,tzinfo=timezone.utc)); assert a["dispatch"]["workflow_dispatch"]["inputs"]["lease_id"]!=b["dispatch"]["workflow_dispatch"]["inputs"]["lease_id"]

def test_build_bounded_candidates_trusts_preflight_not_label():
    c=build_bounded_candidates([raw_issue(600)]); assert len(c)==1 and c[0]["issue_number"]==600 and c[0]["preflight_valid"] is True and c[0]["dependencies_satisfied"] is True and c[0]["preferred_worker"]=="copilot"

def test_build_bounded_candidates_excludes_issue_79():
    assert build_bounded_candidates([raw_issue(79)])==[]

def test_build_bounded_candidates_fails_closed_on_dependencies_authority_and_malformed():
    assert build_bounded_candidates([raw_issue(600,body=contract_body(dependencies='["#829"]'))])[0]["dependencies_satisfied"] is False
    assert build_bounded_candidates([raw_issue(600,body=contract_body(authority="OWNER_REQUIRED"))])[0]["preflight_valid"] is False
    c=build_bounded_candidates([raw_issue(600,body="not a contract")])[0]; assert c["preflight_valid"] is False and c["dependencies_satisfied"] is False

def test_end_to_end_bounded_candidate_reaches_dispatch_ready():
    r=tick(build_bounded_candidates([raw_issue(600)])); assert r["status"]=="DISPATCH_READY" and r["selected"]["issue_number"]==600
