from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from scripts.intraday_subsector_flow import validate_intraday_subsector_flow

_ALLOWED_OPERATORS = {">", ">=", "<", "<=", "==", "!="}
_ALLOWED_FLOW_FIELDS = {
    "observations.intraday_return",
    "observations.benchmark_return",
    "observations.relative_return",
    "observations.breadth",
    "observations.median_constituent_return",
    "observations.turnover_ratio",
    "observations.concentration_top1",
}
_ALLOWED_ACCEL_FIELDS = {
    "delta.intraday_return",
    "delta.relative_return",
    "delta.breadth",
    "delta.median_constituent_return",
    "delta.turnover_ratio",
    "delta.concentration_top1",
}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    return float(value)


def _validate_rule(rule: Any, *, index: int, allowed_fields: set[str]) -> dict[str, Any]:
    if not isinstance(rule, dict):
        raise ValueError(f"rules[{index}] must be an object")
    state = _text(rule.get("state"), f"rules[{index}].state")
    conditions = rule.get("all")
    if not isinstance(conditions, list) or not conditions:
        raise ValueError(f"rules[{index}].all must be a non-empty list")
    normalized: list[dict[str, Any]] = []
    for condition_index, condition in enumerate(conditions):
        if not isinstance(condition, dict):
            raise ValueError(
                f"rules[{index}].all[{condition_index}] must be an object"
            )
        field = _text(
            condition.get("field"), f"rules[{index}].all[{condition_index}].field"
        )
        if field not in allowed_fields:
            raise ValueError(f"unsupported classifier field: {field}")
        operator = _text(
            condition.get("op"), f"rules[{index}].all[{condition_index}].op"
        )
        if operator not in _ALLOWED_OPERATORS:
            raise ValueError(f"unsupported classifier operator: {operator}")
        normalized.append(
            {
                "field": field,
                "op": operator,
                "value": _number(
                    condition.get("value"),
                    f"rules[{index}].all[{condition_index}].value",
                ),
            }
        )
    return {"state": state, "all": normalized}


def validate_threshold_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Validate an explicitly supplied classifier profile.

    The harness intentionally provides no default threshold profile. The caller must
    supply versioned/provenanced rules, keeping investment-significant thresholds
    outside implementation authority.
    """
    if not isinstance(profile, dict):
        raise ValueError("profile must be an object")
    version = _text(profile.get("version"), "version")
    source_or_authority = _text(
        profile.get("source_or_authority"), "source_or_authority"
    )
    rationale = _text(profile.get("rationale"), "rationale")
    created_at = _text(profile.get("created_at"), "created_at")
    try:
        datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("created_at must be ISO-8601") from exc

    flow_rules = profile.get("flow_rules")
    acceleration_rules = profile.get("acceleration_rules")
    if not isinstance(flow_rules, list) or not flow_rules:
        raise ValueError("flow_rules must be a non-empty list")
    if not isinstance(acceleration_rules, list):
        raise ValueError("acceleration_rules must be a list")

    return {
        "version": version,
        "source_or_authority": source_or_authority,
        "rationale": rationale,
        "created_at": created_at,
        "flow_rules": [
            _validate_rule(rule, index=index, allowed_fields=_ALLOWED_FLOW_FIELDS)
            for index, rule in enumerate(flow_rules)
        ],
        "acceleration_rules": [
            _validate_rule(rule, index=index, allowed_fields=_ALLOWED_ACCEL_FIELDS)
            for index, rule in enumerate(acceleration_rules)
        ],
    }


def _read_path(payload: dict[str, Any], path: str) -> float | None:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    if isinstance(current, bool) or not isinstance(current, (int, float)):
        return None
    return float(current)


def _compare(actual: float, operator: str, expected: float) -> bool:
    if operator == ">":
        return actual > expected
    if operator == ">=":
        return actual >= expected
    if operator == "<":
        return actual < expected
    if operator == "<=":
        return actual <= expected
    if operator == "==":
        return actual == expected
    if operator == "!=":
        return actual != expected
    raise ValueError(f"unsupported classifier operator: {operator}")


def _evaluate_rules(payload: dict[str, Any], rules: list[dict[str, Any]]) -> str:
    for rule in rules:
        matched = True
        for condition in rule["all"]:
            actual = _read_path(payload, condition["field"])
            if actual is None or not _compare(actual, condition["op"], condition["value"]):
                matched = False
                break
        if matched:
            return rule["state"]
    return "UNKNOWN"


def classify_flow(
    snapshot: dict[str, Any], threshold_profile: dict[str, Any]
) -> dict[str, Any]:
    validated_snapshot = validate_intraday_subsector_flow(snapshot)
    profile = validate_threshold_profile(threshold_profile)
    if (
        validated_snapshot["freshness"] != "FRESH"
        or validated_snapshot["data_completeness"] != "COMPLETE"
    ):
        state = "UNKNOWN"
        reason = "FAIL_CLOSED_DATA_QUALITY"
    else:
        state = _evaluate_rules(validated_snapshot, profile["flow_rules"])
        reason = "EXPLICIT_PROFILE_EVALUATION"
    return {
        "observed_at": validated_snapshot["observed_at"],
        "flow_state": state,
        "classification_reason": reason,
        "profile_version": profile["version"],
        "profile_source_or_authority": profile["source_or_authority"],
    }


def _snapshot_delta(
    previous: dict[str, Any], current: dict[str, Any]
) -> dict[str, dict[str, float | None]]:
    keys = (
        "intraday_return",
        "relative_return",
        "breadth",
        "median_constituent_return",
        "turnover_ratio",
        "concentration_top1",
    )
    delta: dict[str, float | None] = {}
    for key in keys:
        before = _read_path(previous, f"observations.{key}")
        after = _read_path(current, f"observations.{key}")
        delta[key] = after - before if before is not None and after is not None else None
    return {"delta": delta}


def classify_acceleration(
    previous_snapshot: dict[str, Any],
    current_snapshot: dict[str, Any],
    threshold_profile: dict[str, Any],
) -> dict[str, Any]:
    previous = validate_intraday_subsector_flow(previous_snapshot)
    current = validate_intraday_subsector_flow(current_snapshot)
    profile = validate_threshold_profile(threshold_profile)
    if (
        previous["freshness"] != "FRESH"
        or current["freshness"] != "FRESH"
        or previous["data_completeness"] != "COMPLETE"
        or current["data_completeness"] != "COMPLETE"
    ):
        state = "UNKNOWN"
        reason = "FAIL_CLOSED_DATA_QUALITY"
    elif not profile["acceleration_rules"]:
        state = "UNKNOWN"
        reason = "NO_EXPLICIT_ACCELERATION_RULES"
    else:
        state = _evaluate_rules(
            _snapshot_delta(previous, current), profile["acceleration_rules"]
        )
        reason = "EXPLICIT_PROFILE_EVALUATION"
    return {
        "observed_at": current["observed_at"],
        "acceleration_state": state,
        "classification_reason": reason,
        "profile_version": profile["version"],
        "profile_source_or_authority": profile["source_or_authority"],
    }


def replay_profile(
    history: Iterable[dict[str, Any]], threshold_profile: dict[str, Any]
) -> list[dict[str, Any]]:
    """Replay one explicit profile over historical snapshots in observed_at order."""
    profile = validate_threshold_profile(threshold_profile)
    snapshots = [validate_intraday_subsector_flow(item) for item in history]
    snapshots.sort(
        key=lambda item: datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00"))
    )
    results: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for snapshot in snapshots:
        row = classify_flow(snapshot, profile)
        if previous is None:
            row["acceleration_state"] = "UNKNOWN"
            row["acceleration_reason"] = "NO_PREVIOUS_SNAPSHOT"
        else:
            acceleration = classify_acceleration(previous, snapshot, profile)
            row["acceleration_state"] = acceleration["acceleration_state"]
            row["acceleration_reason"] = acceleration["classification_reason"]
        results.append(row)
        previous = snapshot
    return results


def compare_profiles(
    history: Iterable[dict[str, Any]], profiles: Iterable[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """Return side-by-side replay packets without selecting a winning profile."""
    snapshots = list(history)
    output: dict[str, list[dict[str, Any]]] = {}
    for raw_profile in profiles:
        profile = validate_threshold_profile(raw_profile)
        version = profile["version"]
        if version in output:
            raise ValueError(f"duplicate profile version: {version}")
        output[version] = replay_profile(snapshots, profile)
    return output
