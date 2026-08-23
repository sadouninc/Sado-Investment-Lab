# Market Compass Intraday Evidence Adapter v1 (#586)

## Overview
This document specifies the contract and fail-closed operational rules for the Market Compass Intraday Evidence Adapter v1.

The adapter maps canonical `#550` intraday subsector evidence into `#586` Market Compass evidence without creating a second money-flow producer/taxonomy or modifying `#568` scoring thresholds.

## Required Invariants
1. **Bounded Adapter Contract**: Consumes existing `#550` intraday subsector evidence using `validate_intraday_subsector_flow`.
2. **Taxonomy & Producer Preservation**: Does not invent missing values or introduce new subsector taxonomy versions.
3. **Fail-Closed Semantics**: Strictly preserves `UNKNOWN`, `PARTIAL`, and `STALE` statuses. If data quality is non-FRESH or non-COMPLETE, `is_fail_closed` evaluates to `True`.
4. **No Threshold Mutation**: Does not alter `#568` threshold calculation rules.
5. **No Trade Authority**: Read-only evidence projection only (`READ_ONLY_EVIDENCE`). No automatic BUY/SELL/HOLD recommendations or broker/order generation.

## Data Quality Mapping
- `freshness == "STALE"` => `status = "STALE"`, `is_fail_closed = True`
- `data_completeness == "PARTIAL"` => `status = "PARTIAL"`, `is_fail_closed = True`
- `freshness == "UNKNOWN"` or `data_completeness == "UNKNOWN"` => `status = "UNKNOWN"`, `is_fail_closed = True`
- `freshness == "FRESH"` and `data_completeness == "COMPLETE"` => `status = "PASS"`, `is_fail_closed = False`

## Output Schema Structure
```json
{
  "schema_version": 1,
  "adapted_at": "ISO-8601 UTC timestamp",
  "subsector": {
    "id": "string",
    "label": "string",
    "taxonomy_version": "string",
    "as_of": "string",
    "source_or_authority": "string"
  },
  "sector": {
    "id": "string",
    "label": "string",
    "medium_term_regime": "string"
  },
  "data_quality": {
    "freshness": "FRESH | STALE | UNKNOWN",
    "data_completeness": "COMPLETE | PARTIAL | UNKNOWN",
    "status": "PASS | STALE | PARTIAL | UNKNOWN",
    "is_fail_closed": boolean
  },
  "benchmark": "TOPIX | NIKKEI225 | OTHER | UNKNOWN",
  "metrics": {
    "intraday_return": float or null,
    "benchmark_return": float or null,
    "relative_return": float or null,
    "rising_count": int or null,
    "constituent_count": int or null,
    "breadth": float or null,
    "median_constituent_return": float or null,
    "turnover_ratio": float or null,
    "concentration_top1": float or null
  },
  "flow_state": "UNKNOWN",
  "acceleration_state": "UNKNOWN",
  "leaders": [],
  "evidence_refs": {
    "observed_at": "string",
    "source": "string",
    "source_or_authority": "string"
  },
  "investment_authority": "READ_ONLY_EVIDENCE",
  "trade_recommendation": null
}
```
