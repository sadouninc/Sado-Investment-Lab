from __future__ import annotations

import argparse
import copy
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.money_flow_detector import load_config as load_detector_config
from scripts.money_flow_history import load_history, upsert_snapshot
from scripts.money_flow_sector_adapter import _series, fetch_yahoo_history, load_sector_config
from scripts.money_flow_theme_adapter import build_theme_snapshots, load_theme_config

Fetcher = Callable[[str, str, str], dict[str, Any]]

DEFAULT_THEME_ID = "theme:ai-data-center-power-infrastructure"
DEFAULT_POLICY_T0 = date(2024, 10, 4)


class CanonicalRunError(ValueError):
    pass


class CachedFetcher:
    """Cache raw market payloads so historical backfill does not refetch every trading day."""

    def __init__(self, fetcher: Fetcher) -> None:
        self.fetcher = fetcher
        self.cache: dict[tuple[str, str, str], dict[str, Any]] = {}

    def __call__(self, symbol: str, range_: str, interval: str) -> dict[str, Any]:
        key = (symbol, range_, interval)
        if key not in self.cache:
            self.cache[key] = self.fetcher(symbol, range_, interval)
        return self.cache[key]


def _latest_previous(history: list[dict[str, Any]], *, as_of: date) -> dict[str, dict[str, Any]]:
    previous: dict[str, dict[str, Any]] = {}
    for row in history:
        if row.get("kind") != "THEME":
            continue
        row_date = date.fromisoformat(str(row["as_of"]))
        if row_date >= as_of:
            continue
        entity_id = str(row["id"])
        current = previous.get(entity_id)
        if current is None or str(current["as_of"]) < str(row["as_of"]):
            previous[entity_id] = row
    return previous


def _theme_config_entry(theme_config: dict[str, Any], theme_id: str) -> dict[str, Any]:
    matches = [row for row in theme_config.get("themes") or [] if str(row.get("id")) == theme_id]
    if len(matches) != 1:
        raise CanonicalRunError(f"theme config must contain exactly one {theme_id}")
    return matches[0]


def _trim_chart_payload(payload: dict[str, Any], *, as_of: date) -> dict[str, Any]:
    """Remove observations after as_of to prevent historical backfill from seeing future prices."""
    bounded = copy.deepcopy(payload)
    results = ((bounded.get("chart") or {}).get("result") or [])
    for result in results:
        timestamps = result.get("timestamp") or []
        keep = [
            index
            for index, timestamp in enumerate(timestamps)
            if datetime.fromtimestamp(float(timestamp), tz=timezone.utc).date() <= as_of
        ]
        result["timestamp"] = [timestamps[index] for index in keep]
        indicators = result.get("indicators") or {}
        for indicator_rows in indicators.values():
            if not isinstance(indicator_rows, list):
                continue
            for indicator in indicator_rows:
                if not isinstance(indicator, dict):
                    continue
                for key, values in list(indicator.items()):
                    if isinstance(values, list) and len(values) == len(timestamps):
                        indicator[key] = [values[index] for index in keep]
    return bounded


def bounded_fetcher(fetcher: Fetcher, *, as_of: date) -> Fetcher:
    def _fetch(symbol: str, range_: str, interval: str) -> dict[str, Any]:
        return _trim_chart_payload(fetcher(symbol, range_, interval), as_of=as_of)

    return _fetch


def canonical_snapshot(
    *,
    theme_id: str,
    as_of: date,
    theme_config: dict[str, Any],
    sector_config: dict[str, Any],
    detector_config: dict[str, Any],
    history: list[dict[str, Any]],
    fetcher: Fetcher = fetch_yahoo_history,
) -> dict[str, Any]:
    entry = _theme_config_entry(theme_config, theme_id)
    payload = build_theme_snapshots(
        theme_config=theme_config,
        sector_config=sector_config,
        detector_config=detector_config,
        as_of=as_of,
        fetcher=bounded_fetcher(fetcher, as_of=as_of),
        previous=_latest_previous(history, as_of=as_of),
    )
    matches = [row for row in payload.get("themes") or [] if str(row.get("id")) == theme_id]
    if not matches:
        coverage = payload.get("coverage") or {}
        return {
            "kind": "THEME",
            "id": theme_id,
            "name": str(entry.get("name") or theme_id),
            "as_of": as_of.isoformat(),
            "data_completeness": "UNAVAILABLE",
            "missing_reason": "all theme members unavailable",
            "coverage": coverage,
            "membership_as_of": entry.get("membership_as_of"),
            "membership_version": entry.get("membership_version"),
            "members": entry.get("members") or [],
            "persistable": False,
        }

    snapshot = dict(matches[0])
    snapshot["membership_version"] = entry.get("membership_version") or str(entry.get("membership_as_of"))
    snapshot["backfill_policy"] = entry.get("backfill_policy")
    completeness = str(snapshot.get("data_completeness") or "").upper()
    if completeness == "INSUFFICIENT":
        snapshot["data_completeness"] = "PARTIAL"
    snapshot["missing_reason"] = snapshot.get("missing_reason") or None
    snapshot["persistable"] = True
    return snapshot


def persist_canonical_snapshot(path: Path, snapshot: dict[str, Any]) -> str:
    if not snapshot.get("persistable"):
        return "NOT_PERSISTED_UNAVAILABLE"
    candidate = dict(snapshot)
    candidate.pop("persistable", None)
    return upsert_snapshot(path, candidate)


def first_state_date(history: list[dict[str, Any]], *, theme_id: str, state: str) -> str | None:
    target = state.upper()
    if target not in {"WARMING", "INFLOW"}:
        raise CanonicalRunError("state must be WARMING or INFLOW")
    dates = sorted(
        str(row["as_of"])
        for row in history
        if row.get("kind") == "THEME" and str(row.get("id")) == theme_id and row.get("state") == target
    )
    return dates[0] if dates else None


def evaluate_policy_lead_time(
    history: list[dict[str, Any]],
    *,
    theme_id: str = DEFAULT_THEME_ID,
    policy_t0: date = DEFAULT_POLICY_T0,
    retrospective_membership: bool = False,
) -> dict[str, Any]:
    warming = first_state_date(history, theme_id=theme_id, state="WARMING")
    inflow = first_state_date(history, theme_id=theme_id, state="INFLOW")

    def delta(value: str | None) -> int | None:
        return None if value is None else (date.fromisoformat(value) - policy_t0).days

    limitations: list[str] = []
    if retrospective_membership:
        limitations.append("RETROSPECTIVE_MEMBERSHIP")
    if warming is None:
        limitations.append("FIRST_WARMING_NOT_OBSERVED")
    if inflow is None:
        limitations.append("FIRST_INFLOW_NOT_OBSERVED")

    return {
        "theme_id": theme_id,
        "policy_t0": policy_t0.isoformat(),
        "first_warming_date": warming,
        "first_inflow_date": inflow,
        "policy_to_warming_days": delta(warming),
        "policy_to_inflow_days": delta(inflow),
        "limitations": limitations,
    }


def _with_history_range(theme_config: dict[str, Any], history_range_override: str | None) -> dict[str, Any]:
    if not history_range_override:
        return theme_config
    updated = copy.deepcopy(theme_config)
    updated["history_range"] = history_range_override
    return updated


def latest_market_date(
    *,
    theme_config: dict[str, Any],
    fetcher: Fetcher = fetch_yahoo_history,
    history_range_override: str | None = None,
) -> date:
    config = _with_history_range(theme_config, history_range_override)
    symbol = str((config.get("benchmark") or {}).get("symbol") or "")
    if not symbol:
        raise CanonicalRunError("benchmark.symbol is required")
    range_ = str(config.get("history_range") or "6mo")
    interval = str(config.get("interval") or "1d")
    rows = _series(fetcher(symbol, range_, interval), symbol)
    return date.fromisoformat(str(rows[-1]["date"]))


def _write_json(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_once(
    *,
    as_of: date,
    history_path: Path,
    theme_config_path: Path,
    sector_config_path: Path,
    detector_config_path: Path,
    theme_id: str = DEFAULT_THEME_ID,
    fetcher: Fetcher = fetch_yahoo_history,
    history_range_override: str | None = None,
    lead_time_output_path: Path | None = None,
) -> dict[str, Any]:
    history = load_history(history_path)
    theme_config = _with_history_range(load_theme_config(theme_config_path), history_range_override)
    sector_config = load_sector_config(sector_config_path)
    detector_config = load_detector_config(detector_config_path)
    snapshot = canonical_snapshot(
        theme_id=theme_id,
        as_of=as_of,
        theme_config=theme_config,
        sector_config=sector_config,
        detector_config=detector_config,
        history=history,
        fetcher=fetcher,
    )
    persistence = persist_canonical_snapshot(history_path, snapshot)
    updated_history = load_history(history_path)
    entry = _theme_config_entry(theme_config, theme_id)
    lead_time = evaluate_policy_lead_time(
        updated_history,
        theme_id=theme_id,
        retrospective_membership=(
            str(entry.get("backfill_policy") or "") == "RETROSPECTIVE_MEMBERSHIP_IF_HISTORICAL_MEMBERSHIP_UNAVAILABLE"
            and as_of < date.fromisoformat(str(entry["membership_as_of"]))
        ),
    )
    _write_json(lead_time_output_path, lead_time)
    return {"snapshot": snapshot, "persistence": persistence, "lead_time": lead_time}


def run_latest(
    *,
    history_path: Path,
    theme_config_path: Path,
    sector_config_path: Path,
    detector_config_path: Path,
    theme_id: str = DEFAULT_THEME_ID,
    fetcher: Fetcher = fetch_yahoo_history,
    lead_time_output_path: Path | None = None,
) -> dict[str, Any]:
    cached = CachedFetcher(fetcher)
    theme_config = load_theme_config(theme_config_path)
    as_of = latest_market_date(theme_config=theme_config, fetcher=cached)
    result = run_once(
        as_of=as_of,
        history_path=history_path,
        theme_config_path=theme_config_path,
        sector_config_path=sector_config_path,
        detector_config_path=detector_config_path,
        theme_id=theme_id,
        fetcher=cached,
        lead_time_output_path=lead_time_output_path,
    )
    result["resolved_market_date"] = as_of.isoformat()
    return result


def run_backfill(
    *,
    start: date,
    end: date,
    history_path: Path,
    theme_config_path: Path,
    sector_config_path: Path,
    detector_config_path: Path,
    theme_id: str = DEFAULT_THEME_ID,
    fetcher: Fetcher = fetch_yahoo_history,
    history_range: str = "2y",
    lead_time_output_path: Path | None = None,
) -> dict[str, Any]:
    if end < start:
        raise CanonicalRunError("backfill end must be on or after start")

    cached = CachedFetcher(fetcher)
    theme_config = _with_history_range(load_theme_config(theme_config_path), history_range)
    benchmark_symbol = str((theme_config.get("benchmark") or {}).get("symbol") or "")
    interval = str(theme_config.get("interval") or "1d")
    market_rows = _series(cached(benchmark_symbol, history_range, interval), benchmark_symbol)
    trading_dates = [
        date.fromisoformat(str(row["date"]))
        for row in market_rows
        if start <= date.fromisoformat(str(row["date"])) <= end
    ]
    if not trading_dates:
        raise CanonicalRunError("no benchmark trading dates in requested backfill window")

    counts: dict[str, int] = {}
    for as_of in trading_dates:
        result = run_once(
            as_of=as_of,
            history_path=history_path,
            theme_config_path=theme_config_path,
            sector_config_path=sector_config_path,
            detector_config_path=detector_config_path,
            theme_id=theme_id,
            fetcher=cached,
            history_range_override=history_range,
        )
        status = str(result["persistence"])
        counts[status] = counts.get(status, 0) + 1

    entry = _theme_config_entry(theme_config, theme_id)
    retrospective = (
        str(entry.get("backfill_policy") or "") == "RETROSPECTIVE_MEMBERSHIP_IF_HISTORICAL_MEMBERSHIP_UNAVAILABLE"
        and start < date.fromisoformat(str(entry["membership_as_of"]))
    )
    lead_time = evaluate_policy_lead_time(
        load_history(history_path),
        theme_id=theme_id,
        retrospective_membership=retrospective,
    )
    _write_json(lead_time_output_path, lead_time)
    return {
        "theme_id": theme_id,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "history_range": history_range,
        "trading_dates_processed": len(trading_dates),
        "persistence_counts": counts,
        "lead_time": lead_time,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run canonical Money Flow Theme snapshot")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--as-of")
    mode.add_argument("--latest-market-date", action="store_true")
    mode.add_argument("--backfill-start")
    parser.add_argument("--backfill-end")
    parser.add_argument("--backfill-range", default="2y")
    parser.add_argument("--theme-id", default=DEFAULT_THEME_ID)
    parser.add_argument("--history", default="data/generated/public/money-flow/history.jsonl")
    parser.add_argument("--lead-time-output", default="data/generated/public/money-flow/policy-lead-time-ai-dc.json")
    parser.add_argument("--themes", default="data/config/money-flow-themes-v1.json")
    parser.add_argument("--sector", default="data/config/money-flow-sector-v1.json")
    parser.add_argument("--detector", default="data/config/money-flow-detector-v1.json")
    args = parser.parse_args()

    common = {
        "history_path": Path(args.history),
        "theme_config_path": Path(args.themes),
        "sector_config_path": Path(args.sector),
        "detector_config_path": Path(args.detector),
        "theme_id": args.theme_id,
        "lead_time_output_path": Path(args.lead_time_output) if args.lead_time_output else None,
    }
    if args.latest_market_date:
        result = run_latest(**common)
    elif args.backfill_start:
        if not args.backfill_end:
            raise CanonicalRunError("--backfill-end is required with --backfill-start")
        result = run_backfill(
            start=date.fromisoformat(args.backfill_start),
            end=date.fromisoformat(args.backfill_end),
            history_range=args.backfill_range,
            **common,
        )
    else:
        result = run_once(as_of=date.fromisoformat(args.as_of), **common)

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
