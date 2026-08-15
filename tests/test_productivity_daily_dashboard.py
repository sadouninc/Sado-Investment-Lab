from __future__ import annotations

from datetime import datetime, timezone
import unittest

from scripts.productivity_daily_dashboard import MARKER, render_markdown, summarize


class ProductivityDailyDashboardTest(unittest.TestCase):
    def test_jst_boundary_and_pr_exclusion(self):
        now = datetime(2026, 8, 15, 14, 30, tzinfo=timezone.utc)  # 23:30 JST
        items = [
            {
                "created_at": "2026-08-14T15:30:00Z",  # 8/15 00:30 JST
                "closed_at": "2026-08-15T01:00:00Z",
                "pull_request": {"url": "https://example.test/pr/1"},
            },
            {
                "created_at": "2026-08-14T14:59:59Z",  # 8/14 23:59:59 JST
                "closed_at": "2026-08-14T15:01:00Z",  # 8/15 00:01 JST
            },
        ]

        result = summarize(items, now=now, days=2)
        by_date = {row["date"]: row for row in result["rows"]}

        self.assertEqual(1, by_date["2026-08-15"]["pr_created"])
        self.assertEqual(0, by_date["2026-08-15"]["issue_created"])
        self.assertEqual(1, by_date["2026-08-15"]["issue_closed"])
        self.assertEqual(1, by_date["2026-08-14"]["issue_created"])
        self.assertEqual(0, by_date["2026-08-14"]["pr_created"])

    def test_pr_close_is_not_counted_as_issue_close(self):
        now = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
        items = [
            {
                "created_at": "2026-08-15T01:00:00Z",
                "closed_at": "2026-08-15T02:00:00Z",
                "pull_request": {"url": "https://example.test/pr/2"},
            }
        ]
        result = summarize(items, now=now, days=1)
        row = result["rows"][0]
        self.assertEqual(1, row["pr_created"])
        self.assertEqual(0, row["issue_created"])
        self.assertEqual(0, row["issue_closed"])

    def test_markdown_contains_graph_table_and_marker(self):
        now = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
        result = summarize([], now=now, days=2)
        markdown = render_markdown(result)
        self.assertIn(MARKER, markdown)
        self.assertIn("xychart-beta", markdown)
        self.assertIn("PR発行数 / 日", markdown)
        self.assertIn("Issue Close数 / 日", markdown)
        self.assertIn("2026-08-15", markdown)
        self.assertIn("件数の最大化自体を生産性の目的にはしません", markdown)


if __name__ == "__main__":
    unittest.main()
