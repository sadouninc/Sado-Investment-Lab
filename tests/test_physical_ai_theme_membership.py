from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "data" / "config" / "money-flow-themes-v1.json"
THEME_ID = "theme:physical-ai-robotics-core"


class PhysicalAIThemeMembershipTests(unittest.TestCase):
    def _theme(self) -> dict:
        payload = json.loads(CONFIG.read_text(encoding="utf-8"))
        matches = [theme for theme in payload["themes"] if theme["id"] == THEME_ID]
        self.assertEqual(1, len(matches))
        return matches[0]

    def test_canonical_membership_is_explicit_and_versioned(self) -> None:
        theme = self._theme()
        self.assertEqual("2026-08-12", theme["membership_as_of"])
        self.assertEqual("2026-08-12-v1", theme["membership_version"])
        self.assertIn("Issue #394", theme["authority"])
        self.assertEqual(
            "RETROSPECTIVE_MEMBERSHIP_IF_HISTORICAL_MEMBERSHIP_UNAVAILABLE",
            theme["backfill_policy"],
        )

    def test_members_are_exactly_the_verified_investable_proxy(self) -> None:
        theme = self._theme()
        self.assertEqual(
            ["6954", "6506", "6324", "6268", "6481"],
            [member["security_code"] for member in theme["members"]],
        )
        for member in theme["members"]:
            self.assertTrue(member["symbol"].endswith(".T"))
            self.assertTrue(member["inclusion_rationale"].strip())
            self.assertTrue(member["evidence_ref"].startswith("https://"))

    def test_scope_and_backfill_limitations_are_not_hidden(self) -> None:
        theme = self._theme()
        limitations = set(theme["limitations"])
        self.assertIn("RETROSPECTIVE_MEMBERSHIP", limitations)
        self.assertIn("THEME_SCOPE_PROXY", limitations)
        self.assertIn("BENCHMARK_PROXY", limitations)

    def test_membership_policy_rejects_keyword_only_and_unlisted_names(self) -> None:
        theme = self._theme()
        policy = theme["membership_policy"]
        self.assertIn("ai_keyword_only", policy["exclude_if"])
        self.assertIn("unlisted_security", policy["exclude_if"])
        self.assertIn(
            "direct_robotics_core_component_exposure_reducer_actuator_motion_control",
            policy["include_if"],
        )


if __name__ == "__main__":
    unittest.main()
