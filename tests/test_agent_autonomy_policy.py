from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
POLICY = ROOT / "docs" / "process" / "ai-implementation-autonomy-policy.md"
HANDOFF = ROOT / "docs" / "process" / "ready-for-implementation-handoff.md"


class AgentAutonomyPolicyTest(unittest.TestCase):
    def test_agent_instruction_entrypoint_reaches_authorities_and_policy(self):
        text = AGENTS.read_text(encoding="utf-8")
        self.assertIn("TEAM_RULES.md", text)
        self.assertIn("Issue #99", text)
        self.assertIn("ai-implementation-autonomy-policy.md", text)
        self.assertIn("READY_FOR_IMPLEMENTATION", text)
        self.assertIn("Autonomy: STANDARD", text)

    def test_policy_preserves_green_yellow_red_and_ask_only_contract(self):
        text = POLICY.read_text(encoding="utf-8")
        for heading in (
            "## GREEN — Autonomous",
            "## YELLOW — Explicit scope permission",
            "## RED — Fail closed",
            "## Ask-only conditions",
        ):
            self.assertIn(heading, text)

        red_section = text.split("## RED — Fail closed", 1)[1].split("## Ask-only conditions", 1)[0]
        for protected_boundary in (
            "mainへの直接変更",
            "PR merge",
            "destructive delete",
            "secrets、permissions、billing",
            "production external systemへのwrite",
            "Investment Authority判断",
            "Canonical truth",
            "Issue #79",
        ):
            self.assertIn(protected_boundary, red_section)

        ask_only = text.split("## Ask-only conditions", 1)[1].split("## Runtimeとの境界", 1)[0]
        numbered_conditions = sum(
            line.lstrip().startswith(f"{number}.")
            for number in range(1, 8)
            for line in ask_only.splitlines()
        )
        self.assertEqual(numbered_conditions, 7)

    def test_ready_handoff_is_durable_and_does_not_expand_authority(self):
        text = HANDOFF.read_text(encoding="utf-8")
        for field in (
            "Status: READY_FOR_IMPLEMENTATION",
            "Autonomy: STANDARD",
            "Goal:",
            "Scope:",
            "Authority:",
            "Acceptance Criteria:",
            "Non-goals:",
            "YELLOW permissions:",
        ):
            self.assertIn(field, text)
        self.assertIn("Issue #79変更は禁止", text)
        self.assertIn("RED操作の許可を意味しない", text)

    def test_runtime_specific_values_are_deferred_from_pr1(self):
        combined = AGENTS.read_text(encoding="utf-8") + POLICY.read_text(encoding="utf-8")
        self.assertIn("unrestricted / full-accessを既定にしない", combined)
        self.assertIn("設定値を定義しない", combined)


if __name__ == "__main__":
    unittest.main()
