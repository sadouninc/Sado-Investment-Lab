from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

FRESHNESS = {"FRESH", "STALE", "UNKNOWN"}
COMPLETENESS = {"COMPLETE", "PARTIAL", "UNKNOWN"}
BENCHMARKS = {"TOPIX", "NIKKEI225", "OTHER", "UNKNOWN"}
TOP_LEVEL_FIELDS = {
    "schema_version",
    "observed_at",
    "source",
    "freshness",
    "data_completeness",
    "benchmark",
    "sector",
    "subsector",
    "observations",
    "leaders",
    "flow_state",
    "acceleration_state",
}
SECTOR_FIELDS = {"id", "label", "medium_term_regime"}
SUBSECTOR_FIELDS = {"id", "label", "taxonomy_version", "as_of", "source_or_authority"}
OBSERVATION_FIELDS = {
    "intraday_return",
    "benchmark_return",
    "relative_return",
    "rising_count",
    "constituent_count",
    "breadth",
    "median_constituent_return",
    "turnover_ratio",
    "concentration_top1",
}
LEADER_FIELDS = {"security_code", "name", "intraday_return"}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _nullable_number(value: Any, field: str) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number or null")
    return value


def _nullable_count(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer or null")
    return value


def _require_exact_fields(value: dict[str, Any], expected: set[str], field: str) -> None:
    """Keep the Python validator aligned with JSON Schema additionalProperties=false.

    Canonical nullable fields must be present explicitly as null when unavailable.
    Silently inventing missing nulls or dropping unknown fields would hide producer drift.
    """
    actual = set(value)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        raise ValueError(f"{field} missing required fields: {', '.join(missing)}")
    if extra:
        raise ValueError(f"{field} contains unsupported fields: {', '.join(extra)}")


def validate_intraday_subsector_flow(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate PR1 observation shape without classifying flow or making a trade decision."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    _require_exact_fields(payload, TOP_LEVEL_FIELDS, "payload")
    out = deepcopy(payload)
    if out.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    observed_at = _text(out.get("observed_at"), "observed_at")
    try:
        datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at must be ISO-8601") from exc
    out["source"] = _text(out.get("source"), "source")

    for field, allowed in (("freshness", FRESHNESS), ("data_completeness", COMPLETENESS), ("benchmark", BENCHMARKS)):
        value = _text(out.get(field), field).upper()
        if value not in allowed:
            raise ValueError(f"unsupported {field}: {value}")
        out[field] = value

    sector = out.get("sector")
    if not isinstance(sector, dict):
        raise ValueError("sector must be an object")
    _require_exact_fields(sector, SECTOR_FIELDS, "sector")
    out["sector"] = {
        "id": _text(sector.get("id"), "sector.id"),
        "label": _text(sector.get("label"), "sector.label"),
        "medium_term_regime": _text(sector.get("medium_term_regime"), "sector.medium_term_regime"),
    }

    subsector = out.get("subsector")
    if not isinstance(subsector, dict):
        raise ValueError("subsector must be an object")
    _require_exact_fields(subsector, SUBSECTOR_FIELDS, "subsector")
    out["subsector"] = {
        "id": _text(subsector.get("id"), "subsector.id"),
        "label": _text(subsector.get("label"), "subsector.label"),
        "taxonomy_version": _text(subsector.get("taxonomy_version"), "subsector.taxonomy_version"),
        "as_of": _text(subsector.get("as_of"), "subsector.as_of"),
        "source_or_authority": _text(subsector.get("source_or_authority"), "subsector.source_or_authority"),
    }

    obs = out.get("observations")
    if not isinstance(obs, dict):
        raise ValueError("observations must be an object")
    _require_exact_fields(obs, OBSERVATION_FIELDS, "observations")
    out["observations"] = {
        "intraday_return": _nullable_number(obs.get("intraday_return"), "observations.intraday_return"),
        "benchmark_return": _nullable_number(obs.get("benchmark_return"), "observations.benchmark_return"),
        "relative_return": _nullable_number(obs.get("relative_return"), "observations.relative_return"),
        "rising_count": _nullable_count(obs.get("rising_count"), "observations.rising_count"),
        "constituent_count": _nullable_count(obs.get("constituent_count"), "observations.constituent_count"),
        "breadth": _nullable_number(obs.get("breadth"), "observations.breadth"),
        "median_constituent_return": _nullable_number(obs.get("median_constituent_return"), "observations.median_constituent_return"),
        "turnover_ratio": _nullable_number(obs.get("turnover_ratio"), "observations.turnover_ratio"),
        "concentration_top1": _nullable_number(obs.get("concentration_top1"), "observations.concentration_top1"),
    }

    rising = out["observations"]["rising_count"]
    total = out["observations"]["constituent_count"]
    breadth = out["observations"]["breadth"]
    if rising is None or total is None or total == 0:
        if breadth is not None:
            raise ValueError("breadth must be null when constituent counts are unavailable")
    else:
        expected = rising / total
        if breadth is None or abs(float(breadth) - expected) > 1e-9:
            raise ValueError("breadth must equal rising_count / constituent_count")

    intraday = out["observations"]["intraday_return"]
    benchmark = out["observations"]["benchmark_return"]
    relative = out["observations"]["relative_return"]
    if intraday is None or benchmark is None:
        if relative is not None:
            raise ValueError("relative_return must be null when raw return inputs are unavailable")
    elif relative is None or abs(float(relative) - (intraday - benchmark)) > 1e-9:
        raise ValueError("relative_return must equal intraday_return - benchmark_return")

    leaders = out.get("leaders")
    if not isinstance(leaders, list):
        raise ValueError("leaders must be a list")
    validated_leaders = []
    for i, item in enumerate(leaders):
        if not isinstance(item, dict):
            raise ValueError("each leader must be an object")
        _require_exact_fields(item, LEADER_FIELDS, f"leaders[{i}]")
        validated_leaders.append(
            {
                "security_code": _text(item.get("security_code"), f"leaders[{i}].security_code"),
                "name": _text(item.get("name"), f"leaders[{i}].name"),
                "intraday_return": _nullable_number(item.get("intraday_return"), f"leaders[{i}].intraday_return"),
            }
        )
    out["leaders"] = validated_leaders

    if out.get("flow_state") != "UNKNOWN" or out.get("acceleration_state") != "UNKNOWN":
        raise ValueError("PR1 flow_state and acceleration_state must remain UNKNOWN")
    return out
