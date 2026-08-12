from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
VIEW = ROOT / "06_Research" / "Architecture" / "SADO_INVESTMENT_CODEX_SITEMAP_VIEW.md"


class CodexSitemapPagesViewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = VIEW.read_text(encoding="utf-8")

    def test_reuses_shared_design_system_without_inline_theme(self) -> None:
        self.assertIn('class="codex-page-shell"', self.text)
        self.assertIn('class="codex-status-chip"', self.text)
        self.assertIn('class="codex-disclosure"', self.text)
        self.assertNotIn("<style", self.text.lower())

    def test_first_view_answers_now_next_later(self) -> None:
        self.assertIn("いまどこまで出来ている？", self.text)
        self.assertIn("次に何を作る？", self.text)
        self.assertIn("その先どこを育てる？", self.text)
        self.assertIn("#324 PR4", self.text)

    def test_contains_nine_stage_progressive_map(self) -> None:
        expected = [
            "1. Observe / 観測",
            "2. Discover / 発見",
            "3. Understand / 理解",
            "4. Hypothesize / 仮説",
            "5. Decide / 判断",
            "6. Act / 行動",
            "7. Record / 記録",
            "8. Learn / 振り返り",
            "9. Re-observe / 再観測",
        ]
        for label in expected:
            self.assertIn(label, self.text)

    def test_only_verified_live_routes_are_ctas(self) -> None:
        allowed = {
            "{{ '/' | relative_url }}",
            "{{ '/companies/' | relative_url }}",
            "{{ '/decision-cockpit/daihen/' | relative_url }}",
            "{{ '/risk-preflight/' | relative_url }}",
            "{{ '/trade-journal/' | relative_url }}",
        }
        hrefs = []
        for fragment in self.text.split('href="')[1:]:
            hrefs.append(fragment.split('"', 1)[0])
        self.assertTrue(hrefs)
        self.assertTrue(set(hrefs).issubset(allowed), hrefs)

    def test_authority_and_fail_closed_boundary_are_visible(self) -> None:
        self.assertIn("5249241479", self.text)
        self.assertIn("#320", self.text)
        self.assertIn("#314", self.text)
        self.assertIn("未確認routeはリンクにしません", self.text)
        self.assertIn("Canonical truthを複製する新しいAuthorityではありません", self.text)


if __name__ == "__main__":
    unittest.main()
