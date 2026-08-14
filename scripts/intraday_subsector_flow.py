from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

FRESHNESS = {"FRESH", "STALE", "UNKNOWN"}
COMPLETENESS = {"COMPLETE", "PARTIAL", "UNKNOWN"}
BENCHMARKS = {"TOPIX", "NIKKEI225", "OTHER", "UNKNOWN"}


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


def validate_intraday_subsector_flow(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate PR1 observation shape without classifying flow or making a trade decision."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
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
    out["sector"] = {
        "id": _text(sector.get("id"), "sector.id"),
        "label": _text(sector.get("label"), "sector.label"),
        "medium_term_regime": _text(sector.get("medium_term_regime"), "sector.medium_term_regime"),
    }

    subsector = out.get("subsector")
    if not isinstance(subsector, dict):
        raise ValueError("subsector must be an object")
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
    out["leaders"] = [
        {
            "security_code": _text(item.get("security_code"), f"leaders[{i}].security_code"),
            "name": _text(item.get("name"), f"leaders[{i}].name"),
            "intraday_return": _nullable_number(item.get("intraday_return"), f"leaders[{i}].intraday_return"),
        }
        for i, item in enumerate(leaders)
        if isinstance(item, dict)
    ]
    if len(out["leaders"]) != len(leaders):
        raise ValueError("each leader must be an object")

    if out.get("flow_state") != "UNKNOWN" or out.get("acceleration_state") != "UNKNOWN":
        raise ValueError("PR1 flow_state and acceleration_state must remain UNKNOWN")
    if out["freshness"] != "FRESH" or out["data_completeness"] != "COMPLETE":
        # Fail closed: no missing observation is converted into a synthetic normal/zero value.
        for key in ("breadth", "turnover_ratio"):
            if key not in obs:
                out["observations"][key] = None
    return out
