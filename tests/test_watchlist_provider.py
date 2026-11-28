from __future__ import annotations

from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.morning_dataset.providers.watchlist import WatchlistProvider


class WatchlistProviderTest(unittest.TestCase):
    def write(self, root: str, content: str) -> Path:
        path = Path(root) / "Current_Status.md"
        path.write_text(content, encoding="utf-8")
        return path

    def test_collects_current_focus_without_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, """# Current Status
> 最終更新: 2026-08-08

## Current Focus
> as_of: 2026-08-08

- 信越化学の決算
- 原子力
- テラドローンの需給と事前エントリー条件

## TODO
- [ ] something
""")
            result = WatchlistProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("OK", result.status)
            self.assertEqual(3, len(result.data["items"]))
            self.assertEqual("信越化学の決算", result.data["items"][0]["text"])
            self.assertIsNone(result.data["items"][0]["security_code"])
            self.assertIsNone(result.data["items"][0]["priority"])

    def test_stale_source_preserves_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, """> 最終更新: 2026-08-01
## Current Focus
> as_of: 2026-08-01
- 送電網
""")
            result = WatchlistProvider(path, max_age_days=3, today=date(2026, 8, 8)).collect()
            self.assertEqual("STALE", result.status)
            self.assertEqual("送電網", result.data["items"][0]["text"])

    def test_future_dated_focus_is_partial_not_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, """> 最終更新: 2026-08-08
## Current Focus
> as_of: 2026-08-09
- 原子力
""")
            result = WatchlistProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertEqual("2026-08-09", result.as_of)
            self.assertIn("future", result.reason)
            self.assertEqual("原子力", result.data["items"][0]["text"])

    def test_future_dated_focus_precedes_malformed_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, """> 最終更新: 2026-08-08
## Current Focus
> as_of: 2026-08-09
- 原子力
malformed line
""")
            result = WatchlistProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertIn("future", result.reason)
            self.assertEqual("原子力", result.data["items"][0]["text"])

    def test_missing_section_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "> 最終更新: 2026-08-08\n## Portfolio\n- 信越化学\n")
            result = WatchlistProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)
            self.assertIsNone(result.data)

    def test_missing_update_date_is_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "## Current Focus\n- 原子力\n")
            result = WatchlistProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertEqual("原子力", result.data["items"][0]["text"])

    def test_fresh_global_date_does_not_make_undated_focus_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "> 最終更新: 2026-08-08\n## Current Focus\n- 原子力\n")
            result = WatchlistProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertIsNone(result.as_of)
            self.assertIn("no freshness date", result.reason)

    def test_old_section_date_wins_over_fresh_global_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "> 最終更新: 2026-08-08\n## Current Focus\n> as_of: 2026-08-01\n- 送電網\n")
            result = WatchlistProvider(path, max_age_days=3, today=date(2026, 8, 8)).collect()
            self.assertEqual("STALE", result.status)
            self.assertEqual("2026-08-01", result.as_of)

    def test_invalid_calendar_date_is_partial_without_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "## Current Focus\n> as_of: 2026-02-30\n- 原子力\n")
            result = WatchlistProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertIsNone(result.as_of)
            self.assertIn("invalid", result.reason)
            self.assertEqual("原子力", result.data["items"][0]["text"])

    def test_duplicate_or_conflicting_section_dates_are_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "## Current Focus\n> as_of: 2026-08-07\n> as_of: 2026-08-08\n- 原子力\n")
            result = WatchlistProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertIsNone(result.as_of)
            self.assertIn("duplicate or conflicting", result.reason)

    def test_invalid_utf8_is_missing_without_raw_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Current_Status.md"
            path.write_bytes(b"\xff\xfeprivate")
            result = WatchlistProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)
            self.assertIn("could not be read as UTF-8", result.reason)
            self.assertNotIn("private", result.reason)

    def test_read_error_is_missing_without_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "## Current Focus\n> as_of: 2026-08-08\n- 原子力\n")
            with patch.object(Path, "read_text", side_effect=OSError("sensitive path detail")):
                result = WatchlistProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)
            self.assertNotIn("sensitive", result.reason)

    def test_malformed_line_is_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "> 最終更新: 2026-08-08\n## Current Focus\n- 原子力\nplain text\n")
            result = WatchlistProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertEqual(1, len(result.data["items"]))


if __name__ == "__main__":
    unittest.main()

