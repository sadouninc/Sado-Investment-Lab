from __future__ import annotations

from datetime import datetime
from statistics import median
from typing import Any, Iterable

from scripts.intraday_subsector_flow import validate_intraday_subsector_flow


def _valid_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _positive_concentration_top1(returns: list[float]) -> float | None:
    """Share of positive-return magnitude contributed by the strongest constituent.

    This is an equal-weight, price-return concentration diagnostic, not a claim about
    capital-owner identity or traded-value contribution. No positive return => null.
    """
    positives = [value for value in returns if value > 0]
    if not positives:
        return None
    total = sum(positives)
    return max(positives) / total if total else None


def aggregate_intraday_subsector_snapshot(
    *,
    observed_at: str,
    source: str,
    freshness: str,
    benchmark: str,
    benchmark_return: float | int | None,
    sector: dict[str, Any],
    subsector: dict[str, Any],
    constituents: Iterable[dict[str, Any]],
    membership_count: int | None,
) -> dict[str, Any]:
    """Aggregate raw constituent observations into the PR1 snapshot contract.

    Missing constituent returns are excluded from aggregate math rather than coerced
    to zero. ``membership_count`` is taxonomy membership, while breadth uses only
    valid return observations as its denominator, per the PR2 product handoff.
    """
    rows = [dict(row) for row in constituents]
    valid_rows: list[tuple[dict[str, Any], float]] = []
    for row in rows:
        value = _valid_number(row.get("intraday_return"))
        if value is not None:
            valid_rows.append((row, value))

    returns = [value for _, value in valid_rows]
    valid_count = len(returns)
    rising_count = sum(1 for value in returns if value > 0)
    breadth = rising_count / valid_count if valid_count else None
    intraday_return = _mean(returns)
    benchmark_value = _valid_number(benchmark_return)
    relative_return = (
        intraday_return - benchmark_value
        if intraday_return is not None and benchmark_value is not None
        else None
    )

    comparable_turnover = [
        value
        for row in rows
        if (value := _valid_number(row.get("turnover_ratio"))) is not None
    ]
    turnover_ratio = median(comparable_turnover) if comparable_turnover else None

    ordered_leaders = sorted(
        valid_rows,
        key=lambda item: (-item[1], str(item[0].get("security_code", ""))),
    )
    leaders = [
        {
            "security_code": str(row.get("security_code", "")).strip(),
            "name": str(row.get("name", "")).strip(),
            "intraday_return": value,
        }
        for row, value in ordered_leaders[:5]
    ]

    if membership_count is None:
        completeness = "UNKNOWN"
    elif membership_count < 0:
        raise ValueError("membership_count must be non-negative or null")
    elif valid_count == membership_count:
        completeness = "COMPLETE"
    else:
        completeness = "PARTIAL"

    payload = {
        "schema_version": 1,
        "observed_at": observed_at,
        "source": source,
        "freshness": freshness,
        "data_completeness": completeness,
        "benchmark": benchmark,
        "sector": sector,
        "subsector": subsector,
        "observations": {
            "intraday_return": intraday_return,
            "benchmark_return": benchmark_value,
            "relative_return": relative_return,
            "rising_count": rising_count if valid_count else None,
            "constituent_count": valid_count if valid_count else None,
            "breadth": breadth,
            "median_constituent_return": median(returns) if returns else None,
            "turnover_ratio": turnover_ratio,
            "concentration_top1": _positive_concentration_top1(returns),
        },
        "leaders": leaders,
        "flow_state": "UNKNOWN",
        "acceleration_state": "UNKNOWN",
    }
    return validate_intraday_subsector_flow(payload)


def snapshot_identity(snapshot: dict[str, Any]) -> str:
    validated = validate_intraday_subsector_flow(snapshot)
    observed = datetime.fromisoformat(validated["observed_at"].replace("Z", "+00:00"))
    return "|".join(
        (
            observed.isoformat(),
            validated["source"],
            validated["sector"]["id"],
            validated["subsector"]["id"],
            validated["subsector"]["taxonomy_version"],
        )
    )


def append_snapshot_history(
    history: list[dict[str, Any]], snapshot: dict[str, Any]
) -> list[dict[str, Any]]:
    """Append a validated snapshot once, preserving same-day multi-snapshot history."""
    validated = validate_intraday_subsector_flow(snapshot)
    identity = snapshot_identity(validated)
    existing = {snapshot_identity(item) for item in history}
    if identity in existing:
        return list(history)
    return [*history, validated]
