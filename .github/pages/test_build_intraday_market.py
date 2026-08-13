from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

PAGES = Path(__file__).resolve().parent
if str(PAGES) not in sys.path:
    sys.path.insert(0, str(PAGES))

import build_intraday_market as intraday


class IntradayMarketPageTests(unittest.TestCase):
    def test_missing_snapshot_fails_closed(self) -> None:
        page = intraday.render_page(None)
        self.assertIn("Market freshness: MISSING", page)
        self.assertIn("未取得を正常・最新とは扱いません", page)
        self.assertNotIn("Review Required: YES", page)

    def test_ok_snapshot_prioritizes_morning_delta_then_review(self) -> None:
        snapshot = {
            "identity": "2026-08-13:AFTERNOON",
            "business_date": "2026-08-13",
            "session_slot": "AFTERNOON",
            "observed_at": "2026-08-13T14:01:00+09:00",
            "source_timestamp": "2026-08-13T13:59:00+09:00",
            "source_status": "OK",
            "meaningful_delta": True,
            "review_reasons": ["TOPIX_MOVE"],
            "delta_from_morning": {
                "base_identity": "2026-08-13:MORNING",
                "fields": {
                    "indices.topix": {
                        "before": 3000.0,
                        "current": 3030.0,
                        "absolute": 30.0,
                        "pct": 1.0,
                    }
                },
            },
            "delta_from_previous": None,
        }
        page = intraday.render_page(snapshot)
        self.assertLess(page.index("MORNING → CURRENT"), page.index("REVIEW REQUIRED"))
        self.assertIn("Review Required: YES", page)
        self.assertIn("TOPIX_MOVE", page)
        self.assertIn("これはBUY / SELL / HOLDの推奨ではありません", page)

    def test_non_ok_source_blocks_delta_and_review(self) -> None:
        snapshot = {
            "identity": "2026-08-13:MIDDAY",
            "business_date": "2026-08-13",
            "session_slot": "MIDDAY",
            "observed_at": "2026-08-13T11:40:00+09:00",
            "source_timestamp": "2026-08-12T15:00:00+09:00",
            "source_status": "STALE",
            "meaningful_delta": True,
            "review_reasons": ["SHOULD_NOT_TRIGGER"],
            "delta_from_morning": {
                "fields": {
                    "indices.topix": {"before": 3000.0, "current": 3030.0, "pct": 1.0}
                }
            },
            "delta_from_previous": None,
        }
        page = intraday.render_page(snapshot)
        self.assertIn("差分表示をブロックしています", page)
        self.assertIn("Review Required: NO", page)
        self.assertIn("DATA_QUALITY_BLOCKED", page)


if __name__ == "__main__":
    unittest.main()
