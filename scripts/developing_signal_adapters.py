from __future__ import annotations

from copy import deepcopy
from typing import Any

from scripts.developing_signal_registry import validate_signal


class DevelopingSignalAdapterError(ValueError):
    pass


_ALLOWED_SENSORS = {"ASAHI", "REI", "POLICY", "MONEY_FLOW"}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DevelopingSignalAdapterError(f"{field} must be a non-empty string")
    return value.strip()


def _list(value: Any, field: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise DevelopingSignalAdapterError(f"{field} must be a list")
    return deepcopy(value)


def _base_signal(payload: dict[str, Any], *, sensor: str, signal_type: str | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise DevelopingSignalAdapterError("payload must be an object")
    sensor = sensor.upper()
    if sensor not in _ALLOWED_SENSORS:
        raise DevelopingSignalAdapterError(f"unsupported sensor: {sensor}")

    observed_at = _text(payload.get("observed_at"), "observed_at")
    signal = {
        "signal_key": _text(payload.get("signal_key"), "signal_key"),
        "title": _text(payload.get("title"), "title"),
        "signal_type": signal_type or _text(payload.get("signal_type"), "signal_type").upper(),
        "status": "WATCHING",
        "direction": str(payload.get("direction") or "UNKNOWN").upper(),
        "first_observed_at": observed_at,
        "last_observed_at": observed_at,
        "created_by": sensor,
        "summary": _text(payload.get("summary"), "summary"),
        "why_it_may_matter": _text(payload.get("why_it_may_matter"), "why_it_may_matter"),
        "source_refs": _list(payload.get("source_refs"), "source_refs"),
        "related_entities": _list(payload.get("related_entities"), "related_entities"),
        "related_hypothesis_refs": _list(payload.get("related_hypothesis_refs"), "related_hypothesis_refs"),
        "strengthening_conditions": _list(payload.get("strengthening_conditions"), "strengthening_conditions"),
        "invalidation_conditions": _list(payload.get("invalidation_conditions"), "invalidation_conditions"),
        "promotion_target_candidates": _list(payload.get("promotion_target_candidates"), "promotion_target_candidates"),
        "next_checkpoint": payload.get("next_checkpoint"),
        "expires_at": payload.get("expires_at"),
        "checkpoint_reason": payload.get("checkpoint_reason"),
        "observations": [],
        "adapter_metadata": {
            "sensor": sensor,
            "decision_scope": "WATCH_ONLY",
            "trade_action": None,
            "daily_review_trigger": False,
        },
    }
    return validate_signal(signal)


def adapt_asahi_watch(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert a persistent Daily Briefing observation into a WATCH signal.

    One-day general news must not be registered: the caller must explicitly assert
    that multi-day follow-up has value through `follow_up_required=true`.
    """
    if payload.get("follow_up_required") is not True:
        raise DevelopingSignalAdapterError("ASAHI WATCH requires follow_up_required=true")
    return _base_signal(payload, sensor="ASAHI")


def adapt_rei_watch(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert a Key Person / strategy-change observation into a WATCH signal."""
    if payload.get("strategic_change_candidate") is not True:
        raise DevelopingSignalAdapterError("REI WATCH requires strategic_change_candidate=true")
    return _base_signal(payload, sensor="REI", signal_type="KEY_PERSON")


def adapt_policy_cross_domain(payload: dict[str, Any]) -> dict[str, Any]:
    """Promote only cross-domain policy signals; never duplicate Policy Raw Log."""
    if payload.get("cross_domain") is not True:
        raise DevelopingSignalAdapterError("POLICY adapter requires cross_domain=true")
    raw_ref = _text(payload.get("policy_raw_ref"), "policy_raw_ref")
    signal = _base_signal(payload, sensor="POLICY", signal_type="POLICY")
    signal["adapter_metadata"].update(
        {
            "policy_raw_ref": raw_ref,
            "raw_payload_copied": False,
        }
    )
    return signal


def adapt_money_flow(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert #112 WARMING/INFLOW output into a WATCH signal.

    COLD/HOT/OVERHEATED are intentionally not eligible for Developing Signal
    registration because #112 uses WARMING/INFLOW as the selection window.
    """
    state = _text(payload.get("money_flow_state"), "money_flow_state").upper()
    if state not in {"WARMING", "INFLOW"}:
        raise DevelopingSignalAdapterError("MONEY_FLOW WATCH requires WARMING or INFLOW")
    if payload.get("selection_signal") is not True:
        raise DevelopingSignalAdapterError("MONEY_FLOW WATCH requires selection_signal=true")
    signal_type = _text(payload.get("signal_type"), "signal_type").upper()
    if signal_type not in {"THEME", "MARKET"}:
        raise DevelopingSignalAdapterError("MONEY_FLOW signal_type must be THEME or MARKET")
    signal = _base_signal(payload, sensor="MONEY_FLOW", signal_type=signal_type)
    signal["adapter_metadata"].update(
        {
            "money_flow_state": state,
            "flow_score": payload.get("flow_score"),
            "selection_signal": True,
        }
    )
    return signal


def adapt_team_signal(sensor: str, payload: dict[str, Any]) -> dict[str, Any]:
    sensor = _text(sensor, "sensor").upper()
    adapters = {
        "ASAHI": adapt_asahi_watch,
        "REI": adapt_rei_watch,
        "POLICY": adapt_policy_cross_domain,
        "MONEY_FLOW": adapt_money_flow,
    }
    try:
        return adapters[sensor](payload)
    except KeyError as exc:
        raise DevelopingSignalAdapterError(f"unsupported sensor: {sensor}") from exc
