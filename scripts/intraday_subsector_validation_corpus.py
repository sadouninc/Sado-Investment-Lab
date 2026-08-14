from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Iterable

from scripts.intraday_subsector_aggregation import snapshot_identity
from scripts.intraday_subsector_flow import validate_intraday_subsector_flow


def _timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty ISO-8601 string")
    value = value.strip()
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    return value


def observation_identity(snapshot: dict[str, Any]) -> str:
    return snapshot_identity(validate_intraday_subsector_flow(snapshot))


def annotation_identity(annotation: dict[str, Any]) -> str:
    observation_id = annotation.get("observation_id")
    authority = annotation.get("label_source_or_authority")
    annotated_at = annotation.get("annotated_at")
    expected_signal = annotation.get("expected_signal")
    if not all(isinstance(value, str) and value.strip() for value in (observation_id, authority, expected_signal)):
        raise ValueError("annotation identity fields must be non-empty strings")
    _timestamp(annotated_at, "annotated_at")
    return "|".join((observation_id.strip(), authority.strip(), annotated_at.strip(), expected_signal.strip()))


def validate_annotation(annotation: dict[str, Any], *, known_observation_ids: set[str]) -> dict[str, Any]:
    if not isinstance(annotation, dict):
        raise ValueError("annotation must be an object")
    out = deepcopy(annotation)
    observation_id = out.get("observation_id")
    if not isinstance(observation_id, str) or observation_id not in known_observation_ids:
        raise ValueError("annotation must reference a known observation_id")
    for field in ("label_source_or_authority", "rationale", "expected_signal"):
        value = out.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
        out[field] = value.strip()
    out["annotated_at"] = _timestamp(out.get("annotated_at"), "annotated_at")
    return out


def append_observation(corpus: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Append a raw PR2 snapshot once. Unlabeled observations are valid corpus rows."""
    out = deepcopy(corpus)
    observations = list(out.setdefault("observations", []))
    out.setdefault("annotations", [])
    validated = validate_intraday_subsector_flow(snapshot)
    identity = observation_identity(validated)
    existing = {observation_identity(item) for item in observations}
    if identity not in existing:
        observations.append(validated)
    out["observations"] = observations
    return out


def append_annotation(corpus: dict[str, Any], annotation: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(corpus)
    observations = list(out.setdefault("observations", []))
    annotations = list(out.setdefault("annotations", []))
    known_ids = {observation_identity(item) for item in observations}
    validated = validate_annotation(annotation, known_observation_ids=known_ids)
    identity = annotation_identity(validated)
    existing = {annotation_identity(item) for item in annotations}
    if identity not in existing:
        annotations.append(validated)
    out["annotations"] = annotations
    return out


def replay_observations(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    """Return deterministic historical input order for candidate-profile replay."""
    observations: Iterable[dict[str, Any]] = corpus.get("observations", [])
    validated = [validate_intraday_subsector_flow(item) for item in observations]
    return sorted(validated, key=lambda item: (item["observed_at"], observation_identity(item)))
