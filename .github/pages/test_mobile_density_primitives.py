from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / ".github" / "pages" / "book.css"


class MobileDensityPrimitivesContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = CSS.read_text(encoding="utf-8")
        marker = "@media (max-width: 640px) {"
        start = cls.css.index(marker)
        # The first mobile block is the shared cross-page contract. Stop before
        # page-specific feature rules begin so the test cannot pass accidentally.
        end = cls.css.index("\n.phase-controls", start)
        cls.mobile = cls.css[start:end]

    def test_mobile_hero_is_content_height_not_viewport_height(self):
        self.assertIn(".book-hero { min-height: 0;", self.mobile)
        self.assertNotIn("min-height: 72vh", self.mobile)
        self.assertIn("padding: 2rem 0 2.25rem", self.mobile)

    def test_shared_heading_scale_and_vertical_rhythm_are_compact(self):
        self.assertIn("font-size: clamp(1.9rem, 8.8vw, 2.2rem)", self.mobile)
        self.assertIn("h2 { margin-top: 2.1em", self.mobile)
        self.assertIn("h3 { margin-top: 1.8em", self.mobile)
        self.assertIn(".breadcrumb { margin: 1rem 0 1.5rem;", self.mobile)
        self.assertIn(".section-index { padding: 2.5rem 0 1.5rem;", self.mobile)

    def test_shared_cards_are_dense_without_page_specific_css(self):
        self.assertIn(".card-grid, .content-grid", self.mobile)
        self.assertIn("gap: .75rem; margin: 1.25rem 0 2rem", self.mobile)
        self.assertIn(".nav-card, .content-card { min-height: 0; gap: .45rem; padding: 1rem;", self.mobile)
        for page_selector in ("companies", "trade-journal", "home-page"):
            self.assertNotIn(page_selector, self.mobile.lower())

    def test_mobile_shell_and_overflow_guards_cover_390_and_small_widths(self):
        self.assertIn("width: min(100% - 24px, 840px)", self.mobile)
        self.assertIn("table { display: block; max-width: 100%; overflow-x: auto; }", self.mobile)
        self.assertIn("pre { max-width: 100%; padding: .9rem; }", self.mobile)
        self.assertIn("@media (max-width: 360px)", self.css)
        self.assertIn("width: min(100% - 20px, 840px)", self.css)

    def test_theme_toggle_has_mobile_clearance(self):
        self.assertIn(".theme-toggle { top: 108px; right: 12px; }", self.mobile)
        self.assertIn(".site-header", self.mobile)
        self.assertIn("gap: .4rem", self.mobile)


if __name__ == "__main__":
    unittest.main()
