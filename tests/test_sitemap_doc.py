"""Regression tests for the canonical Sado Investment Codex sitemap document.

Covers Issue #566 (Copilot Gate C Pilot) acceptance criteria for
`00_Framework/SADO_INVESTMENT_CODEX_SITEMAP.md`:
- the canonical doc exists
- all 9 stages of the Observe -> Re-observe loop are present
- the main status enum values are present
- foundation / feature nodes are mapped
- existing vs. planned routes are not conflated
- related Issues are traceable
- Issue #79 is not touched / required by this doc
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "00_Framework" / "SADO_INVESTMENT_CODEX_SITEMAP.md"


class SitemapDocTest(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(DOC.exists(), f"Canonical sitemap doc missing: {DOC}")
        self.text = DOC.read_text(encoding="utf-8")

    def test_canonical_doc_exists_and_is_non_empty(self) -> None:
        self.assertTrue(DOC.is_file())
        self.assertGreater(len(self.text.strip()), 0)

    def test_has_title_purpose_and_last_reviewed(self) -> None:
        self.assertIn("Sado Investment Codex", self.text)
        self.assertIn("Purpose:", self.text)
        self.assertIn("Last reviewed:", self.text)

    def test_contains_nine_stage_loop(self) -> None:
        expected_stages = [
            "Observe",
            "Discover",
            "Understand",
            "Hypothesize",
            "Decide",
            "Act",
            "Record",
            "Learn",
            "Re-observe",
        ]
        for stage in expected_stages:
            self.assertIn(stage, self.text, f"Missing 9-stage loop stage: {stage}")

    def test_contains_status_enum(self) -> None:
        expected_statuses = [
            "LIVE",
            "DONE",
            "BUILDING",
            "DESIGNED",
            "NEXT",
            "PLANNED",
            "IDEA",
            "BLOCKED",
            "DEFERRED",
            "RETIRED",
        ]
        for status in expected_statuses:
            self.assertIn(f"`{status}`", self.text, f"Missing status enum value: {status}")

    def test_contains_major_foundation_nodes(self) -> None:
        foundation_nodes = [
            "Home",
            "Codex Map",
            "Global Navigation",
            "Concept",
        ]
        for node in foundation_nodes:
            self.assertIn(node, self.text, f"Missing foundation node: {node}")

    def test_contains_major_feature_nodes(self) -> None:
        feature_nodes = [
            "Money Flow",
            "Candidate Selector",
            "Company Research",
            "Hypothesis",
            "Bear",
            "Cockpit",
            "Trade Intent",
            "Portfolio Preflight",
            "Decision Journal",
            "Review",
            "Checkpoint",
        ]
        for node in feature_nodes:
            self.assertIn(node, self.text, f"Missing feature node: {node}")

    def test_does_not_conflate_existing_and_planned_routes(self) -> None:
        self.assertIn(
            "route/page existence must be verified independently",
            self.text,
        )
        self.assertIn(
            "is not considered live until its actual route/artifact and user reachability have both been verified",
            self.text,
        )

    def test_related_issue_refs_are_traceable(self) -> None:
        for issue_ref in ["#309", "#312", "#313", "#314", "#317", "#324"]:
            self.assertIn(issue_ref, self.text, f"Missing related Issue ref: {issue_ref}")

    def test_does_not_require_changes_to_protected_issue_79(self) -> None:
        # Issue #79 is protected canonical truth; this doc must never reference
        # it as something to be implemented/changed.
        self.assertNotIn("#79", self.text)


if __name__ == "__main__":
    unittest.main()
