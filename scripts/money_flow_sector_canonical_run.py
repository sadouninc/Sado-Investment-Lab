"""Run and persist the canonical TOPIX-17 sector snapshot set."""
from __future__ import annotations

import argparse
import copy
import json
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Callable

from scripts.money_flow_canonical_run import CachedFetcher, bounded_fetcher
from scripts.money_flow_detector import load_config as load_detector_config
from scripts.money_flow_history import load_history, snapshot_key, upsert_snapshot
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


def _with_history_range(sector_config: dict[str, Any], history_range_override: str | None) -> dict[str, Any]:
    if not history_range_override:
        return sector_config
    updated = copy.deepcopy(sector_config)
    updated["history_range"] = history_range_override
    return updated


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
    history_range_override: str | None = None,
) -> dict[str, Any]:
    history = load_history(history_path)
    sector_config = _with_history_range(load_sector_config(sector_config_path), history_range_override)
    payload = canonical_sector_set(
        as_of=as_of,
        sector_config=sector_config,
        detector_config=load_detector_config(detector_config_path),
        history=history,
        fetcher=fetcher,
    )
    return {"snapshot_set": payload, "persistence": persist_sector_set(history_path, payload)}


def _write_history(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(records, key=snapshot_key)
    content = "\n".join(json.dumps(record, ensure_ascii=False, sort_keys=True) for record in ordered)
    if content:
        path.write_text(content + "\n", encoding="utf-8")
    elif path.exists():
        path.unlink()


def run_backfill(
    *,
    start: date,
    end: date,
    history_path: Path,
    sector_config_path: Path,
    detector_config_path: Path,
    fetcher: Fetcher = fetch_yahoo_history,
    history_range: str = "2y",
) -> dict[str, Any]:
    """Atomically rebuild a bounded Sector history window oldest-first.

    Existing Sector rows inside the requested window are intentionally rebuilt because
    their hysteresis may have been computed before older history existed. Rows outside
    the window are preserved. To avoid leaving downstream detector states inconsistent,
    the requested end must include the latest existing Sector snapshot date.
    """
    if end < start:
        raise SectorCanonicalRunError("backfill end must be on or after start")

    original_history = load_history(history_path)
    existing_sector_dates = sorted(
        date.fromisoformat(str(row["as_of"]))
        for row in original_history
        if row.get("kind") == "SECTOR"
    )
    if existing_sector_dates and end < existing_sector_dates[-1]:
        raise SectorCanonicalRunError(
            "backfill end must include latest existing Sector snapshot date "
            f"{existing_sector_dates[-1].isoformat()}"
        )

    cached = CachedFetcher(fetcher)
    sector_config = _with_history_range(load_sector_config(sector_config_path), history_range)
    benchmark = sector_config.get("benchmark") or {}
    benchmark_symbol = str(benchmark.get("symbol") or "")
    if not benchmark_symbol:
        raise SectorCanonicalRunError("benchmark.symbol is required")
    interval = str(sector_config.get("interval") or "1d")
    market_rows = _series(cached(benchmark_symbol, history_range, interval), benchmark_symbol)
    trading_dates = [
        row_date
        for row in market_rows
        for row_date in [date.fromisoformat(str(row["date"]))]
        if start <= row_date <= end
    ]
    if not trading_dates:
        raise SectorCanonicalRunError("no benchmark trading dates in requested backfill window")

    preserved_history = [
        row
        for row in original_history
        if not (
            row.get("kind") == "SECTOR"
            and start <= date.fromisoformat(str(row["as_of"])) <= end
        )
    ]

    persistence_counts: dict[str, int] = {}
    unavailable_dates: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        working_history = Path(tmp) / "sector-history.jsonl"
        _write_history(working_history, preserved_history)

        for as_of in trading_dates:
            result = run_once(
                as_of=as_of,
                history_path=working_history,
                sector_config_path=sector_config_path,
                detector_config_path=detector_config_path,
                fetcher=cached,
                history_range_override=history_range,
            )
            snapshot_set = result["snapshot_set"]
            if not snapshot_set.get("persistable"):
                unavailable_dates.append(as_of.isoformat())
            for status, count in result["persistence"].items():
                persistence_counts[status] = persistence_counts.get(status, 0) + int(count)

        rebuilt_history = load_history(working_history)
        _write_history(history_path, rebuilt_history)

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "history_range": history_range,
        "trading_dates_processed": len(trading_dates),
        "trading_dates": [value.isoformat() for value in trading_dates],
        "unavailable_dates": unavailable_dates,
        "persistence_counts": persistence_counts,
        "replaced_existing_sector_rows": len(original_history) - len(preserved_history),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run #305 TOPIX-17 sector canonical persistence")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--as-of", help="Confirmed trading date (YYYY-MM-DD)")
    mode.add_argument("--backfill-start", help="Historical backfill start date (YYYY-MM-DD)")
    parser.add_argument("--backfill-end", help="Historical backfill end date (YYYY-MM-DD)")
    parser.add_argument("--backfill-range", default="2y")
    parser.add_argument("--history", type=Path, default=Path("data/generated/public/money-flow/sector-history.jsonl"))
    parser.add_argument("--sector-config", type=Path, default=Path("data/config/money-flow-sector-v1.json"))
    parser.add_argument("--detector-config", type=Path, default=Path("data/config/money-flow-detector-v1.json"))
    args = parser.parse_args()

    common = {
        "history_path": args.history,
        "sector_config_path": args.sector_config,
        "detector_config_path": args.detector_config,
    }
    if args.backfill_start:
        if not args.backfill_end:
            raise SectorCanonicalRunError("--backfill-end is required with --backfill-start")
        result = run_backfill(
            start=date.fromisoformat(args.backfill_start),
            end=date.fromisoformat(args.backfill_end),
            history_range=args.backfill_range,
            **common,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if not result["unavailable_dates"] else 3

    result = run_once(as_of=date.fromisoformat(args.as_of), **common)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["snapshot_set"].get("persistable") else 3


if __name__ == "__main__":
    raise SystemExit(main())
