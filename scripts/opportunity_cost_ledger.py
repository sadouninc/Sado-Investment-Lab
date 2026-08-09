from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from typing import Any

ACTIONS = {"BUY", "ADD", "HOLD", "REDUCE", "SELL", "PASS", "CASH", "DO_NOTHING"}
SOURCES = {"CANDIDATE_SELECTOR", "OWNER_NAMED", "CURRENT_HOLDING", "SYSTEM"}
DATA_STATUSES = {"CURRENT", "STALE", "MISSING", "UNKNOWN"}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _timestamp(value: Any, field: str) -> str:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include timezone")
    return text


def _action(value: Any, field: str) -> str:
    action = _text(value, field).upper()
    if action not in ACTIONS:
        raise ValueError(f"unsupported {field}: {action}")
    return action


def _security_code(value: Any, field: str, *, allow_cash: bool = False) -> str | None:
    if value is None and allow_cash:
        return None
    code = _text(value, field)
    if not code.isdigit() or len(code) != 4:
        raise ValueError(f"{field} must be a 4-digit security code")
    return code


def deterministic_opportunity_set_id(decision_ref: str, captured_at: str) -> str:
    decision = _text(decision_ref, "decision_ref")
    captured = _timestamp(captured_at, "captured_at")
    digest = hashlib.sha256(f"{decision}|{captured}".encode("utf-8")).hexdigest()[:16]
    return f"opp:{digest}"


def deterministic_alternative_id(alternative: dict[str, Any]) -> str:
    action = _action(alternative.get("action"), "alternative.action")
    code = alternative.get("security_code")
    if action in {"CASH", "DO_NOTHING"}:
        if code not in (None, ""):
            raise ValueError("CASH/DO_NOTHING alternative must not have security_code")
        identity = action
    else:
        identity = f"{_security_code(code, 'alternative.security_code')}:{action}"
    return "alt:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]


def validate_alternative(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("alternative must be an object")
    item = deepcopy(value)
    action = _action(item.get("action"), "alternative.action")
    source = _text(item.get("source"), "alternative.source").upper()
    if source not in SOURCES:
        raise ValueError(f"unsupported alternative.source: {source}")
    if action in {"CASH", "DO_NOTHING"}:
        if source != "SYSTEM":
            raise ValueError("CASH/DO_NOTHING alternative source must be SYSTEM")
        if item.get("security_code") not in (None, ""):
            raise ValueError("CASH/DO_NOTHING alternative must not have security_code")
        item["security_code"] = None
    else:
        item["security_code"] = _security_code(item.get("security_code"), "alternative.security_code")
    item["action"] = action
    item["source"] = source
    item["why_feasible"] = _text(item.get("why_feasible"), "alternative.why_feasible")
    why_not = item.get("why_not_chosen")
    if why_not is not None:
        item["why_not_chosen"] = _text(why_not, "alternative.why_not_chosen")
    status = _text(item.get("data_status", "UNKNOWN"), "alternative.data_status").upper()
    if status not in DATA_STATUSES:
        raise ValueError(f"unsupported alternative.data_status: {status}")
    item["data_status"] = status
    rank = item.get("rank_at_decision")
    if rank is not None and (isinstance(rank, bool) or not isinstance(rank, int) or rank < 1):
        raise ValueError("rank_at_decision must be a positive integer or null")
    if source == "CANDIDATE_SELECTOR":
        _text(item.get("candidate_ref"), "alternative.candidate_ref")
        if rank is None:
            raise ValueError("Candidate alternative requires rank_at_decision")
    elif rank is not None:
        raise ValueError("rank_at_decision is only valid for CANDIDATE_SELECTOR")
    for field in ("candidate_ref", "research_ref", "valuation_ref", "hypothesis_ref"):
        if item.get(field) is not None:
            item[field] = _text(item[field], f"alternative.{field}")
    expected_id = deterministic_alternative_id(item)
    if item.get("alternative_id") not in (None, expected_id):
        raise ValueError("alternative_id does not match deterministic identity")
    item["alternative_id"] = expected_id
    return item


def validate_opportunity_set(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("opportunity set must be an object")
    result = deepcopy(value)
    decision_ref = _text(result.get("decision_ref"), "decision_ref")
    captured_at = _timestamp(result.get("captured_at"), "captured_at")
    result["actor"] = _text(result.get("actor"), "actor")
    result["selection_rule"] = _text(result.get("selection_rule"), "selection_rule")
    result["snapshot_freshness"] = _text(result.get("snapshot_freshness"), "snapshot_freshness")

    chosen = result.get("chosen_action")
    if not isinstance(chosen, dict):
        raise ValueError("chosen_action must be an object")
    chosen = deepcopy(chosen)
    chosen["action"] = _action(chosen.get("action"), "chosen_action.action")
    if chosen["action"] in {"CASH", "DO_NOTHING"}:
        if chosen.get("security_code") not in (None, ""):
            raise ValueError("CASH/DO_NOTHING chosen action must not have security_code")
        chosen["security_code"] = None
    else:
        chosen["security_code"] = _security_code(chosen.get("security_code"), "chosen_action.security_code")
    if chosen.get("decision_ref") is not None and _text(chosen["decision_ref"], "chosen_action.decision_ref") != decision_ref:
        raise ValueError("chosen_action.decision_ref must match opportunity set decision_ref")
    chosen["decision_ref"] = decision_ref
    result["chosen_action"] = chosen

    capital = result.get("capital_context", {})
    if not isinstance(capital, dict):
        raise ValueError("capital_context must be an object")
    result["capital_context"] = deepcopy(capital)

    alternatives = result.get("alternatives")
    if not isinstance(alternatives, list) or not alternatives:
        raise ValueError("alternatives must be a non-empty list")
    validated = [validate_alternative(item) for item in alternatives]
    ids = [item["alternative_id"] for item in validated]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate alternatives are not allowed")
    chosen_identity = (chosen.get("security_code"), chosen["action"])
    for item in validated:
        if (item.get("security_code"), item["action"]) == chosen_identity:
            raise ValueError("chosen action must not be duplicated as an alternative")
    result["alternatives"] = sorted(validated, key=lambda item: item["alternative_id"])

    expected_id = deterministic_opportunity_set_id(decision_ref, captured_at)
    if result.get("opportunity_set_id") not in (None, expected_id):
        raise ValueError("opportunity_set_id does not match deterministic identity")
    result["opportunity_set_id"] = expected_id
    return result


def capture_opportunity_set(value: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    candidate = validate_opportunity_set(value)
    if existing is None:
        return candidate
    current = validate_opportunity_set(existing)
    if current["opportunity_set_id"] != candidate["opportunity_set_id"]:
        raise ValueError("existing snapshot has a different identity")
    if current != candidate:
        raise ValueError("immutable opportunity snapshot cannot be rewritten")
    return current


def dumps(value: dict[str, Any]) -> str:
    return json.dumps(validate_opportunity_set(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
