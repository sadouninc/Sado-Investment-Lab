from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

SIGNAL_TYPES = {
    "MARKET", "COMPANY", "THEME", "KEY_PERSON", "POLICY",
    "TECHNOLOGY", "SUPPLY_CHAIN", "MACRO", "OTHER",
}
STATUSES = {
    "WATCHING", "STRENGTHENING", "WEAKENING", "MIXED",
    "PROMOTED", "DISMISSED", "EXPIRED", "SUPERSEDED",
}
DIRECTIONS = {"STRENGTHENING", "WEAKENING", "MIXED", "UNKNOWN"}
OBSERVATION_EFFECTS = {"STRENGTHENS", "WEAKENS", "NEUTRAL", "CONFLICTS"}
TERMINAL_STATUSES = {"PROMOTED", "DISMISSED", "EXPIRED", "SUPERSEDED"}


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _parse_datetime(value: Any, field: str) -> datetime:
    text = _require_text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include timezone")
    return parsed


def _slug(value: str) -> str:
    ascii_text = value.strip().lower()
    ascii_text = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return ascii_text or "signal"


def deterministic_signal_id(signal_key: str, first_observed_at: str, related_entities: list[dict[str, Any]] | None = None) -> str:
    key = _require_text(signal_key, "signal_key")
    observed = _parse_datetime(first_observed_at, "first_observed_at")
    normalized_relations: list[str] = []
    for entity in related_entities or []:
        if not isinstance(entity, dict):
            raise ValueError("related_entities entries must be objects")
        entity_type = _require_text(entity.get("type"), "related_entities.type").upper()
        entity_id = _require_text(entity.get("id"), "related_entities.id").upper()
        normalized_relations.append(f"{entity_type}:{entity_id}")
    payload = "|".join([key.strip().lower(), observed.date().isoformat(), *sorted(set(normalized_relations))])
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"signal:{_slug(key)}:{observed.date().isoformat()}:{digest}"


def validate_observation(observation: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(observation, dict):
        raise ValueError("observation must be an object")
    result = deepcopy(observation)
    _parse_datetime(result.get("observed_at"), "observed_at")
    _require_text(result.get("observation"), "observation")
    _require_text(result.get("actor"), "actor")
    effect = _require_text(result.get("effect"), "effect").upper()
    if effect not in OBSERVATION_EFFECTS:
        raise ValueError(f"unsupported observation effect: {effect}")
    result["effect"] = effect
    source_ref = result.get("source_ref")
    if source_ref is not None and not isinstance(source_ref, str):
        raise ValueError("source_ref must be a string or null")
    interpretation = result.get("interpretation")
    if interpretation is not None and not isinstance(interpretation, str):
        raise ValueError("interpretation must be a string or null")
    return result


def validate_signal(signal: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(signal, dict):
        raise ValueError("signal must be an object")
    result = deepcopy(signal)
    signal_key = _require_text(result.get("signal_key"), "signal_key")
    _require_text(result.get("title"), "title")
    _require_text(result.get("summary"), "summary")
    _require_text(result.get("why_it_may_matter"), "why_it_may_matter")
    _require_text(result.get("created_by"), "created_by")
    signal_type = _require_text(result.get("signal_type"), "signal_type").upper()
    status = _require_text(result.get("status"), "status").upper()
    direction = _require_text(result.get("direction", "UNKNOWN"), "direction").upper()
    if signal_type not in SIGNAL_TYPES:
        raise ValueError(f"unsupported signal_type: {signal_type}")
    if status not in STATUSES:
        raise ValueError(f"unsupported status: {status}")
    if direction not in DIRECTIONS:
        raise ValueError(f"unsupported direction: {direction}")
    result.update(signal_type=signal_type, status=status, direction=direction)
    first = _parse_datetime(result.get("first_observed_at"), "first_observed_at")
    last = _parse_datetime(result.get("last_observed_at"), "last_observed_at")
    if last < first:
        raise ValueError("last_observed_at cannot precede first_observed_at")
    related_entities = result.get("related_entities", [])
    if not isinstance(related_entities, list):
        raise ValueError("related_entities must be a list")
    expected_id = deterministic_signal_id(signal_key, result["first_observed_at"], related_entities)
    supplied_id = result.get("signal_id")
    if supplied_id is None:
        result["signal_id"] = expected_id
    elif supplied_id != expected_id:
        raise ValueError("signal_id does not match deterministic identity")
    observations = result.get("observations", [])
    if not isinstance(observations, list):
        raise ValueError("observations must be a list")
    result["observations"] = [validate_observation(item) for item in observations]
    source_refs = result.get("source_refs", [])
    if not isinstance(source_refs, list):
        raise ValueError("source_refs must be a list")
    for ref in source_refs:
        if ref is not None and not isinstance(ref, str):
            raise ValueError("source_refs entries must be strings or null")
    for field in ("next_checkpoint", "expires_at", "promoted_at", "resolved_at"):
        if result.get(field) is not None:
            _parse_datetime(result[field], field)
    if result.get("expires_at") and _parse_datetime(result["expires_at"], "expires_at") < first:
        raise ValueError("expires_at cannot precede first_observed_at")
    if result.get("next_checkpoint") is None and result.get("expires_at") is None:
        _require_text(result.get("checkpoint_reason"), "checkpoint_reason")
    if status == "PROMOTED":
        _require_text(result.get("promotion_ref"), "promotion_ref")
        _parse_datetime(result.get("promoted_at"), "promoted_at")
    if status == "SUPERSEDED":
        _require_text(result.get("superseded_by"), "superseded_by")
    if status in {"DISMISSED", "EXPIRED", "SUPERSEDED"}:
        _require_text(result.get("resolution_reason"), "resolution_reason")
    if status in TERMINAL_STATUSES:
        _parse_datetime(result.get("resolved_at"), "resolved_at")
    duplicate_state = result.get("duplicate_state", "UNIQUE")
    if duplicate_state not in {"UNIQUE", "POSSIBLE_DUPLICATE"}:
        raise ValueError("duplicate_state must be UNIQUE or POSSIBLE_DUPLICATE")
    result["duplicate_state"] = duplicate_state
    if duplicate_state == "POSSIBLE_DUPLICATE":
        refs = result.get("possible_duplicate_refs")
        if not isinstance(refs, list) or not any(isinstance(item, str) and item for item in refs):
            raise ValueError("possible_duplicate_refs required for POSSIBLE_DUPLICATE")
    return result


def append_observation(signal: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
    result = validate_signal(signal)
    if result["status"] in TERMINAL_STATUSES:
        raise ValueError("cannot append observation to terminal signal")
    item = validate_observation(observation)
    observed_at = _parse_datetime(item["observed_at"], "observed_at")
    last = _parse_datetime(result["last_observed_at"], "last_observed_at")
    if observed_at < last:
        raise ValueError("observations must be append-only chronological")
    result.setdefault("observations", []).append(item)
    result["last_observed_at"] = item["observed_at"]
    return result


def transition_signal(signal: dict[str, Any], new_status: str, *, at: str, reason: str | None = None, promotion_ref: str | None = None, superseded_by: str | None = None) -> dict[str, Any]:
    result = validate_signal(signal)
    target = _require_text(new_status, "new_status").upper()
    if target not in STATUSES:
        raise ValueError(f"unsupported status: {target}")
    if result["status"] in TERMINAL_STATUSES:
        raise ValueError("terminal signal cannot transition")
    _parse_datetime(at, "at")
    result["status"] = target
    if target in {"STRENGTHENING", "WEAKENING", "MIXED"}:
        result["direction"] = target
    if target == "PROMOTED":
        result["promotion_ref"] = _require_text(promotion_ref, "promotion_ref")
        result["promoted_at"] = at
        result["resolved_at"] = at
    elif target == "SUPERSEDED":
        result["superseded_by"] = _require_text(superseded_by, "superseded_by")
        result["resolution_reason"] = _require_text(reason, "reason")
        result["resolved_at"] = at
    elif target in {"DISMISSED", "EXPIRED"}:
        result["resolution_reason"] = _require_text(reason, "reason")
        result["resolved_at"] = at
    return validate_signal(result)


def mark_possible_duplicate(signal: dict[str, Any], candidate_refs: list[str]) -> dict[str, Any]:
    result = validate_signal(signal)
    refs = sorted({ref.strip() for ref in candidate_refs if isinstance(ref, str) and ref.strip()})
    if not refs:
        raise ValueError("candidate_refs must contain at least one signal ref")
    result["duplicate_state"] = "POSSIBLE_DUPLICATE"
    result["possible_duplicate_refs"] = refs
    return validate_signal(result)


def dumps(signal: dict[str, Any]) -> str:
    return json.dumps(validate_signal(signal), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
