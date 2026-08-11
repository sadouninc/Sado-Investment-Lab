from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Iterable, Mapping


UNKNOWN = "UNKNOWN"
FEATURE_GROUPS = (
    "exposure_proxy",
    "growth_proxy",
    "capacity_proxy",
    "expectation_proxy",
)
REQUIRED_IDENTITY_FIELDS = ("code", "company", "market", "sector")


class UniverseScannerError(ValueError):
    pass


def _text_or_unknown(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else UNKNOWN


def _optional_number(value: Any, *, field: str) -> float | str:
    if value in (None, "", UNKNOWN):
        return UNKNOWN
    if isinstance(value, bool):
        raise UniverseScannerError(f"{field} must be numeric or UNKNOWN")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise UniverseScannerError(f"{field} must be numeric or UNKNOWN") from exc
    if not math.isfinite(number):
        raise UniverseScannerError(f"{field} must be finite or UNKNOWN")
    return number


def _score(value: Any, *, field: str) -> float | str:
    number = _optional_number(value, field=field)
    if number == UNKNOWN:
        return UNKNOWN
    if number < 0 or number > 100:
        raise UniverseScannerError(f"{field} must be between 0 and 100")
    return number


def normalize_universe_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a discovery-universe row without guessing missing facts."""

    source = deepcopy(dict(row))
    normalized = {field: _text_or_unknown(source.get(field)) for field in REQUIRED_IDENTITY_FIELDS}
    normalized["market_cap"] = _optional_number(source.get("market_cap"), field="market_cap")
    normalized["source_timestamp"] = _text_or_unknown(source.get("source_timestamp"))
    normalized["source_confidence"] = _score(source.get("source_confidence"), field="source_confidence")

    features = source.get("features") or {}
    if not isinstance(features, Mapping):
        raise UniverseScannerError("features must be a mapping")
    normalized["features"] = {
        name: _score(features.get(name), field=name) for name in FEATURE_GROUPS
    }

    exclusion_reason = source.get("exclusion_reason")
    normalized["exclusion_reason"] = (
        str(exclusion_reason).strip() if exclusion_reason not in (None, "") else None
    )
    return normalized


def _candidate_score(features: Mapping[str, float | str]) -> tuple[float | str, int]:
    available = [float(features[name]) for name in FEATURE_GROUPS if features[name] != UNKNOWN]
    if not available:
        return UNKNOWN, 0
    return round(sum(available) / len(available), 6), len(available)


def _confidence(row: Mapping[str, Any], available_count: int) -> float:
    coverage = available_count / len(FEATURE_GROUPS)
    source_confidence = row["source_confidence"]
    source_factor = float(source_confidence) / 100 if source_confidence != UNKNOWN else 0.5
    timestamp_factor = 1.0 if row["source_timestamp"] != UNKNOWN else 0.75
    return round(coverage * source_factor * timestamp_factor, 6)


def score_candidate(row: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_universe_row(row)
    score, available_count = _candidate_score(normalized["features"])
    confidence = _confidence(normalized, available_count)

    missing_fields: list[str] = []
    for field in (*REQUIRED_IDENTITY_FIELDS, "market_cap", "source_timestamp", "source_confidence"):
        if normalized[field] == UNKNOWN:
            missing_fields.append(field)
    missing_fields.extend(
        f"features.{name}" for name in FEATURE_GROUPS if normalized["features"][name] == UNKNOWN
    )

    return {
        "code": normalized["code"],
        "company": normalized["company"],
        "market": normalized["market"],
        "sector": normalized["sector"],
        "market_cap": normalized["market_cap"],
        "discovery_score": score,
        "score_confidence": confidence,
        "score_breakdown": dict(normalized["features"]),
        "source_timestamp": normalized["source_timestamp"],
        "source_confidence": normalized["source_confidence"],
        "missing_fields": missing_fields,
        "exclusion_reason": normalized["exclusion_reason"],
        "review_stage": "STAGE2_IR_REVIEW",
        "is_recommendation": False,
        "trade_action": None,
        "target_price": None,
        "recommended_quantity": None,
        "canonical_mutations": [],
    }


def _sort_key(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    score = candidate["discovery_score"]
    has_score = score != UNKNOWN
    numeric_score = float(score) if has_score else 0.0
    return (
        0 if candidate["exclusion_reason"] else 1,
        1 if has_score else 0,
        numeric_score,
        float(candidate["score_confidence"]),
        str(candidate["code"]),
    )


def rank_universe(rows: Iterable[Mapping[str, Any]], *, top_n: int | None = None) -> dict[str, Any]:
    """Return a deterministic discovery queue, never an investment recommendation.

    Missing feature values remain UNKNOWN and are omitted from the score denominator;
    they are not silently converted to zero. Confidence is emitted separately so a
    sparse candidate can still surface without pretending its evidence is complete.
    """

    if top_n is not None and (isinstance(top_n, bool) or not isinstance(top_n, int) or top_n <= 0):
        raise UniverseScannerError("top_n must be a positive integer")

    source_rows = [deepcopy(dict(row)) for row in rows]
    candidates = [score_candidate(row) for row in source_rows]
    ranked = sorted(candidates, key=_sort_key, reverse=True)
    eligible = [candidate for candidate in ranked if not candidate["exclusion_reason"]]
    selected = eligible if top_n is None else eligible[:top_n]

    review_queue = []
    for rank, candidate in enumerate(selected, start=1):
        queued = deepcopy(candidate)
        queued["rank"] = rank
        review_queue.append(queued)

    excluded = [candidate for candidate in ranked if candidate["exclusion_reason"]]
    return {
        "schema_version": 1,
        "purpose": "DISCOVERY_ONLY",
        "feature_groups": list(FEATURE_GROUPS),
        "review_queue": review_queue,
        "excluded": excluded,
        "is_recommendation": False,
        "canonical_mutations": [],
    }
