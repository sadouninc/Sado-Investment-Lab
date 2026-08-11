from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / ".github" / "pages" / "design-system.css"
FIXTURE = ROOT / "06_Research" / "Architecture" / "Design_System_Fixture.md"
BUILDER = ROOT / ".github" / "pages" / "build_architecture.py"


class DesignSystemContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.css = CSS.read_text(encoding="utf-8")
        cls.fixture = FIXTURE.read_text(encoding="utf-8")
        cls.builder = BUILDER.read_text(encoding="utf-8")

    def test_required_semantic_tokens_exist(self):
        for token in (
            "--codex-surface-canvas",
            "--codex-surface-panel",
            "--codex-text-primary",
            "--codex-text-muted",
            "--codex-border-subtle",
            "--codex-border-emphasis",
            "--codex-accent-primary",
            "--codex-accent-brass",
            "--codex-state-supportive",
            "--codex-state-challenging",
            "--codex-state-critical",
            "--codex-state-stale",
            "--codex-state-unavailable",
            "--codex-state-unknown",
        ):
            self.assertIn(token, self.css)

    def test_scenario_namespace_is_separate_from_system_state(self):
        for token in (
            "--codex-scenario-bear",
            "--codex-scenario-base",
            "--codex-scenario-bull",
        ):
            self.assertIn(token, self.css)
        self.assertNotIn("--codex-state-bull", self.css)
        self.assertNotIn("--codex-state-bear", self.css)

    def test_required_primitives_exist(self):
        for primitive in (
            ".codex-page-shell",
            ".codex-page-header",
            ".codex-summary-card",
            ".codex-kpi",
            ".codex-delta",
            ".codex-status-chip",
            ".codex-alert",
            ".codex-action",
            ".codex-scenario-card",
            ".codex-evidence",
            ".codex-disclosure",
            ".codex-instrument-icon",
        ):
            self.assertIn(primitive, self.css)

    def test_status_fixture_uses_human_readable_japanese_labels(self):
        for label in ("通常", "追い風", "要確認", "重要警告", "更新が古い", "現在取得できません", "まだ判断できません"):
            self.assertIn(label, self.fixture)
        for state in ("normal", "supportive", "challenging", "critical", "stale", "unavailable", "unknown"):
            self.assertIn(f'data-state="{state}"', self.fixture)

    def test_fixture_covers_scenarios_delta_and_evidence(self):
        for scenario in ("bear", "base", "bull"):
            self.assertIn(f'data-scenario="{scenario}"', self.fixture)
        self.assertIn("前回 11,500円", self.fixture)
        self.assertIn("現在 12,480円", self.fixture)
        self.assertIn("根拠を詳しく見る", self.fixture)
        self.assertIn("Canonical mutationなし", self.fixture)

    def test_asset_is_published_by_architecture_builder(self):
        self.assertIn('PAGES / "design-system.css"', self.builder)
        self.assertIn('SITE_ROOT / "assets" / "design-system.css"', self.builder)
        self.assertIn("shutil.copy2(DESIGN_SYSTEM_CSS, destination)", self.builder)
        self.assertIn("'/assets/design-system.css' | relative_url", self.fixture)

    def test_mobile_and_focus_contracts_are_present(self):
        self.assertIn("@media (max-width: 640px)", self.css)
        self.assertIn(":focus-visible", self.css)
        self.assertIn("prefers-reduced-motion", self.css)


if __name__ == "__main__":
    unittest.main()
