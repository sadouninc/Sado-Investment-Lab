from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Callable

from scripts.money_flow_canonical_run import bounded_fetcher
from scripts.money_flow_detector import load_config as load_detector_config
from scripts.money_flow_history import load_history, upsert_snapshot
from scripts.money_flow_sector_adapter import (
    _series,
    build_sector_snapshots,
    fetch_yahoo_history,
    load_sector_config,
)

Fetcher = Callable[[str, str, str], dict[str, Any]]


class SectorCanonicalRunError(ValueError):
    pass


def _latest_previous(history: list[dict[str, Any]], *, as_of: date) -> dict[str, dict[str, Any]]:
    previous: dict[str, dict[str, Any]] = {}
    for row in history:
        if row.get("kind") != "SECTOR" or str(row.get("as_of") or "") >= as_of.isoformat():
            continue
        entity_id = str(row["id"])
        current = previous.get(entity_id)
        if current is None or str(current["as_of"]) < str(row["as_of"]):
            previous[entity_id] = row
    return previous


def latest_market_date(*, sector_config: dict[str, Any], fetcher: Fetcher = fetch_yahoo_history) -> date:
    benchmark = sector_config.get("benchmark") or {}
    symbol = str(benchmark.get("symbol") or "")
    if not symbol:
        raise SectorCanonicalRunError("benchmark.symbol is required")
    rows = _series(
        fetcher(symbol, str(sector_config.get("history_range") or "6mo"), str(sector_config.get("interval") or "1d")),
        symbol,
    )
    return date.fromisoformat(str(rows[-1]["date"]))


def canonical_sector_set(
    *,
    as_of: date,
    sector_config: dict[str, Any],
    detector_config: dict[str, Any],
    history: list[dict[str, Any]],
    fetcher: Fetcher = fetch_yahoo_history,
) -> dict[str, Any]:
    payload = build_sector_snapshots(
        sector_config=sector_config,
        detector_config=detector_config,
        as_of=as_of,
        fetcher=bounded_fetcher(fetcher, as_of=as_of),
        previous=_latest_previous(history, as_of=as_of),
    )
    requested = int((payload.get("coverage") or {}).get("requested") or 0)
    sectors = list(payload.get("sectors") or [])
    if len(sectors) != requested:
        return {**payload, "persistable": False, "data_completeness": "UNAVAILABLE", "missing_reason": "not all sector proxies available"}

    source_dates = {str((row.get("source_metrics") or {}).get("market_data_as_of") or "") for row in sectors}
    sector_dates = {str((row.get("source_metrics") or {}).get("sector_source_as_of") or "") for row in sectors}
    benchmark_dates = {str((row.get("source_metrics") or {}).get("benchmark_source_as_of") or "") for row in sectors}
    expected = as_of.isoformat()
    if source_dates != {expected} or sector_dates != {expected} or benchmark_dates != {expected}:
        return {
            **payload,
            "persistable": False,
            "data_completeness": "PARTIAL",
            "missing_reason": "mixed-date or stale sector/benchmark market data",
        }

    for row in sectors:
        row["data_completeness"] = "OK"
        row["missing_reason"] = None
    return {**payload, "persistable": True, "data_completeness": "OK", "missing_reason": None}


def persist_sector_set(path: Path, payload: dict[str, Any]) -> dict[str, int]:
    if not payload.get("persistable"):
        return {"NOT_PERSISTED_UNAVAILABLE": len(payload.get("sectors") or [])}
    counts: dict[str, int] = {}
    for snapshot in payload.get("sectors") or []:
        status = upsert_snapshot(path, snapshot)
        counts[status] = counts.get(status, 0) + 1
    return counts


def run_once(
    *,
    as_of: date,
    history_path: Path,
    sector_config_path: Path,
    detector_config_path: Path,
    fetcher: Fetcher = fetch_yahoo_history,
) -> dict[str, Any]:
    history = load_history(history_path)
    payload = canonical_sector_set(
        as_of=as_of,
        sector_config=load_sector_config(sector_config_path),
        detector_config=load_detector_config(detector_config_path),
        history=history,
        fetcher=fetcher,
    )
    return {"snapshot_set": payload, "persistence": persist_sector_set(history_path, payload)}
