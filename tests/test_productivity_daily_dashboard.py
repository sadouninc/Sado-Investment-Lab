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
                "merged_at": "2026-08-15T02:00:00Z",  # 8/15 11:00 JST
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
        self.assertEqual(1, by_date["2026-08-15"]["pr_merged"])
        self.assertEqual(1, by_date["2026-08-14"]["issue_created"])
        self.assertEqual(0, by_date["2026-08-14"]["pr_created"])

    def test_pr_close_is_not_counted_as_issue_close(self):
        now = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
        items = [
            {
                "created_at": "2026-08-15T01:00:00Z",
                "closed_at": "2026-08-15T02:00:00Z",
                "merged_at": "2026-08-15T03:00:00Z",
                "pull_request": {"url": "https://example.test/pr/2"},
            }
        ]
        result = summarize(items, now=now, days=1)
        row = result["rows"][0]
        self.assertEqual(1, row["pr_created"])
        self.assertEqual(0, row["issue_created"])
        self.assertEqual(0, row["issue_closed"])

        self.assertEqual(1, row["pr_merged"])
    def test_markdown_contains_graph_table_and_marker(self):
        now = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
        result = summarize([], now=now, days=2)
        markdown = render_markdown(result)
        self.assertIn(MARKER, markdown)
        self.assertIn("xychart-beta", markdown)
        self.assertIn("PR発行 / 日", markdown)
        self.assertIn("PR Merge / 日", markdown)
        self.assertIn("Issue Close / 日", markdown)
        self.assertIn("2026-08-15", markdown)
        self.assertIn("件数の最大化自体を生産性の目的にはしません", markdown)

    def test_merged_at_jst_boundary(self):
        """Test that PR merged_at is correctly bucketed to JST date."""
        now = datetime(2026, 8, 16, 10, 0, tzinfo=timezone.utc)
        items = [
            {
                "created_at": "2026-08-15T00:00:00Z",
                "merged_at": "2026-08-15T14:59:59Z",  # 8/15 23:59:59 JST
                "pull_request": {"url": "https://example.test/pr/3"},
            },
            {
                "created_at": "2026-08-15T00:00:00Z",
                "merged_at": "2026-08-15T15:00:00Z",  # 8/16 00:00:00 JST
                "pull_request": {"url": "https://example.test/pr/4"},
            },
        ]
        result = summarize(items, now=now, days=2)
        by_date = {row["date"]: row for row in result["rows"]}
        
        self.assertEqual(1, by_date["2026-08-15"]["pr_merged"])
        self.assertEqual(1, by_date["2026-08-16"]["pr_merged"])

    def test_pr_merged_excluded_from_issue_close(self):
        """Test that PR merge does not increment issue_closed count."""
        now = datetime(2026, 8, 16, 10, 0, tzinfo=timezone.utc)
        items = [
            {
                "created_at": "2026-08-16T00:00:00Z",
                "closed_at": "2026-08-16T02:00:00Z",
                "merged_at": "2026-08-16T02:00:00Z",
                "pull_request": {"url": "https://example.test/pr/5"},
            },
            {
                "created_at": "2026-08-16T00:00:00Z",
                "closed_at": "2026-08-16T03:00:00Z",
            },
        ]
        result = summarize(items, now=now, days=1)
        row = result["rows"][0]
        
        self.assertEqual(1, row["pr_merged"])
        self.assertEqual(1, row["issue_closed"])
        self.assertEqual(1, row["issue_created"])
        self.assertEqual(0, row["issue_net_change"])

    def test_7d_comparison_with_percentage(self):
        """Test 7d-vs-previous-7d totals/deltas with percentage calculation."""
        now = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
        items = []
        # Previous 7 days (8/7-8/13): 2 PRs created, 1 merged
        for day in range(7, 14):
            items.append({"created_at": f"2026-08-{day:02d}T01:00:00Z", "pull_request": {}})
            if day == 10:
                items.append({"created_at": f"2026-08-{day:02d}T02:00:00Z", "pull_request": {}})
        items.append({"created_at": "2026-08-10T03:00:00Z", "merged_at": "2026-08-10T04:00:00Z", "pull_request": {}})
        
        # Recent 7 days (8/14-8/20): 4 PRs created, 2 merged
        for day in range(14, 21):
            items.append({"created_at": f"2026-08-{day:02d}T01:00:00Z", "pull_request": {}})
            if day < 17:
                items.append({"created_at": f"2026-08-{day:02d}T02:00:00Z", "pull_request": {}})
        for day in range(15, 17):
            items.append({"created_at": f"2026-08-{day:02d}T03:00:00Z", "merged_at": f"2026-08-{day:02d}T04:00:00Z", "pull_request": {}})
        
        result = summarize(items, now=now, days=14)
        markdown = render_markdown(result)
        
        self.assertIn("直近7日 vs 前7日", markdown)
        # Check that the comparison table exists
        self.assertIn("直近7日", markdown)
        self.assertIn("前7日", markdown)
        self.assertIn("差分", markdown)
        self.assertIn("変化率", markdown)

    def test_percentage_na_for_zero_denominator(self):
        """Test that percentage shows N/A when previous period is zero."""
        now = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
        items = [{"created_at": "2026-08-15T01:00:00Z", "pull_request": {}}]
        result = summarize(items, now=now, days=14)
        markdown = render_markdown(result)
        
        self.assertIn("N/A", markdown)

if __name__ == "__main__":
    unittest.main()
