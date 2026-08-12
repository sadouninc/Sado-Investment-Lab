from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


USABLE_SOURCE_STATES = {"OK", "PARTIAL", "STALE"}


def _source_status(dataset: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    for row in dataset.get("source_status") or []:
        if isinstance(row, Mapping) and row.get("name") == name:
            return row
    return {
        "name": name,
        "status": "MISSING",
        "reason": "source status not available",
    }


def project_portfolio_impact(dataset: Mapping[str, Any]) -> dict[str, Any]:
    """Project canonical holdings for Home without inventing an impact judgement.

    Home is a read-only consumer. Until a canonical security-level signal/research
    join exists in Morning Dataset, the projection exposes holdings and freshness
    but keeps impact_state UNKNOWN instead of deriving recommendations from names,
    sectors, or market movement.
    """
    source = _source_status(dataset, "portfolio")
    status = str(source.get("status") or "MISSING").upper()
    portfolio = dataset.get("portfolio") if isinstance(dataset.get("portfolio"), Mapping) else {}
    raw_positions = portfolio.get("positions") if isinstance(portfolio.get("positions"), list) else []
    positions = [deepcopy(dict(row)) for row in raw_positions if isinstance(row, Mapping)]

    if status not in USABLE_SOURCE_STATES or not positions:
        return {
            "status": status if status else "MISSING",
            "as_of": source.get("as_of"),
            "source_reference": source.get("source_reference") or source.get("source"),
            "reason": source.get("reason") or "canonical portfolio holdings are unavailable",
            "positions": [],
            "impact_state": "UNAVAILABLE",
            "impact_reason": "保有銘柄を確認できないため、自分への影響を判定しません。",
        }

    return {
        "status": status,
        "as_of": source.get("as_of"),
        "source_reference": source.get("source_reference") or source.get("source"),
        "reason": source.get("reason"),
        "positions": positions,
        "impact_state": "UNKNOWN",
        "impact_reason": (
            "保有銘柄はCanonical Portfolioから確認できますが、"
            "security-levelのMarket/Research/Signal joinは未接続です。"
            "Homeで独自の影響score・BUY/SELLを生成しません。"
        ),
    }
