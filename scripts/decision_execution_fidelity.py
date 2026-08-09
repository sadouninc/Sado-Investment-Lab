from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from datetime import datetime
from typing import Any

ACTIONS = {"BUY", "ADD", "REDUCE", "SELL"}
ACCOUNT_TYPES = {"CASH", "MARGIN", "UNKNOWN"}
INTENT_SOURCES = {"OWNER_EXPLICIT", "DECISION_JOURNAL", "UNKNOWN"}
PRICE_TYPES = {"MARKET", "LIMIT", "RANGE", "NONE", "UNKNOWN"}
SESSIONS = {"OPEN", "AM", "PM", "CLOSE", "NONE", "UNKNOWN"}
EXECUTION_STATUS = {"NOT_EXECUTED", "PARTIAL", "EXECUTED", "UNKNOWN"}
SOURCE_STATUS = {"CURRENT", "STALE", "UNAVAILABLE", "UNKNOWN"}
FIDELITY_RESULTS = {
    "MATCH",
    "PARTIAL_MATCH",
    "MISMATCH",
    "NOT_EXECUTED",
    "NOT_JUDGABLE",
    "UNKNOWN",
}
DEVIATIONS = {
    "ACTION_MISMATCH",
    "QUANTITY_MISMATCH",
    "PRICE_CONDITION_MISMATCH",
    "TIMING_CONDITION_MISMATCH",
    "ACCOUNT_TYPE_MISMATCH",
    "PARTIAL_FILL",
    "NOT_EXECUTED",
    "UNJOURNALED_EXECUTION",
    "UNKNOWN",
}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _dt(value: Any, field: str) -> datetime:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include timezone")
    return parsed


def _enum(value: Any, field: str, allowed: set[str]) -> str:
    normalized = _text(value, field).upper()
    if normalized not in allowed:
        raise ValueError(f"unsupported {field}: {normalized}")
    return normalized


def _positive_int_or_none(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer or null")
    return value


def _positive_number_or_none(value: Any, field: str) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a positive finite number or null")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field} must be a positive finite number or null")
    return value


def _hash_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]
    return f"{prefix}:{digest}"


def deterministic_intent_id(decision_ref: str, security_code: str, captured_at: str) -> str:
    decision = _text(decision_ref, "decision_ref")
    code = _text(security_code, "security_code")
    at = _dt(captured_at, "captured_at").isoformat()
    return _hash_id("exec-intent", decision, code, at)


def deterministic_execution_id(decision_ref: str, security_code: str, captured_at: str) -> str:
    decision = _text(decision_ref, "decision_ref")
    code = _text(security_code, "security_code")
    at = _dt(captured_at, "captured_at").isoformat()
    return _hash_id("exec", decision, code, at)


def _validate_price_condition(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("price_condition must be an object")
    out = deepcopy(value)
    kind = _enum(out.get("type"), "price_condition.type", PRICE_TYPES)
    price = _positive_number_or_none(out.get("value"), "price_condition.value")
    lower = _positive_number_or_none(out.get("lower"), "price_condition.lower")
    upper = _positive_number_or_none(out.get("upper"), "price_condition.upper")
    if kind == "LIMIT":
        if price is None or lower is not None or upper is not None:
            raise ValueError("LIMIT requires value only")
    elif kind == "RANGE":
        if lower is None or upper is None or price is not None:
            raise ValueError("RANGE requires lower and upper only")
        if lower > upper:
            raise ValueError("price_condition.lower must be <= upper")
    elif any(item is not None for item in (price, lower, upper)):
        raise ValueError(f"{kind} price condition must not contain numeric bounds")
    out.update({"type": kind, "value": price, "lower": lower, "upper": upper})
    return out


def _validate_timing_condition(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("timing_condition must be an object")
    out = deepcopy(value)
    execute_by = out.get("execute_by")
    if execute_by is not None:
        _dt(execute_by, "timing_condition.execute_by")
    session = _enum(out.get("session", "UNKNOWN"), "timing_condition.session", SESSIONS)
    out.update({"execute_by": execute_by, "session": session})
    return out


def validate_execution_intent(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("execution intent must be an object")
    out = deepcopy(record)
    decision_ref = _text(out.get("decision_ref"), "decision_ref")
    code = _text(out.get("security_code"), "security_code")
    captured_at = _dt(out.get("captured_at"), "captured_at").isoformat()
    action = _enum(out.get("action"), "action", ACTIONS)
    quantity = _positive_int_or_none(out.get("intended_quantity"), "intended_quantity")
    notional = _positive_number_or_none(out.get("intended_notional"), "intended_notional")
    price_condition = _validate_price_condition(out.get("price_condition", {"type": "UNKNOWN"}))
    timing_condition = _validate_timing_condition(out.get("timing_condition", {"session": "UNKNOWN"}))
    account_type = _enum(out.get("account_type", "UNKNOWN"), "account_type", ACCOUNT_TYPES)
    source = _enum(out.get("source", "UNKNOWN"), "source", INTENT_SOURCES)
    expected_id = deterministic_intent_id(decision_ref, code, captured_at)
    if out.get("execution_intent_id") not in (None, expected_id):
        raise ValueError("execution_intent_id does not match deterministic identity")
    out.update(
        {
            "execution_intent_id": expected_id,
            "decision_ref": decision_ref,
            "security_code": code,
            "captured_at": captured_at,
            "action": action,
            "intended_quantity": quantity,
            "intended_notional": notional,
            "price_condition": price_condition,
            "timing_condition": timing_condition,
            "account_type": account_type,
            "source": source,
        }
    )
    return out


def _validate_fill(fill: Any, index: int, captured_at: datetime) -> dict[str, Any]:
    if not isinstance(fill, dict):
        raise ValueError(f"fills[{index}] must be an object")
    out = deepcopy(fill)
    executed_at = _dt(out.get("executed_at"), f"fills[{index}].executed_at")
    if executed_at > captured_at:
        raise ValueError("fill cannot occur after snapshot captured_at")
    side = _enum(out.get("side"), f"fills[{index}].side", {"BUY", "SELL"})
    quantity = _positive_int_or_none(out.get("quantity"), f"fills[{index}].quantity")
    price = _positive_number_or_none(out.get("price"), f"fills[{index}].price")
    if quantity is None or price is None:
        raise ValueError("fill quantity and price are required")
    account_type = _enum(out.get("account_type", "UNKNOWN"), f"fills[{index}].account_type", ACCOUNT_TYPES)
    source_ref = _text(out.get("source_ref"), f"fills[{index}].source_ref")
    session = _enum(out.get("session", "UNKNOWN"), f"fills[{index}].session", SESSIONS)
    out.update(
        {
            "executed_at": executed_at.isoformat(),
            "side": side,
            "quantity": quantity,
            "price": price,
            "account_type": account_type,
            "source_ref": source_ref,
            "session": session,
        }
    )
    return out


def validate_actual_execution(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("actual execution snapshot must be an object")
    out = deepcopy(record)
    decision_ref = _text(out.get("decision_ref"), "decision_ref")
    code = _text(out.get("security_code"), "security_code")
    captured_dt = _dt(out.get("captured_at"), "captured_at")
    captured_at = captured_dt.isoformat()
    status = _enum(out.get("execution_status"), "execution_status", EXECUTION_STATUS)
    source_status = _enum(out.get("source_status", "UNKNOWN"), "source_status", SOURCE_STATUS)
    actual_action = _enum(out.get("actual_action", "UNKNOWN"), "actual_action", ACTIONS | {"UNKNOWN"})
    fills_value = out.get("fills", [])
    if not isinstance(fills_value, list):
        raise ValueError("fills must be an array")
    fills = [_validate_fill(fill, index, captured_dt) for index, fill in enumerate(fills_value)]
    if source_status in {"CURRENT", "STALE"}:
        if status in {"PARTIAL", "EXECUTED"} and not fills:
            raise ValueError(f"{status} requires at least one confirmed fill")
        if status == "NOT_EXECUTED" and fills:
            raise ValueError("NOT_EXECUTED cannot contain fills")
    expected_id = deterministic_execution_id(decision_ref, code, captured_at)
    if out.get("execution_snapshot_id") not in (None, expected_id):
        raise ValueError("execution_snapshot_id does not match deterministic identity")
    out.update(
        {
            "execution_snapshot_id": expected_id,
            "decision_ref": decision_ref,
            "security_code": code,
            "captured_at": captured_at,
            "execution_status": status,
            "source_status": source_status,
            "actual_action": actual_action,
            "fills": fills,
        }
    )
    return out


def _capture(validated: dict[str, Any], existing: dict[str, Any] | None, validator) -> dict[str, Any]:
    if existing is None:
        return validated
    prior = validator(existing)
    if prior != validated:
        raise ValueError("immutable execution record conflict")
    return prior


def capture_execution_intent(record: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    return _capture(validate_execution_intent(record), existing, validate_execution_intent)


def capture_actual_execution(record: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    return _capture(validate_actual_execution(record), existing, validate_actual_execution)


def _price_fidelity(intent: dict[str, Any], actual: dict[str, Any]) -> str:
    condition = intent["price_condition"]
    kind = condition["type"]
    if kind in {"NONE", "UNKNOWN", "MARKET"}:
        return "NOT_JUDGABLE"
    prices = [fill["price"] for fill in actual["fills"]]
    if not prices:
        return "NOT_JUDGABLE"
    if kind == "RANGE":
        matched = all(condition["lower"] <= price <= condition["upper"] for price in prices)
    elif intent["action"] in {"BUY", "ADD"}:
        matched = all(price <= condition["value"] for price in prices)
    else:
        matched = all(price >= condition["value"] for price in prices)
    return "MATCH" if matched else "MISMATCH"


def _timing_fidelity(intent: dict[str, Any], actual: dict[str, Any]) -> str:
    condition = intent["timing_condition"]
    checks: list[bool] = []
    if condition["execute_by"] is not None:
        deadline = _dt(condition["execute_by"], "timing_condition.execute_by")
        checks.append(all(_dt(fill["executed_at"], "fill.executed_at") <= deadline for fill in actual["fills"]))
    if condition["session"] not in {"NONE", "UNKNOWN"}:
        sessions = [fill["session"] for fill in actual["fills"]]
        if any(session == "UNKNOWN" for session in sessions):
            if not checks:
                return "NOT_JUDGABLE"
        else:
            checks.append(all(session == condition["session"] for session in sessions))
    if not checks:
        return "NOT_JUDGABLE"
    return "MATCH" if all(checks) else "MISMATCH"


def _account_fidelity(intent: dict[str, Any], actual: dict[str, Any]) -> str:
    expected = intent["account_type"]
    if expected == "UNKNOWN":
        return "NOT_JUDGABLE"
    accounts = [fill["account_type"] for fill in actual["fills"]]
    if not accounts or any(account == "UNKNOWN" for account in accounts):
        return "NOT_JUDGABLE"
    return "MATCH" if all(account == expected for account in accounts) else "MISMATCH"


def compare_execution(intent_record: dict[str, Any] | None, actual_record: dict[str, Any]) -> dict[str, Any]:
    if intent_record is None:
        raise ValueError("execution intent is required; do not infer Owner intent from actual fills")
    intent = validate_execution_intent(intent_record)
    actual = validate_actual_execution(actual_record)
    if intent["decision_ref"] != actual["decision_ref"] or intent["security_code"] != actual["security_code"]:
        raise ValueError("intent and actual execution identity mismatch")

    dimensions = {
        "action": "NOT_JUDGABLE",
        "quantity": "NOT_JUDGABLE",
        "price": "NOT_JUDGABLE",
        "timing": "NOT_JUDGABLE",
        "account": "NOT_JUDGABLE",
        "completion": "UNKNOWN",
    }
    deviations: list[str] = []

    if actual["source_status"] in {"UNAVAILABLE", "UNKNOWN"}:
        dimensions = {key: "UNKNOWN" for key in dimensions}
        return {
            "decision_ref": intent["decision_ref"],
            "execution_intent_id": intent["execution_intent_id"],
            "execution_snapshot_id": actual["execution_snapshot_id"],
            "overall": "UNKNOWN",
            "dimensions": dimensions,
            "deviations": ["UNKNOWN"],
        }

    if actual["execution_status"] == "UNKNOWN":
        dimensions = {key: "UNKNOWN" for key in dimensions}
        return {
            "decision_ref": intent["decision_ref"],
            "execution_intent_id": intent["execution_intent_id"],
            "execution_snapshot_id": actual["execution_snapshot_id"],
            "overall": "UNKNOWN",
            "dimensions": dimensions,
            "deviations": ["UNKNOWN"],
        }

    if actual["execution_status"] == "NOT_EXECUTED":
        dimensions["completion"] = "NOT_EXECUTED"
        return {
            "decision_ref": intent["decision_ref"],
            "execution_intent_id": intent["execution_intent_id"],
            "execution_snapshot_id": actual["execution_snapshot_id"],
            "overall": "NOT_EXECUTED",
            "dimensions": dimensions,
            "deviations": ["NOT_EXECUTED"],
        }

    if actual["actual_action"] != "UNKNOWN":
        dimensions["action"] = "MATCH" if actual["actual_action"] == intent["action"] else "MISMATCH"
        if dimensions["action"] == "MISMATCH":
            deviations.append("ACTION_MISMATCH")

    if intent["intended_quantity"] is not None:
        actual_quantity = sum(fill["quantity"] for fill in actual["fills"])
        dimensions["quantity"] = "MATCH" if actual_quantity == intent["intended_quantity"] else "MISMATCH"
        if dimensions["quantity"] == "MISMATCH":
            deviations.append("QUANTITY_MISMATCH")

    dimensions["price"] = _price_fidelity(intent, actual)
    if dimensions["price"] == "MISMATCH":
        deviations.append("PRICE_CONDITION_MISMATCH")

    dimensions["timing"] = _timing_fidelity(intent, actual)
    if dimensions["timing"] == "MISMATCH":
        deviations.append("TIMING_CONDITION_MISMATCH")

    dimensions["account"] = _account_fidelity(intent, actual)
    if dimensions["account"] == "MISMATCH":
        deviations.append("ACCOUNT_TYPE_MISMATCH")

    if actual["execution_status"] == "PARTIAL":
        dimensions["completion"] = "PARTIAL_MATCH"
        deviations.append("PARTIAL_FILL")
    else:
        dimensions["completion"] = "MATCH"

    if any(value == "MISMATCH" for value in dimensions.values()):
        overall = "MISMATCH"
    elif actual["execution_status"] == "PARTIAL":
        overall = "PARTIAL_MATCH"
    elif any(value == "MATCH" for value in dimensions.values()):
        overall = "MATCH"
    else:
        overall = "NOT_JUDGABLE"

    return {
        "decision_ref": intent["decision_ref"],
        "execution_intent_id": intent["execution_intent_id"],
        "execution_snapshot_id": actual["execution_snapshot_id"],
        "overall": overall,
        "dimensions": dimensions,
        "deviations": deviations,
    }


def classify_unjournaled_execution(actual_record: dict[str, Any]) -> dict[str, Any]:
    actual = validate_actual_execution(actual_record)
    return {
        "execution_snapshot_id": actual["execution_snapshot_id"],
        "decision_ref": actual["decision_ref"],
        "deviation": "UNJOURNALED_EXECUTION",
        "intent_inferred": False,
    }


def dumps(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
