from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote
from urllib.request import Request, urlopen

from scripts.money_flow_detector import evaluate_snapshot, load_config as load_detector_config

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={range_}&interval={interval}"
Fetcher = Callable[[str, str, str], dict[str, Any]]


class SectorAdapterError(ValueError):
    pass


def load_sector_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config.get("sectors"), list) or not config["sectors"]:
        raise SectorAdapterError("sectors must be a non-empty list")
    benchmark = config.get("benchmark") or {}
    if not benchmark.get("symbol"):
        raise SectorAdapterError("benchmark.symbol is required")
    windows = config.get("windows") or {}
    for key in ("short", "medium", "long", "activity_short", "activity_baseline"):
        if not isinstance(windows.get(key), int) or windows[key] < 1:
            raise SectorAdapterError(f"windows.{key} must be a positive integer")
    return config


def fetch_yahoo_history(symbol: str, range_: str, interval: str, *, timeout: int = 20) -> dict[str, Any]:
    url = YAHOO_CHART.format(symbol=quote(symbol, safe=""), range_=range_, interval=interval)
    request = Request(url, headers={"User-Agent": "Sado-Investment-Lab/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _series(payload: dict[str, Any], symbol: str) -> dict[str, list[float]]:
    results = ((payload.get("chart") or {}).get("result") or [])
    if not results:
        raise SectorAdapterError(f"no chart result for {symbol}")
    chart = results[0]
    quote_data = (((chart.get("indicators") or {}).get("quote") or [{}])[0])
    closes = quote_data.get("close") or []
    volumes = quote_data.get("volume") or []
    aligned = [(float(c), float(v) if v is not None else math.nan) for c, v in zip(closes, volumes) if c is not None]
    if not aligned:
        raise SectorAdapterError(f"no close values for {symbol}")
    return {
        "close": [item[0] for item in aligned],
        "volume": [item[1] for item in aligned],
    }


def _return(values: list[float], days: int) -> float | None:
    if len(values) <= days or values[-days - 1] == 0:
        return None
    return (values[-1] / values[-days - 1] - 1.0) * 100.0


def _avg(values: list[float], count: int) -> float | None:
    clean = [v for v in values[-count:] if not math.isnan(v)]
    return sum(clean) / len(clean) if clean else None


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def _score_or_none(value: float | None, *, center: float, scale: float) -> float | None:
    return None if value is None else _clamp(center + value * scale)


def derive_sector_scores(
    sector: dict[str, list[float]], benchmark: dict[str, list[float]], *, config: dict[str, Any]
) -> tuple[dict[str, float | None], list[str], dict[str, Any]]:
    windows = config["windows"]
    scoring = config["scoring"]
    short = int(windows["short"])
    medium = int(windows["medium"])
    long = int(windows["long"])

    sector_returns = {k: _return(sector["close"], d) for k, d in (("short", short), ("medium", medium), ("long", long))}
    bench_returns = {k: _return(benchmark["close"], d) for k, d in (("short", short), ("medium", medium), ("long", long))}
    relative = {
        key: (sector_returns[key] - bench_returns[key])
        if sector_returns[key] is not None and bench_returns[key] is not None
        else None
        for key in sector_returns
    }

    available_relative = [relative[k] for k in ("short", "medium", "long") if relative[k] is not None]
    relative_level = sum(available_relative) / len(available_relative) if available_relative else None
    acceleration_raw = None
    if relative["short"] is not None and relative["medium"] is not None and relative["long"] is not None:
        acceleration_raw = ((relative["short"] - relative["medium"]) + (relative["medium"] - relative["long"])) / 2.0

    activity_short = _avg(sector["volume"], int(windows["activity_short"]))
    activity_baseline = _avg(sector["volume"], int(windows["activity_baseline"]))
    activity_ratio = None
    if activity_short is not None and activity_baseline not in (None, 0):
        activity_ratio = activity_short / activity_baseline

    heat_raw = sector_returns["medium"]
    scores = {
        "relative_strength": _score_or_none(
            relative_level,
            center=50.0,
            scale=float(scoring["relative_strength_points_per_pct"]),
        ),
        "activity": None if activity_ratio is None else _clamp(50.0 + (activity_ratio - 1.0) * float(scoring["activity_points_per_ratio"])),
        "breadth": None,
        "heat": _score_or_none(heat_raw, center=50.0, scale=float(scoring["heat_points_per_pct"])),
        "acceleration": _score_or_none(
            acceleration_raw,
            center=50.0,
            scale=float(scoring["acceleration_points_per_pct"]),
        ),
    }
    evidence = [
        f"relative_return_{short}d={relative['short']:.2f}%" if relative["short"] is not None else f"relative_return_{short}d=missing",
        f"relative_return_{medium}d={relative['medium']:.2f}%" if relative["medium"] is not None else f"relative_return_{medium}d=missing",
        f"relative_return_{long}d={relative['long']:.2f}%" if relative["long"] is not None else f"relative_return_{long}d=missing",
        f"activity_ratio={activity_ratio:.3f}" if activity_ratio is not None else "activity_ratio=missing",
        "breadth unavailable from single sector ETF proxy; preserved as null",
    ]
    metrics = {
        "sector_returns_pct": sector_returns,
        "benchmark_returns_pct": bench_returns,
        "relative_returns_pct": relative,
        "activity_ratio": activity_ratio,
        "proxy_breadth_available": False,
    }
    return scores, evidence, metrics


def build_sector_snapshots(
    *,
    sector_config: dict[str, Any],
    detector_config: dict[str, Any],
    as_of: date,
    fetcher: Fetcher = fetch_yahoo_history,
    previous: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    previous = previous or {}
    range_ = str(sector_config.get("history_range") or "6mo")
    interval = str(sector_config.get("interval") or "1d")
    benchmark_spec = sector_config["benchmark"]
    benchmark_symbol = str(benchmark_spec["symbol"])
    benchmark_series = _series(fetcher(benchmark_symbol, range_, interval), benchmark_symbol)

    snapshots: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for spec in sector_config["sectors"]:
        sector_id = str(spec.get("id") or "").strip()
        name = str(spec.get("name") or "").strip()
        symbol = str(spec.get("symbol") or "").strip()
        if not sector_id or not name or not symbol:
            raise SectorAdapterError("sector id/name/symbol are required")
        try:
            series = _series(fetcher(symbol, range_, interval), symbol)
            scores, source_evidence, metrics = derive_sector_scores(series, benchmark_series, config=sector_config)
            prior = previous.get(sector_id) or {}
            raw = {
                "id": sector_id,
                "name": name,
                "kind": "SECTOR",
                "scores": scores,
                "previous_state": prior.get("state", "COLD"),
                "prior_target_state": prior.get("target_state"),
                "target_streak": prior.get("target_streak", 0),
                "state_since": prior.get("state_since", as_of.isoformat()),
                "member_count": 0,
                "membership_as_of": None,
            }
            snapshot = evaluate_snapshot(raw, config=detector_config, as_of=as_of)
            snapshot["sector_taxonomy"] = sector_config.get("taxonomy")
            snapshot["proxy_symbol"] = symbol
            snapshot["benchmark"] = {"name": benchmark_spec.get("name"), "symbol": benchmark_symbol}
            snapshot["source"] = "Yahoo Finance chart endpoint"
            snapshot["source_metrics"] = metrics
            snapshot["evidence"] = source_evidence + snapshot["evidence"]
            snapshots.append(snapshot)
        except Exception as exc:
            failures.append({"id": sector_id, "symbol": symbol, "reason": exc.__class__.__name__})

    return {
        "schema_version": 1,
        "as_of": as_of.isoformat(),
        "taxonomy": sector_config.get("taxonomy"),
        "benchmark": benchmark_spec,
        "sectors": snapshots,
        "coverage": {
            "requested": len(sector_config["sectors"]),
            "available": len(snapshots),
            "missing": failures,
        },
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build #112 TOPIX-17 sector money-flow snapshots")
    parser.add_argument("--sector-config", type=Path, default=Path("data/config/money-flow-sector-v1.json"))
    parser.add_argument("--detector-config", type=Path, default=Path("data/config/money-flow-detector-v1.json"))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/generated/public/money-flow-sectors.json"))
    args = parser.parse_args()

    previous: dict[str, dict[str, Any]] = {}
    if args.previous and args.previous.is_file():
        payload = json.loads(args.previous.read_text(encoding="utf-8"))
        previous = {row["id"]: row for row in payload.get("sectors", []) if isinstance(row, dict) and row.get("id")}
    result = build_sector_snapshots(
        sector_config=load_sector_config(args.sector_config),
        detector_config=load_detector_config(args.detector_config),
        as_of=date.fromisoformat(args.as_of),
        previous=previous,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Money Flow sectors: {result['coverage']['available']}/{result['coverage']['requested']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
