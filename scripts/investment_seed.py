from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from typing import Any

SOURCE_SENSORS = {"ASAHI", "REI", "KAEDE", "OWNER", "OTHER"}
SIGNAL_TYPES = {
    "CAPITAL",
    "POLICY",
    "CAPEX",
    "ORDER",
    "SUPPLY_CONSTRAINT",
    "TECHNOLOGY",
    "REGULATION",
    "MANAGEMENT",
    "OTHER",
}
STATUSES = {"SEED", "VALIDATING", "REJECTED", "PROMOTED_TO_SIGNAL"}
TERMINAL_STATUSES = {"REJECTED", "PROMOTED_TO_SIGNAL"}


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


def _string_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    result: list[str] = []
    for item in value:
        result.append(_require_text(item, f"{field} entry"))
    return result


def deterministic_seed_id(
    *,
    observed_at: str,
    source_sensor: str,
    signal_type: str,
    observation: str,
    source_refs: list[str],
) -> str:
    observed = _parse_datetime(observed_at, "observed_at")
    sensor = _require_text(source_sensor, "source_sensor").upper()
    kind = _require_text(signal_type, "signal_type").upper()
    fact = _require_text(observation, "observation")
    refs = sorted({_require_text(ref, "source_refs entry") for ref in source_refs})
    payload = json.dumps(
        {
            "observed_at": observed.isoformat(),
            "source_sensor": sensor,
            "signal_type": kind,
            "observation": fact,
            "source_refs": refs,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"seed:{observed.date().isoformat()}:{digest}"


def validate_seed(seed: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(seed, dict):
        raise ValueError("seed must be an object")
    result = deepcopy(seed)

    observed_at = _require_text(result.get("observed_at"), "observed_at")
    _parse_datetime(observed_at, "observed_at")
    updated_at = _require_text(result.get("updated_at"), "updated_at")
    if _parse_datetime(updated_at, "updated_at") < _parse_datetime(observed_at, "observed_at"):
        raise ValueError("updated_at cannot precede observed_at")

    sensor = _require_text(result.get("source_sensor"), "source_sensor").upper()
    if sensor not in SOURCE_SENSORS:
        raise ValueError(f"unsupported source_sensor: {sensor}")
    result["source_sensor"] = sensor

    signal_type = _require_text(result.get("signal_type"), "signal_type").upper()
    if signal_type not in SIGNAL_TYPES:
        raise ValueError(f"unsupported signal_type: {signal_type}")
    result["signal_type"] = signal_type

    observation = _require_text(result.get("observation"), "observation")
    inference = result.get("inference")
    if inference is not None:
        result["inference"] = _require_text(inference, "inference")
        if result["inference"] == observation:
            raise ValueError("inference must remain distinct from observation")

    source_refs = _string_list(result.get("source_refs"), "source_refs")
    if not source_refs:
        raise ValueError("source_refs must contain at least one provenance ref")
    result["source_refs"] = source_refs
    result["related_seed_refs"] = _string_list(result.get("related_seed_refs"), "related_seed_refs")
    result["related_issue_refs"] = _string_list(result.get("related_issue_refs"), "related_issue_refs")

    expected_id = deterministic_seed_id(
        observed_at=observed_at,
        source_sensor=sensor,
        signal_type=signal_type,
        observation=observation,
        source_refs=source_refs,
    )
    supplied_id = result.get("seed_id")
    if supplied_id is None:
        result["seed_id"] = expected_id
    elif supplied_id != expected_id:
        raise ValueError("seed_id does not match deterministic identity")

    status = _require_text(result.get("status", "SEED"), "status").upper()
    if status not in STATUSES:
        raise ValueError(f"unsupported status: {status}")
    result["status"] = status

    if status == "REJECTED":
        _require_text(result.get("rejection_reason"), "rejection_reason")
    if status == "PROMOTED_TO_SIGNAL":
        _require_text(result.get("promotion_ref"), "promotion_ref")
        promoted_at = _require_text(result.get("promoted_at"), "promoted_at")
        if _parse_datetime(promoted_at, "promoted_at") < _parse_datetime(observed_at, "observed_at"):
            raise ValueError("promoted_at cannot precede observed_at")

    return result


def transition_seed(
    seed: dict[str, Any],
    new_status: str,
    *,
    at: str,
    rejection_reason: str | None = None,
    promotion_ref: str | None = None,
) -> dict[str, Any]:
    result = validate_seed(seed)
    if result["status"] in TERMINAL_STATUSES:
        raise ValueError("terminal seed cannot transition")

    target = _require_text(new_status, "new_status").upper()
    allowed = {
        "SEED": {"VALIDATING", "REJECTED"},
        "VALIDATING": {"REJECTED", "PROMOTED_TO_SIGNAL"},
    }
    if target not in allowed.get(result["status"], set()):
        raise ValueError(f"invalid seed transition: {result['status']} -> {target}")

    transition_at = _parse_datetime(at, "at")
    if transition_at < _parse_datetime(result["updated_at"], "updated_at"):
        raise ValueError("transition at cannot precede updated_at")

    result["status"] = target
    result["updated_at"] = at
    if target == "REJECTED":
        result["rejection_reason"] = _require_text(rejection_reason, "rejection_reason")
    elif target == "PROMOTED_TO_SIGNAL":
        result["promotion_ref"] = _require_text(promotion_ref, "promotion_ref")
        result["promoted_at"] = at
    return validate_seed(result)


def promotion_payload(
    seed: dict[str, Any],
    *,
    title: str,
    related_entity_candidates: list[dict[str, str]],
    why_continued_observation: str,
    next_checkpoint: str | None = None,
    checkpoint_reason: str | None = None,
) -> dict[str, Any]:
    validated = validate_seed(seed)
    if validated["status"] != "PROMOTED_TO_SIGNAL":
        raise ValueError("seed must be PROMOTED_TO_SIGNAL before handoff")
    if not isinstance(related_entity_candidates, list):
        raise ValueError("related_entity_candidates must be a list")
    entities: list[dict[str, str]] = []
    for item in related_entity_candidates:
        if not isinstance(item, dict):
            raise ValueError("related_entity_candidates entries must be objects")
        entities.append(
            {
                "type": _require_text(item.get("type"), "related_entity_candidates.type"),
                "id": _require_text(item.get("id"), "related_entity_candidates.id"),
            }
        )
    if next_checkpoint is None:
        _require_text(checkpoint_reason, "checkpoint_reason")
    return {
        "origin_seed_ref": validated["seed_id"],
        "title": _require_text(title, "title"),
        "observation_summary": validated["observation"],
        "source_refs": deepcopy(validated["source_refs"]),
        "related_entity_candidates": entities,
        "why_continued_observation": _require_text(
            why_continued_observation, "why_continued_observation"
        ),
        "next_checkpoint": next_checkpoint,
        "checkpoint_reason": checkpoint_reason,
    }


class SeedRegistry:
    """In-memory PR1 ingestion boundary with fail-closed identity semantics."""

    def __init__(self) -> None:
        self._seeds: dict[str, dict[str, Any]] = {}

    def ingest(self, seed: dict[str, Any]) -> dict[str, Any]:
        candidate = validate_seed(seed)
        seed_id = candidate["seed_id"]
        existing = self._seeds.get(seed_id)
        if existing is None:
            self._seeds[seed_id] = deepcopy(candidate)
            return {"outcome": "INSERTED", "seed": deepcopy(candidate)}
        if existing == candidate:
            return {"outcome": "UNCHANGED", "seed": deepcopy(existing)}
        raise ValueError(f"seed identity conflict: {seed_id}")

    def get(self, seed_id: str) -> dict[str, Any] | None:
        value = self._seeds.get(_require_text(seed_id, "seed_id"))
        return deepcopy(value) if value is not None else None
