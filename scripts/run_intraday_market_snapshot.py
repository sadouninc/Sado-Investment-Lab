from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.intraday_market_snapshot import (
    SESSION_SLOTS,
    build_snapshot,
    load_morning,
    load_previous,
    persist_snapshot,
)
from scripts.japan_market_calendar import is_japan_market_business_day
from scripts.morning_dataset.providers.market import MarketProvider

JST = ZoneInfo("Asia/Tokyo")
DEFAULT_ROOT = Path("data/generated/intraday-market")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect one #444 intraday market snapshot")
    parser.add_argument("--session-slot", required=True, choices=SESSION_SLOTS)
    parser.add_argument("--business-date", help="YYYY-MM-DD; defaults to current JST date")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    observed_at = datetime.now(JST)
    business_date = date.fromisoformat(args.business_date) if args.business_date else observed_at.date()

    if not is_japan_market_business_day(business_date):
        print(f"skipped_non_business_day={business_date.isoformat()}")
        return 0

    result = MarketProvider().collect()
    previous = load_previous(args.output_root, business_date, args.session_slot)
    morning = load_morning(args.output_root, business_date)
    snapshot = build_snapshot(
        result,
        business_date=business_date,
        session_slot=args.session_slot,
        observed_at=observed_at,
        previous=previous,
        morning=morning,
    )
    paths = persist_snapshot(args.output_root, snapshot)
    print(f"identity={snapshot['identity']}")
    print(f"source_status={snapshot['source_status']}")
    print(f"history={paths.history}")
    print(f"latest={paths.latest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
