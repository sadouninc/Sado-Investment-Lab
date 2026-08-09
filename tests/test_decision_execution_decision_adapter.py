from copy import deepcopy

import pytest

from scripts.decision_execution_decision_adapter import (
    DecisionExecutionAdapterError,
    build_decision_execution_context,
    build_execution_intent_from_decision,
    build_risk_preflight_relation,
)


def decision(action="ADD", *, retrospective=False):
    return {
        "decided_at": "2026-08-09T10:30:00+09:00",
        "security_code": "6622",
        "company_name": "ダイヘン",
        "decision": action,
        "actor": "SADO",
        "confidence": "MEDIUM",
        "owner_judgment": {
            "why_now": "決算後の前提を確認した",
            "biggest_risk": "需要鈍化",
            "what_changes_my_mind": "受注と利益率が悪化する",
        },
        "system_snapshot": {},
        "evidence_refs": [],
        "retrospective_note": retrospective,
    }


def explicit_intent(**updates):
    payload = {
        "captured_at": "2026-08-09T10:30:00+09:00",
        "intended_quantity": 100,
        "price_condition": {"type": "LIMIT", "value": 12000},
        "timing_condition": {
            "execute_by": "2026-08-09T15:00:00+09:00",
            "session": "PM",
        },
        "account_type": "CASH",
        "source": "OWNER_EXPLICIT",
    }
    payload.update(updates)
    return payload


def risk_snapshot(action="ADD", *, captured_at="2026-08-09T10:25:00+09:00", code="6622"):
    return {
        "snapshot_id": "risk-preflight:6622:add:001",
        "captured_at": captured_at,
        "proposed_action": {
            "security_code": code,
            "action": action,
            "quantity": 100,
            "price": 12000,
            "account_type": "CASH",
        },
        "before": {},
        "after_if_executed": {},
        "guardrail_results": [
            {"guardrail": "SINGLE_NAME", "result": "UNKNOWN", "reason": "rule unset"}
        ],
        "data_status": "PARTIAL",
    }


def test_explicit_owner_intent_projects_to_core_without_inference():
    result = build_execution_intent_from_decision(decision(), explicit_intent())
    assert result["action"] == "ADD"
    assert result["security_code"] == "6622"
    assert result["intended_quantity"] == 100
    assert result["price_condition"] == {"type": "LIMIT", "value": 12000, "lower": None, "upper": None}
    assert result["account_type"] == "CASH"
    assert result["source"] == "OWNER_EXPLICIT"


def test_action_only_intent_does_not_invent_quantity_price_or_timing():
    result = build_execution_intent_from_decision(decision("BUY"), {})
    assert result["action"] == "BUY"
    assert result["intended_quantity"] is None
    assert result["intended_notional"] is None
    assert result["price_condition"]["type"] == "UNKNOWN"
    assert result["timing_condition"]["session"] == "UNKNOWN"
    assert result["account_type"] == "UNKNOWN"


def test_missing_intent_stays_missing():
    result = build_decision_execution_context(decision(), explicit_intent=None)
    assert result["execution_intent"] is None
    assert result["intent_status"] == "NOT_RECORDED"
    assert result["trade_action"] is None


def test_actual_execution_fields_cannot_be_used_as_owner_intent():
    with pytest.raises(DecisionExecutionAdapterError, match="actual execution fields"):
        build_execution_intent_from_decision(decision(), explicit_intent(fills=[]))


def test_decision_action_conflict_is_fail_closed():
    with pytest.raises(DecisionExecutionAdapterError, match="action conflicts"):
        build_execution_intent_from_decision(decision("ADD"), explicit_intent(action="BUY"))


def test_future_intent_timestamp_is_rejected():
    with pytest.raises(DecisionExecutionAdapterError, match="after decided_at"):
        build_execution_intent_from_decision(
            decision(), explicit_intent(captured_at="2026-08-09T10:31:00+09:00")
        )


def test_retrospective_decision_cannot_create_ex_ante_intent():
    with pytest.raises(DecisionExecutionAdapterError, match="retrospective"):
        build_execution_intent_from_decision(decision(retrospective=True), explicit_intent())


def test_non_execution_decision_does_not_accept_execution_intent():
    with pytest.raises(DecisionExecutionAdapterError, match="not an executable"):
        build_execution_intent_from_decision(decision("HOLD"), {})


def test_valid_preflight_relation_keeps_explicit_ref_and_partial_status():
    relation = build_risk_preflight_relation(decision(), risk_snapshot())
    assert relation == {
        "type": "DECISION_RISK_PREFLIGHT_RELATION",
        "decision_ref": build_decision_execution_context(decision())["decision_ref"],
        "risk_snapshot_ref": "risk-preflight:6622:add:001",
        "captured_at": "2026-08-09T10:25:00+09:00",
        "security_code": "6622",
        "proposed_action": "ADD",
        "data_status": "PARTIAL",
        "relation": "PRE_DECISION_PREFLIGHT",
    }


def test_future_preflight_is_rejected_as_lookahead():
    with pytest.raises(DecisionExecutionAdapterError, match="after decided_at"):
        build_risk_preflight_relation(
            decision(), risk_snapshot(captured_at="2026-08-09T10:31:00+09:00")
        )


def test_preflight_action_and_security_must_match_decision():
    with pytest.raises(DecisionExecutionAdapterError, match="proposed action conflicts"):
        build_risk_preflight_relation(decision("ADD"), risk_snapshot(action="BUY"))
    with pytest.raises(DecisionExecutionAdapterError, match="security_code conflicts"):
        build_risk_preflight_relation(decision(), risk_snapshot(code="4063"))


def test_no_preflight_stays_null_and_is_not_inferred():
    context = build_decision_execution_context(decision(), explicit_intent=explicit_intent())
    assert context["risk_preflight_relation"] is None


def test_non_execution_context_is_not_applicable_without_inference():
    context = build_decision_execution_context(decision("PASS"))
    assert context["execution_intent"] is None
    assert context["intent_status"] == "NOT_APPLICABLE"
    assert context["risk_preflight_relation"] is None


def test_adapter_is_deterministic_and_does_not_mutate_inputs():
    source_decision = decision()
    source_intent = explicit_intent()
    source_risk = risk_snapshot()
    before = deepcopy((source_decision, source_intent, source_risk))

    first = build_decision_execution_context(
        source_decision, explicit_intent=source_intent, risk_preflight=source_risk
    )
    second = build_decision_execution_context(
        source_decision, explicit_intent=source_intent, risk_preflight=source_risk
    )

    assert first == second
    assert (source_decision, source_intent, source_risk) == before
