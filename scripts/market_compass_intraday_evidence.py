from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from scripts.intraday_subsector_flow import validate_intraday_subsector_flow


def adapt_intraday_subsector_to_market_compass(payload: dict[str, Any]) -> dict[str, Any]:
    """Adapt #550 intraday subsector evidence into #586 Market Compass intraday evidence.

    Invariants:
    - Consume existing #550 validator (`validate_intraday_subsector_flow`).
    - Preserve UNKNOWN/PARTIAL/STALE fail-closed semantics.
    - No threshold changes or trade recommendations generated.
    """
    validated = validate_intraday_subsector_flow(payload)

    freshness = validated["freshness"]
    completeness = validated["data_completeness"]

    is_fail_closed = freshness != "FRESH" or completeness != "COMPLETE"

    if freshness == "STALE":
        quality_status = "STALE"
    elif completeness == "PARTIAL":
        quality_status = "PARTIAL"
    elif freshness == "UNKNOWN" or completeness == "UNKNOWN":
        quality_status = "UNKNOWN"
    elif freshness == "FRESH" and completeness == "COMPLETE":
        quality_status = "PASS"
    else:
        quality_status = "UNKNOWN"

    obs = validated["observations"]
    subsector = validated["subsector"]

    adapted = {
        "schema_version": 1,
        "adapted_at": datetime.now(timezone.utc).isoformat(),
        "subsector": {
            "id": subsector["id"],
            "label": subsector["label"],
            "taxonomy_version": subsector["taxonomy_version"],
            "as_of": subsector["as_of"],
            "source_or_authority": subsector["source_or_authority"],
        },
        "sector": {
            "id": validated["sector"]["id"],
            "label": validated["sector"]["label"],
            "medium_term_regime": validated["sector"]["medium_term_regime"],
        },
        "data_quality": {
            "freshness": freshness,
            "data_completeness": completeness,
            "status": quality_status,
            "is_fail_closed": is_fail_closed,
        },
        "benchmark": validated["benchmark"],
        "metrics": {
            "intraday_return": obs["intraday_return"],
            "benchmark_return": obs["benchmark_return"],
            "relative_return": obs["relative_return"],
            "rising_count": obs["rising_count"],
            "constituent_count": obs["constituent_count"],
            "breadth": obs["breadth"],
            "median_constituent_return": obs["median_constituent_return"],
            "turnover_ratio": obs["turnover_ratio"],
            "concentration_top1": obs["concentration_top1"],
        },
        "flow_state": validated["flow_state"],
        "acceleration_state": validated["acceleration_state"],
        "leaders": deepcopy(validated["leaders"]),
        "evidence_refs": {
            "observed_at": validated["observed_at"],
            "source": validated["source"],
            "source_or_authority": subsector["source_or_authority"],
        },
        "investment_authority": "READ_ONLY_EVIDENCE",
        "trade_recommendation": None,
    }

    return adapted
