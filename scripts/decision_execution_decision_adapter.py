from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping

from scripts.decision_execution_fidelity import validate_execution_intent
from scripts.investment_decision_journal import validate_decision
from scripts.portfolio_risk_preflight_integrations import decision_journal_ref


EXECUTION_DECISIONS = {"BUY", "ADD", "REDUCE", "SELL"}
_ACTUAL_ONLY_FIELDS = {
    "fills",
    "execution_status",
    "execution_snapshot_id",
    "actual_action",
    "position_before_ref",
    "position_after_ref",
}


class DecisionExecutionAdapterError(ValueError):
    pass


def _dt(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise DecisionExecutionAdapterError(f"{field} must be a non-empty string")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise DecisionExecutionAdapterError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise DecisionExecutionAdapterError(f"{field} must include timezone")
    return parsed


def _validated_decision(decision: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(decision, Mapping):
        raise DecisionExecutionAdapterError("decision must be an object")
    try:
        return validate_decision(dict(decision))
    except ValueError as exc:
        raise DecisionExecutionAdapterError(str(exc)) from exc


def build_execution_intent_from_decision(
    decision: Mapping[str, Any],
    explicit_intent: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Project only decision-time explicit execution intent into the #251 core contract.

    The Decision Journal is authoritative for the explicit decision action and identity.
    Quantity, notional, price/timing conditions, and account type are used only when
    explicitly supplied. Actual fills or later Portfolio state are never used to infer
    missing Owner intent.
    """
    journal = _validated_decision(decision)
    action = journal["decision"]

    if explicit_intent is None:
        return None
    if not isinstance(explicit_intent, Mapping):
        raise DecisionExecutionAdapterError("explicit_intent must be an object or null")
    if action not in EXECUTION_DECISIONS:
        raise DecisionExecutionAdapterError(
            f"decision {action} is not an executable #251 action; do not infer execution intent"
        )
    if journal.get("retrospective_note"):
        raise DecisionExecutionAdapterError(
            "retrospective decision cannot establish ex-ante execution intent"
        )

    raw = deepcopy(dict(explicit_intent))
    forbidden = sorted(_ACTUAL_ONLY_FIELDS.intersection(raw))
    if forbidden:
        raise DecisionExecutionAdapterError(
            f"actual execution fields are not allowed in Owner intent: {forbidden}"
        )

    decision_ref = journal["decision_id"]
    code = journal["security_code"]
    decided_at = journal["decided_at"]

    for field, expected in (
        ("decision_ref", decision_ref),
        ("security_code", code),
        ("action", action),
    ):
        if raw.get(field) is not None and str(raw[field]).strip().upper() != str(expected).strip().upper():
            raise DecisionExecutionAdapterError(f"explicit_intent.{field} conflicts with Decision Journal")

    captured_at = raw.get("captured_at", decided_at)
    if _dt(captured_at, "explicit_intent.captured_at") > _dt(decided_at, "decision.decided_at"):
        raise DecisionExecutionAdapterError("execution intent cannot be captured after decided_at")

    candidate = {
        "decision_ref": decision_ref,
        "security_code": code,
        "action": action,
        "intended_quantity": raw.get("intended_quantity"),
        "intended_notional": raw.get("intended_notional"),
        "price_condition": deepcopy(raw.get("price_condition", {"type": "UNKNOWN"})),
        "timing_condition": deepcopy(raw.get("timing_condition", {"session": "UNKNOWN"})),
        "account_type": raw.get("account_type", "UNKNOWN"),
        "captured_at": captured_at,
        "source": raw.get("source", "DECISION_JOURNAL"),
    }
    if raw.get("execution_intent_id") is not None:
        candidate["execution_intent_id"] = raw["execution_intent_id"]

    try:
        return validate_execution_intent(candidate)
    except ValueError as exc:
        raise DecisionExecutionAdapterError(str(exc)) from exc


def build_risk_preflight_relation(
    decision: Mapping[str, Any],
    risk_preflight: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Attach an explicit pre-decision #233 ref without treating it as Owner intent."""
    journal = _validated_decision(decision)
    if risk_preflight is None:
        return None
    if not isinstance(risk_preflight, Mapping):
        raise DecisionExecutionAdapterError("risk_preflight must be an object or null")

    snapshot = deepcopy(dict(risk_preflight))
    proposed = snapshot.get("proposed_action")
    if not isinstance(proposed, Mapping):
        raise DecisionExecutionAdapterError("risk_preflight.proposed_action is required")

    try:
        ref = decision_journal_ref(snapshot)
    except ValueError as exc:
        raise DecisionExecutionAdapterError(str(exc)) from exc

    if ref["security_code"] != journal["security_code"]:
        raise DecisionExecutionAdapterError("Risk Preflight security_code conflicts with Decision Journal")
    if _dt(ref["captured_at"], "risk_preflight.captured_at") > _dt(
        journal["decided_at"], "decision.decided_at"
    ):
        raise DecisionExecutionAdapterError("Risk Preflight captured after decided_at cannot be attached")

    proposed_action = str(proposed.get("action") or "").strip().upper()
    if journal["decision"] not in EXECUTION_DECISIONS:
        raise DecisionExecutionAdapterError(
            "non-executable decision cannot be related to an execution Risk Preflight"
        )
    if proposed_action != journal["decision"]:
        raise DecisionExecutionAdapterError("Risk Preflight proposed action conflicts with Decision Journal")

    return {
        "type": "DECISION_RISK_PREFLIGHT_RELATION",
        "decision_ref": journal["decision_id"],
        "risk_snapshot_ref": ref["ref"],
        "captured_at": ref["captured_at"],
        "security_code": ref["security_code"],
        "proposed_action": proposed_action,
        "data_status": ref["data_status"],
        "relation": "PRE_DECISION_PREFLIGHT",
    }


def build_decision_execution_context(
    decision: Mapping[str, Any],
    *,
    explicit_intent: Mapping[str, Any] | None = None,
    risk_preflight: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a read-only #133/#233 → #251 relation bundle.

    Missing intent/preflight stays missing. This function does not consult fills,
    transaction history, or current Portfolio state and never creates a trade action.
    """
    journal = _validated_decision(decision)
    intent = build_execution_intent_from_decision(journal, explicit_intent)
    risk = build_risk_preflight_relation(journal, risk_preflight)

    if journal["decision"] not in EXECUTION_DECISIONS:
        intent_status = "NOT_APPLICABLE"
    elif journal.get("retrospective_note"):
        intent_status = "RETROSPECTIVE_NO_EX_ANTE_INTENT"
    elif intent is None:
        intent_status = "NOT_RECORDED"
    else:
        intent_status = "EXPLICIT"

    return {
        "type": "DECISION_EXECUTION_CONTEXT",
        "decision_ref": journal["decision_id"],
        "security_code": journal["security_code"],
        "decision": journal["decision"],
        "decided_at": journal["decided_at"],
        "execution_intent": intent,
        "intent_status": intent_status,
        "risk_preflight_relation": risk,
        "trade_action": None,
    }
