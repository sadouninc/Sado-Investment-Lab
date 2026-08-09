from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / ".github" / "pages" / "book-header.md"
BUILD_SITE = ROOT / ".github" / "pages" / "build_site.py"


class FrameworkNavigationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.header = HEADER.read_text(encoding="utf-8")
        self.builder = BUILD_SITE.read_text(encoding="utf-8")

    def test_all_framework_chapters_have_card_and_sticky_jump_links(self):
        for anchor in (
            "philosophy",
            "psychology",
            "thinking",
            "rules",
            "evaluation",
            "allocation",
            "lessons",
            "metrics",
        ):
            self.assertIn(f'href="#{anchor}"', self.header)
            self.assertIn(f'data-framework-target="{anchor}"', self.header)

    def test_current_chapter_highlighting_and_footer_navigation_are_present(self):
        self.assertIn("IntersectionObserver", self.header)
        self.assertIn("aria-current", self.header)
        self.assertIn("framework-chapter-footer", self.header)
        self.assertIn("目次へ戻る", self.header)
        self.assertIn("前の章", self.header)
        self.assertIn("次の章", self.header)

    def test_mobile_progressive_navigation_is_defined(self):
        self.assertIn("@media (max-width: 640px)", self.header)
        self.assertIn("overflow-x: auto", self.header)
        self.assertIn("grid-template-columns: 1fr", self.header)

    def test_framework_source_documents_remain_build_authority(self):
        self.assertIn("FRAMEWORK_CHAPTERS", self.builder)
        self.assertIn('ROOT / "00_Framework"', self.builder)
        self.assertIn("source.read_text", self.builder)
        self.assertIn("唯一の元データ", self.header)

    def test_key_principles_are_visually_promoted_without_rewriting_source(self):
        self.assertIn(".book-chapter blockquote::before", self.header)
        self.assertIn('content: "KEY PRINCIPLE"', self.header)


if __name__ == "__main__":
    unittest.main()
