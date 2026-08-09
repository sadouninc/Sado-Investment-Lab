from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / ".github" / "pages" / "build_ai_morning_reports.py"
SPEC = importlib.util.spec_from_file_location("build_ai_morning_reports", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


REPORT = """---
dataset_status: PARTIAL
model: gpt-5
---

# AI Morning Report

## 市場概況
- AI半導体は底堅い一方、金利上昇を警戒。

## リスク要因
- VIX上昇とイベント跨ぎに注意。

## 今日の戦略
- 押し目候補を優先し、追いかけ買いは避ける。

## 注目銘柄
- 4063 信越化学 / 5803 フジクラ
"""


class MorningReportCardTests(unittest.TestCase):
    def test_extracts_investment_summary_from_stable_sections(self):
        summary = MODULE.report_card_summary(REPORT)
        self.assertEqual(summary["market"], "AI半導体は底堅い一方、金利上昇を警戒。")
        self.assertEqual(summary["strategy"], "押し目候補を優先し、追いかけ買いは避ける。")
        self.assertEqual(summary["watch"], "4063 信越化学 / 5803 フジクラ")

    def test_card_detail_prioritizes_investment_content_over_api_diagnostics(self):
        detail = MODULE.card_detail(MODULE.report_card_summary(REPORT), "PARTIAL")
        self.assertIn("市場:", detail)
        self.assertIn("戦略:", detail)
        self.assertIn("注目:", detail)
        self.assertIn("Data quality: PARTIAL", detail)
        self.assertNotIn("gpt-5", detail)
        self.assertNotIn("tokens", detail.lower())

    def test_falls_back_to_risk_when_watch_section_is_missing(self):
        report = REPORT.replace("## 注目銘柄\n- 4063 信越化学 / 5803 フジクラ\n", "")
        detail = MODULE.card_detail(MODULE.report_card_summary(report), "OK")
        self.assertIn("リスク: VIX上昇とイベント跨ぎに注意。", detail)

    def test_build_keeps_api_diagnostics_on_detail_page_but_not_index_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_dir = root / "reports"
            diag_dir = root / "diagnostics"
            site = root / "site"
            report_dir.mkdir()
            diag_dir.mkdir()
            (report_dir / "2026-08-09.md").write_text(REPORT, encoding="utf-8")
            (diag_dir / "2026-08-09.json").write_text(
                '{"model":"gpt-5","total_tokens":1234,"dataset_status":"PARTIAL",'
                '"input_tokens":1000,"output_tokens":234,"execution_seconds":2.5,"
                'estimated_cost_usd":0.1,"cost_basis":"test"}',
                encoding="utf-8",
            )

            old_report_dir, old_diag_dir, old_site = MODULE.REPORT_DIR, MODULE.DIAG_DIR, MODULE.SITE
            try:
                MODULE.REPORT_DIR, MODULE.DIAG_DIR, MODULE.SITE = report_dir, diag_dir, site
                MODULE.build()
            finally:
                MODULE.REPORT_DIR, MODULE.DIAG_DIR, MODULE.SITE = old_report_dir, old_diag_dir, old_site

            index = (site / "reports" / "morning" / "index.md").read_text(encoding="utf-8")
            detail = (site / "reports" / "morning" / "2026-08-09" / "index.md").read_text(encoding="utf-8")
            self.assertIn("AI半導体は底堅い", index)
            self.assertNotIn("gpt-5 / tokens", index)
            self.assertNotIn("tokens 1234", index)
            self.assertIn("## API Diagnostics", detail)
            self.assertIn("Model: `gpt-5`", detail)
            self.assertIn("Total tokens: `1234`", detail)


if __name__ == "__main__":
    unittest.main()
