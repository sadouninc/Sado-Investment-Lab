from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Callable

from scripts.money_flow_canonical_run import DEFAULT_THEME_ID, run_once
from scripts.money_flow_sector_adapter import _series, fetch_yahoo_history
from scripts.money_flow_theme_adapter import load_theme_config

Fetcher = Callable[[str, str, str], dict[str, Any]]


def _latest_date(payload: dict[str, Any], symbol: str) -> str:
    series = _series(payload, symbol)
    return str(series[-1]["date"])


def market_session_guard(
    *,
    as_of: date,
    theme_id: str,
    theme_config: dict[str, Any],
    fetcher: Fetcher = fetch_yahoo_history,
) -> dict[str, Any]:
    """Verify the requested day has fresh benchmark/member market data.

    Scheduled runs execute on weekdays, but Japanese exchange holidays still occur.
    A holiday must not be persisted as a new detector day using the prior session's
    prices. Fetch errors remain explicit unavailable inputs; they are not converted
    to COLD/zero signals.
    """

    benchmark = theme_config.get("benchmark") or {}
    benchmark_symbol = str(benchmark.get("symbol") or "").strip()
    if not benchmark_symbol:
        raise ValueError("benchmark.symbol is required")

    themes = [row for row in theme_config.get("themes") or [] if str(row.get("id")) == theme_id]
    if len(themes) != 1:
        raise ValueError(f"theme config must contain exactly one {theme_id}")
    theme = themes[0]
    range_ = str(theme_config.get("history_range") or "6mo")
    interval = str(theme_config.get("interval") or "1d")
    requested = as_of.isoformat()

    try:
        benchmark_date = _latest_date(fetcher(benchmark_symbol, range_, interval), benchmark_symbol)
    except Exception as exc:
        return {
            "ready": False,
            "reason": "BENCHMARK_UNAVAILABLE",
            "requested_as_of": requested,
            "benchmark_as_of": None,
            "member_as_of": {},
            "unavailable_members": [],
            "error": exc.__class__.__name__,
        }

    member_dates: dict[str, str] = {}
    unavailable_members: list[str] = []
    for member in theme.get("members") or []:
        code = str(member.get("security_code") or "").strip()
        symbol = str(member.get("symbol") or "").strip()
        if not code or not symbol:
            raise ValueError("theme member security_code/symbol are required")
        try:
            member_dates[code] = _latest_date(fetcher(symbol, range_, interval), symbol)
        except Exception:
            unavailable_members.append(code)

    if benchmark_date != requested:
        return {
            "ready": False,
            "reason": "MARKET_SESSION_NOT_CURRENT",
            "requested_as_of": requested,
            "benchmark_as_of": benchmark_date,
            "member_as_of": member_dates,
            "unavailable_members": unavailable_members,
        }

    stale_members = sorted(code for code, value in member_dates.items() if value != requested)
    current_members = sorted(code for code, value in member_dates.items() if value == requested)
    if stale_members:
        return {
            "ready": False,
            "reason": "MEMBER_MARKET_DATA_STALE",
            "requested_as_of": requested,
            "benchmark_as_of": benchmark_date,
            "member_as_of": member_dates,
            "stale_members": stale_members,
            "unavailable_members": unavailable_members,
        }
    if not current_members:
        return {
            "ready": False,
            "reason": "ALL_MEMBERS_UNAVAILABLE",
            "requested_as_of": requested,
            "benchmark_as_of": benchmark_date,
            "member_as_of": member_dates,
            "unavailable_members": unavailable_members,
        }

    return {
        "ready": True,
        "reason": "CURRENT_MARKET_SESSION",
        "requested_as_of": requested,
        "benchmark_as_of": benchmark_date,
        "member_as_of": member_dates,
        "unavailable_members": unavailable_members,
    }


def run_scheduled(
    *,
    as_of: date,
    history_path: Path,
    theme_config_path: Path,
    sector_config_path: Path,
    detector_config_path: Path,
    theme_id: str = DEFAULT_THEME_ID,
    fetcher: Fetcher = fetch_yahoo_history,
) -> dict[str, Any]:
    theme_config = load_theme_config(theme_config_path)
    guard = market_session_guard(
        as_of=as_of,
        theme_id=theme_id,
        theme_config=theme_config,
        fetcher=fetcher,
    )
    if not guard["ready"]:
        return {"status": "SKIPPED", "guard": guard, "result": None}

    result = run_once(
        as_of=as_of,
        history_path=history_path,
        theme_config_path=theme_config_path,
        sector_config_path=sector_config_path,
        detector_config_path=detector_config_path,
        theme_id=theme_id,
        fetcher=fetcher,
    )
    return {"status": "COMPLETED", "guard": guard, "result": result}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Money Flow canonical snapshot only for a current market session")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--theme-id", default=DEFAULT_THEME_ID)
    parser.add_argument("--history", default="data/generated/public/money-flow/history.jsonl")
    parser.add_argument("--themes", default="data/config/money-flow-themes-v1.json")
    parser.add_argument("--sector", default="data/config/money-flow-sector-v1.json")
    parser.add_argument("--detector", default="data/config/money-flow-detector-v1.json")
    args = parser.parse_args()

    output = run_scheduled(
        as_of=date.fromisoformat(args.as_of),
        history_path=Path(args.history),
        theme_config_path=Path(args.themes),
        sector_config_path=Path(args.sector),
        detector_config_path=Path(args.detector),
        theme_id=args.theme_id,
    )
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
