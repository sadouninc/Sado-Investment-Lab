from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from scripts.intraday_subsector_classifier_harness import (
    compare_profiles,
    validate_threshold_profile,
)

_SIGNAL_LABELS = {"POSITIVE", "NEGATIVE", "UNKNOWN"}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _iso(value: Any, field: str) -> str:
    text = _text(value, field)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    return text


def _state_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    states = [_text(item, f"{field}[]") for item in value]
    if len(states) != len(set(states)):
        raise ValueError(f"{field} must not contain duplicates")
    return states


def validate_validation_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Validate explicit evaluation semantics without inventing classifier meaning."""
    if not isinstance(spec, dict):
        raise ValueError("validation spec must be an object")
    positive_states = _state_list(spec.get("positive_states"), "positive_states")
    negative_states = _state_list(spec.get("negative_states"), "negative_states")
    overlap = set(positive_states) & set(negative_states)
    if overlap:
        raise ValueError("positive_states and negative_states must not overlap")
    return {
        "version": _text(spec.get("version"), "version"),
        "source_or_authority": _text(
            spec.get("source_or_authority"), "source_or_authority"
        ),
        "rationale": _text(spec.get("rationale"), "rationale"),
        "created_at": _iso(spec.get("created_at"), "created_at"),
        "positive_states": positive_states,
        "negative_states": negative_states,
        "target_transition_states": _state_list(
            spec.get("target_transition_states"), "target_transition_states"
        ),
    }


def validate_validation_cases(cases: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    case_ids: set[str] = set()
    row_keys: set[str] = set()
    for index, raw in enumerate(cases):
        if not isinstance(raw, dict):
            raise ValueError(f"cases[{index}] must be an object")
        case_id = _text(raw.get("case_id"), f"cases[{index}].case_id")
        observed_at = _iso(raw.get("observed_at"), f"cases[{index}].observed_at")
        series_key = raw.get("series_key")
        if series_key is not None:
            series_key = _text(series_key, f"cases[{index}].series_key")
            row_key = f"{series_key}:{observed_at}"
        else:
            row_key = observed_at

        if case_id in case_ids:
            raise ValueError(f"duplicate case_id: {case_id}")
        if row_key in row_keys:
            raise ValueError(f"duplicate case row_key or observed_at: {row_key}")
        case_ids.add(case_id)
        row_keys.add(row_key)
        expected_signal = _text(
            raw.get("expected_signal"), f"cases[{index}].expected_signal"
        ).upper()
        if expected_signal not in _SIGNAL_LABELS:
            raise ValueError(f"unsupported expected_signal: {expected_signal}")
        case_dict = {
            "case_id": case_id,
            "observed_at": observed_at,
            "label_source_or_authority": _text(
                raw.get("label_source_or_authority"),
                f"cases[{index}].label_source_or_authority",
            ),
            "rationale": _text(raw.get("rationale"), f"cases[{index}].rationale"),
            "expected_signal": expected_signal,
            "accepted_flow_states": _state_list(
                raw.get("accepted_flow_states"),
                f"cases[{index}].accepted_flow_states",
            ),
        }
        if series_key is not None:
            case_dict["series_key"] = series_key
            case_dict["row_key"] = row_key
        normalized.append(case_dict)
    return normalized


def _output_signal(state: str, spec: dict[str, Any]) -> str:
    if state == "UNKNOWN":
        return "UNKNOWN"
    if state in spec["positive_states"]:
        return "POSITIVE"
    if state in spec["negative_states"]:
        return "NEGATIVE"
    return "UNKNOWN"


def _first_transition_at(
    replay: list[dict[str, Any]], target_states: list[str]
) -> str | None:
    targets = set(target_states)
    for row in replay:
        if row.get("flow_state") in targets:
            return str(row.get("observed_at"))
    return None


def score_profile_replay(
    replay: list[dict[str, Any]],
    cases: Iterable[dict[str, Any]],
    validation_spec: dict[str, Any],
) -> dict[str, Any]:
    """Score one replay against explicit labels; UNKNOWN never becomes negative."""
    spec = validate_validation_spec(validation_spec)
    validated_cases = validate_validation_cases(cases)
    rows_by_key: dict[str, dict[str, Any]] = {}
    rows_by_time: dict[str, dict[str, Any]] = {}
    ambiguous_times: set[str] = set()

    for row in replay:
        observed_at = _iso(row.get("observed_at"), "replay.observed_at")
        row_key = row.get("row_key")
        if row_key is not None:
            rk = str(row_key)
            if rk in rows_by_key:
                raise ValueError(f"duplicate replay row_key: {rk}")
            rows_by_key[rk] = row

        if observed_at in rows_by_time:
            ambiguous_times.add(observed_at)
        else:
            rows_by_time[observed_at] = row

    evaluated = 0
    missing = 0
    accepted_match = 0
    accepted_mismatch = 0
    unknown_output = 0
    false_positive_proxy = 0
    false_negative_proxy = 0

    for case in validated_cases:
        if "row_key" in case:
            row = rows_by_key.get(case["row_key"])
        elif "series_key" in case:
            row = rows_by_key.get(f"{case['series_key']}:{case['observed_at']}")
        else:
            if case["observed_at"] in ambiguous_times:
                raise ValueError(
                    f"ambiguous case observed_at without series_key: {case['observed_at']}"
                )
            row = rows_by_time.get(case["observed_at"])

        if row is None:
            missing += 1
            continue
        evaluated += 1
        state = _text(row.get("flow_state"), "replay.flow_state")
        output_signal = _output_signal(state, spec)
        if output_signal == "UNKNOWN":
            unknown_output += 1
        if state in case["accepted_flow_states"]:
            accepted_match += 1
        else:
            accepted_mismatch += 1
        if case["expected_signal"] == "NEGATIVE" and output_signal == "POSITIVE":
            false_positive_proxy += 1
        elif case["expected_signal"] == "POSITIVE" and output_signal == "NEGATIVE":
            false_negative_proxy += 1

    return {
        "evaluated_case_count": evaluated,
        "missing_replay_case_count": missing,
        "accepted_match_count": accepted_match,
        "accepted_mismatch_count": accepted_mismatch,
        "unknown_output_count": unknown_output,
        "unknown_output_rate": unknown_output / evaluated if evaluated else None,
        "false_positive_proxy_count": false_positive_proxy,
        "false_negative_proxy_count": false_negative_proxy,
        "first_target_transition_at": _first_transition_at(
            replay, spec["target_transition_states"]
        ),
    }


def build_candidate_validation_packet(
    *,
    history: Iterable[dict[str, Any]],
    profiles: Iterable[dict[str, Any]],
    cases: Iterable[dict[str, Any]],
    validation_spec: dict[str, Any],
) -> dict[str, Any]:
    """Build side-by-side evidence only; deliberately emits no winner/recommendation."""
    spec = validate_validation_spec(validation_spec)
    case_list = validate_validation_cases(cases)
    profile_list = [validate_threshold_profile(profile) for profile in profiles]
    comparison = compare_profiles(history, profile_list)
    candidates: dict[str, dict[str, Any]] = {}
    for profile in profile_list:
        version = profile["version"]
        candidates[version] = {
            "profile_version": version,
            "profile_source_or_authority": profile["source_or_authority"],
            "metrics": score_profile_replay(comparison[version], case_list, spec),
            "replay": comparison[version],
        }
    return {
        "validation_spec_version": spec["version"],
        "validation_spec_source_or_authority": spec["source_or_authority"],
        "case_count": len(case_list),
        "candidates": candidates,
    }
