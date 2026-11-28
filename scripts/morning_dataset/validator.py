from __future__ import annotations

from datetime import datetime
import json
import math
from typing import Any

from .schema import SCHEMA_VERSION, STATUS_VALUES, TOP_LEVEL_FIELDS


# The eight deterministic source slots the generator reports in source_status.
CANONICAL_SOURCE_NAMES = (
    "market",
    "portfolio",
    "capital",
    "candidates",
    "investor_dna",
    "events",
    "watchlist",
    "sector_rotation",
)
QUALITY_COUNT_FIELDS = ("available_sources", "ok_sources", "usable_sources", "total_sources")


class MorningDatasetValidationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MorningDatasetValidationError(message)


def _is_status(value: object) -> bool:
    # Guard the set lookup: an unhashable value (list/dict) would otherwise raise
    # an accidental TypeError instead of a validation error.
    return isinstance(value, str) and value in STATUS_VALUES


def _is_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _derived_quality_status(counts: dict[str, int], total: int) -> str:
    # Mirrors generator._quality so a hand-edited data_quality cannot claim a
    # better state than its own source_status supports.
    ok = counts["OK"]
    usable = counts["OK"] + counts["PARTIAL"] + counts["STALE"]
    if total == 0 or ok == total:
        return "OK"
    if usable == 0:
        return "MISSING"
    return "PARTIAL"


def _validate_source_status(source_status: object) -> dict[str, int]:
    _require(isinstance(source_status, list), "source_status must be an array")
    counts = {status: 0 for status in ("OK", "PARTIAL", "STALE", "MISSING")}
    seen: list[str] = []
    for source in source_status:
        _require(isinstance(source, dict), "source_status entries must be objects")
        name = source.get("name")
        _require(isinstance(name, str) and bool(name.strip()), "source status needs name")
        _require(name in CANONICAL_SOURCE_NAMES, f"unknown source status name: {name}")
        _require(name not in seen, f"duplicate source status name: {name}")
        seen.append(name)
        _require(_is_status(source.get("status")), f"invalid source status for {name}")
        counts[source["status"]] += 1
    missing = [name for name in CANONICAL_SOURCE_NAMES if name not in seen]
    _require(not missing, f"missing source status entries: {', '.join(missing)}")
    return counts


def _validate_quality(quality: object, counts: dict[str, int]) -> None:
    _require(isinstance(quality, dict), "data_quality must be an object")
    _require(_is_status(quality.get("status")), "invalid data_quality.status")

    completeness = quality.get("completeness")
    _require(
        isinstance(completeness, (int, float)) and not isinstance(completeness, bool),
        "data_quality.completeness must be numeric",
    )
    try:
        completeness_value = float(completeness)
    except OverflowError as exc:
        raise MorningDatasetValidationError("data_quality.completeness must be finite") from exc
    _require(math.isfinite(completeness_value), "data_quality.completeness must be finite")
    _require(0 <= completeness_value <= 1, "data_quality.completeness must be 0..1")

    for field in QUALITY_COUNT_FIELDS:
        _require(_is_count(quality.get(field)), f"data_quality.{field} must be a non-negative integer")

    total = sum(counts.values())
    ok = counts["OK"]
    usable = counts["OK"] + counts["PARTIAL"] + counts["STALE"]
    _require(quality["total_sources"] == total, "data_quality.total_sources does not match source_status")
    _require(quality["ok_sources"] == ok, "data_quality.ok_sources does not match source_status")
    _require(quality["available_sources"] == ok, "data_quality.available_sources does not match source_status")
    _require(quality["usable_sources"] == usable, "data_quality.usable_sources does not match source_status")

    source_counts = quality.get("source_counts")
    _require(isinstance(source_counts, dict), "data_quality.source_counts must be an object")
    _require(
        set(source_counts) == set(counts),
        "data_quality.source_counts must contain exactly OK, PARTIAL, STALE and MISSING",
    )
    for status, expected in counts.items():
        value = source_counts[status]
        _require(_is_count(value), f"data_quality.source_counts.{status} must be a non-negative integer")
        _require(value == expected, f"data_quality.source_counts.{status} does not match source_status")

    expected_completeness = 1.0 if total == 0 else round(ok / total, 4)
    _require(
        math.isclose(completeness_value, expected_completeness, abs_tol=5e-5),
        "data_quality.completeness does not match source_status",
    )
    _require(
        quality.get("completeness_label") == f"{ok} / {total}",
        "data_quality.completeness_label does not match source_status",
    )
    _require(
        quality["status"] == _derived_quality_status(counts, total),
        "data_quality.status does not match source_status",
    )


def validate_dataset(payload: dict[str, Any]) -> dict[str, Any]:
    _require(isinstance(payload, dict), "dataset must be an object")
    missing = [key for key in TOP_LEVEL_FIELDS if key not in payload]
    _require(not missing, f"missing top-level fields: {', '.join(missing)}")
    _require(
        isinstance(payload["schema_version"], str) and payload["schema_version"] == SCHEMA_VERSION,
        "unsupported schema_version",
    )

    for key in ("generated_at", "as_of"):
        value = payload[key]
        _require(isinstance(value, str) and value, f"{key} must be a non-empty string")
        try:
            datetime.fromisoformat(value)
        except ValueError as exc:
            raise MorningDatasetValidationError(f"{key} must be ISO-8601") from exc

    counts = _validate_source_status(payload["source_status"])
    _validate_quality(payload["data_quality"], counts)

    # Serialization is part of the public contract: strict, finite JSON only.
    try:
        json.dumps(payload, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise MorningDatasetValidationError(f"dataset must serialize to strict finite JSON: {exc}") from exc
    return payload
