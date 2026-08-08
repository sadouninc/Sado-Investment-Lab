from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

STATES = ("COLD", "WARMING", "INFLOW", "HOT", "OVERHEATED")
AXES = ("relative_strength", "activity", "breadth", "heat", "acceleration")


class MoneyFlowDetectorError(ValueError):
    pass


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if tuple(config.get("required_axes") or []) != AXES:
        raise MoneyFlowDetectorError("required_axes must match detector axes")
    weights = config.get("weights") or {}
    if set(weights) != {"relative_strength", "activity", "breadth", "acceleration"}:
        raise MoneyFlowDetectorError("weights must define non-heat signal axes")
    if sum(float(v) for v in weights.values()) <= 0:
        raise MoneyFlowDetectorError("weights must have positive total")
    return config


def _score(value: Any, key: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or not 0 <= value <= 100:
        raise MoneyFlowDetectorError(f"{key} must be null or within 0..100")
    return float(value)


def normalize_scores(scores: dict[str, Any]) -> dict[str, float | None]:
    if not isinstance(scores, dict):
        raise MoneyFlowDetectorError("scores must be an object")
    unexpected = set(scores) - set(AXES)
    if unexpected:
        raise MoneyFlowDetectorError(f"unsupported score axes: {sorted(unexpected)}")
    return {key: _score(scores.get(key), key) for key in AXES}


def flow_score(scores: dict[str, float | None], weights: dict[str, float]) -> float | None:
    available = [key for key in weights if scores.get(key) is not None and float(weights[key]) > 0]
    if not available:
        return None
    total_weight = sum(float(weights[key]) for key in available)
    return round(sum(float(scores[key]) * float(weights[key]) for key in available) / total_weight, 2)


def data_completeness(scores: dict[str, float | None], minimum_non_null_axes: int) -> tuple[str, str | None]:
    count = sum(value is not None for value in scores.values())
    if count == len(AXES):
        return "OK", None
    if count >= minimum_non_null_axes:
        return "PARTIAL", f"{len(AXES) - count} score axis missing"
    return "INSUFFICIENT", f"only {count}/{len(AXES)} score axes available"


def target_state(scores: dict[str, float | None], config: dict[str, Any]) -> str:
    completeness, _ = data_completeness(scores, int(config["minimum_non_null_axes"]))
    if completeness == "INSUFFICIENT":
        return "COLD"
    total = flow_score(scores, config["weights"])
    heat = scores.get("heat")
    thresholds = config["thresholds"]
    if heat is not None and heat >= float(thresholds["overheated_heat"]):
        return "OVERHEATED"
    if total is not None and total >= float(thresholds["hot_score"]):
        return "HOT"
    if total is not None and total >= float(thresholds["inflow_score"]) and (heat is None or heat <= float(thresholds["max_heat_for_inflow"])):
        return "INFLOW"
    if total is not None and total >= float(thresholds["warming_score"]) and (heat is None or heat <= float(thresholds["max_heat_for_warming"])):
        return "WARMING"
    return "COLD"


def _rank(state: str) -> int:
    if state not in STATES:
        raise MoneyFlowDetectorError(f"unsupported state: {state}")
    return STATES.index(state)


def apply_hysteresis(*, previous_state: str, target: str, prior_target: str | None, target_streak: int, config: dict[str, Any]) -> tuple[str, int]:
    if previous_state not in STATES:
        raise MoneyFlowDetectorError(f"unsupported previous_state: {previous_state}")
    streak = target_streak + 1 if prior_target == target else 1
    if target == previous_state:
        return previous_state, streak
    needed = int(config["hysteresis"]["promote_days"] if _rank(target) > _rank(previous_state) else config["hysteresis"]["demote_days"])
    return (target if streak >= needed else previous_state), streak


def evidence_for(scores: dict[str, float | None], total: float | None, state: str, completeness_reason: str | None) -> list[str]:
    evidence: list[str] = []
    if total is not None:
        evidence.append(f"flow_score={total:.2f}")
    for key in AXES:
        if scores[key] is not None:
            evidence.append(f"{key}={scores[key]:.1f}")
    if completeness_reason:
        evidence.append(completeness_reason)
    evidence.append(f"target_state={state}")
    return evidence


def evaluate_snapshot(raw: dict[str, Any], *, config: dict[str, Any], as_of: date) -> dict[str, Any]:
    kind = str(raw.get("kind") or "").upper()
    if kind not in {"SECTOR", "THEME"}:
        raise MoneyFlowDetectorError("kind must be SECTOR or THEME")
    entity_id = str(raw.get("id") or "").strip()
    name = str(raw.get("name") or "").strip()
    if not entity_id or not name:
        raise MoneyFlowDetectorError("id and name are required")

    scores = normalize_scores(raw.get("scores") or {})
    completeness, completeness_reason = data_completeness(scores, int(config["minimum_non_null_axes"]))
    target = target_state(scores, config)
    previous_state = str(raw.get("previous_state") or "COLD")
    prior_target = raw.get("prior_target_state")
    prior_streak = int(raw.get("target_streak") or 0)
    state, streak = apply_hysteresis(
        previous_state=previous_state,
        target=target,
        prior_target=str(prior_target) if prior_target else None,
        target_streak=prior_streak,
        config=config,
    )
    total = flow_score(scores, config["weights"])
    selection_signal = state in {"WARMING", "INFLOW"} and completeness != "INSUFFICIENT"
    prior_since = str(raw.get("state_since") or as_of.isoformat())

    return {
        "schema_version": 1,
        "id": entity_id,
        "name": name,
        "kind": kind,
        "as_of": as_of.isoformat(),
        "state": state,
        "previous_state": previous_state,
        "state_since": as_of.isoformat() if state != previous_state else prior_since,
        "target_state": target,
        "target_streak": streak,
        "scores": scores,
        "flow_score": total,
        "evidence": evidence_for(scores, total, target, completeness_reason),
        "member_count": int(raw.get("member_count") or 0),
        "membership_as_of": raw.get("membership_as_of"),
        "data_completeness": completeness,
        "data_completeness_reason": completeness_reason,
        "selection_signal": selection_signal,
    }
