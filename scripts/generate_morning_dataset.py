#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.morning_dataset.generator import (
    build_dataset,
    build_dataset_from_providers,
    load_json_source,
    write_dataset,
)
from scripts.morning_dataset.providers import (
    CapitalProvider,
    CandidateSelectorProvider,
    CandidatesProvider,
    EventsProvider,
    JsonFileProvider,
    MarketProvider,
    PortfolioProvider,
    SectorRotationProvider,
    WatchlistProvider,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Morning Dataset v1")
    parser.add_argument("--as-of", help="explicit dataset date YYYY-MM-DD; scheduled jobs should pass JST date")
    parser.add_argument("--market")
    parser.add_argument("--live-market", action="store_true", help="collect the public market snapshot via MarketProvider")
    parser.add_argument("--portfolio")
    parser.add_argument("--repo-portfolio", action="store_true", help="collect portfolio from data/portfolio/current.json")
    parser.add_argument("--capital")
    parser.add_argument("--repo-capital", action="store_true", help="collect latest capital snapshot from repository history.db")
    parser.add_argument("--candidates")
    parser.add_argument("--repo-candidates", action="store_true", help="collect latest legacy candidate snapshot from repository history.db")
    parser.add_argument(
        "--selector-candidates",
        action="store_true",
        help="collect the existing #108 Candidate Selector snapshot from data/generated/public/candidate-selector.json",
    )
    parser.add_argument("--investor-dna")
    parser.add_argument("--events")
    parser.add_argument("--repo-events", action="store_true", help="collect events from repository data/events/calendar.json")
    parser.add_argument("--watchlist")
    parser.add_argument("--repo-watchlist", action="store_true", help="collect active watch items from repository Current_Status.md Current Focus")
    parser.add_argument(
        "--repo-sector-rotation",
        action="store_true",
        help="collect the latest canonical TOPIX-17 Sector rotation from sector-history.jsonl",
    )
    parser.add_argument("--output", default="data/generated/public/morning-dataset.json")
    args = parser.parse_args()

    try:
        target_date = date.fromisoformat(args.as_of) if args.as_of else date.today()
    except ValueError:
        parser.error("--as-of must be YYYY-MM-DD")

    if args.live_market and args.market:
        parser.error("--live-market and --market are mutually exclusive")
    if args.repo_portfolio and args.portfolio:
        parser.error("--repo-portfolio and --portfolio are mutually exclusive")
    if args.repo_capital and args.capital:
        parser.error("--repo-capital and --capital are mutually exclusive")
    if sum(bool(value) for value in (args.repo_candidates, args.selector_candidates, args.candidates)) > 1:
        parser.error("--repo-candidates, --selector-candidates and --candidates are mutually exclusive")
    if args.repo_events and args.events:
        parser.error("--repo-events and --events are mutually exclusive")
    if args.repo_watchlist and args.watchlist:
        parser.error("--repo-watchlist and --watchlist are mutually exclusive")

    source_paths = {
        "market": args.market,
        "portfolio": args.portfolio,
        "capital": args.capital,
        "candidates": args.candidates,
        "investor_dna": args.investor_dna,
        "events": args.events,
        "watchlist": args.watchlist,
    }

    if (
        args.live_market
        or args.repo_portfolio
        or args.repo_capital
        or args.repo_candidates
        or args.selector_candidates
        or args.repo_events
        or args.repo_watchlist
        or args.repo_sector_rotation
    ):
        providers = []
        if args.live_market:
            providers.append(MarketProvider())
        if args.repo_portfolio:
            providers.append(PortfolioProvider(Path("data/portfolio/current.json"), today=target_date))
        if args.repo_capital:
            providers.append(CapitalProvider(Path("data/database/history.db"), today=target_date))
        if args.repo_candidates:
            providers.append(CandidatesProvider(Path("data/database/history.db"), today=target_date))
        if args.selector_candidates:
            providers.append(
                CandidateSelectorProvider(
                    Path("data/generated/public/candidate-selector.json"),
                    today=target_date,
                )
            )
        if args.repo_events:
            providers.append(EventsProvider(Path("data/events/calendar.json"), today=target_date))
        if args.repo_watchlist:
            providers.append(WatchlistProvider(Path("Current_Status.md"), today=target_date))
        if args.repo_sector_rotation:
            providers.append(SectorRotationProvider())
        providers.extend(
            JsonFileProvider(name, Path(path))
            for name, path in source_paths.items()
            if path
            and not (name == "market" and args.live_market)
            and not (name == "portfolio" and args.repo_portfolio)
            and not (name == "capital" and args.repo_capital)
            and not (name == "candidates" and (args.repo_candidates or args.selector_candidates))
            and not (name == "events" and args.repo_events)
            and not (name == "watchlist" and args.repo_watchlist)
        )
        dataset = build_dataset_from_providers(providers, as_of=target_date)
    else:
        def read(value: str | None):
            return load_json_source(Path(value)) if value else None

        dataset = build_dataset(
            as_of=target_date,
            market=read(args.market),
            portfolio=read(args.portfolio),
            capital=read(args.capital),
            candidates=read(args.candidates),
            investor_dna=read(args.investor_dna),
            events=read(args.events),
            watchlist=read(args.watchlist),
        )

    path = write_dataset(dataset, Path(args.output))
    print(f"Morning Dataset: {path}")
    quality = dataset.get("data_quality") or {}
    print(f"Completeness: {quality.get('completeness_count', quality.get('completeness_label', 'unknown'))} / status={quality.get('status', 'unknown')}")


if __name__ == "__main__":
    main()
