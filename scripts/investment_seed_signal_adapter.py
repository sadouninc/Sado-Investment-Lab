from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from scripts.developing_signal_registry import validate_signal
from scripts.developing_signal_store import CANONICAL_SIGNAL_STORE, read_store, write_signal
from scripts.investment_seed import transition_seed, validate_seed


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _existing_signal_for_seed(seed_id: str, path: Path) -> dict[str, Any] | None:
    result = read_store(path)
    if result.status == "PARTIAL":
        raise ValueError("canonical signal store is PARTIAL; repair before Seed promotion")
    matches = [
        signal for signal in result.signals
        if signal.get("origin_seed_ref") == seed_id
    ]
    if len(matches) > 1:
        raise ValueError(f"multiple Developing Signals reference origin_seed_ref: {seed_id}")
    return deepcopy(matches[0]) if matches else None


def build_signal_from_seed(
    seed: dict[str, Any],
    *,
    signal_type: str,
    title: str,
    related_entities: list[dict[str, str]],
    why_continued_observation: str,
    next_checkpoint: str | None = None,
    checkpoint_reason: str | None = None,
) -> dict[str, Any]:
    """Build the minimal #170 Signal projection without copying Seed raw payload."""
    validated_seed = validate_seed(seed)
    if validated_seed["status"] not in {"VALIDATING", "PROMOTED_TO_SIGNAL"}:
        raise ValueError("seed must be VALIDATING before promotion")
    if not isinstance(related_entities, list):
        raise ValueError("related_entities must be a list")

    normalized_entities: list[dict[str, str]] = []
    for item in related_entities:
        if not isinstance(item, dict):
            raise ValueError("related_entities entries must be objects")
        normalized_entities.append(
            {
                "type": _require_text(item.get("type"), "related_entities.type").upper(),
                "id": _require_text(item.get("id"), "related_entities.id").upper(),
            }
        )

    if next_checkpoint is None:
        _require_text(checkpoint_reason, "checkpoint_reason")

    observed_at = validated_seed["observed_at"]
    signal = {
        "signal_key": f"origin-seed:{validated_seed['seed_id']}",
        "title": _require_text(title, "title"),
        "signal_type": _require_text(signal_type, "signal_type").upper(),
        "status": "WATCHING",
        "direction": "UNKNOWN",
        "first_observed_at": observed_at,
        "last_observed_at": observed_at,
        "created_by": validated_seed["source_sensor"],
        "summary": validated_seed["observation"],
        "why_it_may_matter": _require_text(
            why_continued_observation, "why_continued_observation"
        ),
        "source_refs": deepcopy(validated_seed["source_refs"]),
        "related_entities": normalized_entities,
        "observations": [],
        "next_checkpoint": next_checkpoint,
        "expires_at": None,
        "checkpoint_reason": checkpoint_reason,
        "duplicate_state": "UNIQUE",
        "origin_seed_ref": validated_seed["seed_id"],
    }
    return validate_signal(signal)


def promote_seed_to_signal(
    seed: dict[str, Any],
    *,
    promoted_at: str,
    signal_type: str,
    title: str,
    related_entities: list[dict[str, str]],
    why_continued_observation: str,
    next_checkpoint: str | None = None,
    checkpoint_reason: str | None = None,
    signal_path: Path = CANONICAL_SIGNAL_STORE,
) -> dict[str, Any]:
    """Write the canonical Signal first, then return the promoted Seed projection.

    The function is intentionally fail-closed: a destination write/validation failure
    raises before a PROMOTED Seed is returned. If a prior attempt wrote the Signal but
    the caller failed to persist the Seed result, retry finds the existing
    ``origin_seed_ref`` and reuses the same promotion_ref instead of creating another
    active Signal.
    """
    validated_seed = validate_seed(seed)
    if validated_seed["status"] == "REJECTED":
        raise ValueError("REJECTED seed cannot be promoted")
    if validated_seed["status"] == "SEED":
        raise ValueError("seed must enter VALIDATING before promotion")

    candidate = build_signal_from_seed(
        validated_seed,
        signal_type=signal_type,
        title=title,
        related_entities=related_entities,
        why_continued_observation=why_continued_observation,
        next_checkpoint=next_checkpoint,
        checkpoint_reason=checkpoint_reason,
    )
    existing = _existing_signal_for_seed(validated_seed["seed_id"], signal_path)

    if existing is not None:
        if existing != candidate:
            raise ValueError("origin_seed_ref already maps to a different Signal payload")
        signal_id = existing["signal_id"]
    else:
        if validated_seed["status"] == "PROMOTED_TO_SIGNAL":
            raise ValueError("promoted Seed references a missing destination Signal")
        # Pre-validate the Seed transition before any destination mutation.
        transition_seed(
            validated_seed,
            "PROMOTED_TO_SIGNAL",
            at=promoted_at,
            promotion_ref=candidate["signal_id"],
        )
        write_signal(candidate, signal_path)
        signal_id = candidate["signal_id"]

    if validated_seed["status"] == "PROMOTED_TO_SIGNAL":
        if validated_seed.get("promotion_ref") != signal_id:
            raise ValueError("Seed promotion_ref does not match origin_seed_ref destination")
        return validated_seed

    return transition_seed(
        validated_seed,
        "PROMOTED_TO_SIGNAL",
        at=promoted_at,
        promotion_ref=signal_id,
    )
