from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.research_revision_ledger import (
    ResearchRevisionError,
    append_revision,
    changed_fields,
    deterministic_revision_id,
    scenario_numeric_change,
    validate_revision,
)


def revision_fixture() -> dict:
    return {
        "entity_type": "COMPANY",
        "entity_id": "6622",
        "artifact_type": "SCENARIO",
        "artifact_ref": "research:6622",
        "revised_at": "2026-11-05T16:10:00+09:00",
        "trigger_type": "EARNINGS",
        "trigger_ref": "event:company:6622:earnings:FY2027Q2",
        "previous_revision_ref": None,
        "change_summary": "Base net income revised",
        "changed_fields": [
            scenario_numeric_change(
                field_path="scenarios.base.net_income",
                before=17000,
                after=18500,
                before_target_fiscal_year="FY2027",
                after_target_fiscal_year="FY2027",
            )
        ],
        "reasoning": "Margin conversion improved after Q2 evidence.",
        "evidence_refs": ["fact:6622:fy2027q2:operating-profit"],
        "confidence_before": "MEDIUM",
        "confidence_after": "MEDIUM",
        "materiality": "MATERIAL",
        "author_type": "ANALYST",
        "as_of": "2026-11-05",
    }


class ResearchRevisionLedgerTests(unittest.TestCase):
    def test_identity_is_deterministic(self):
        row = revision_fixture()
        self.assertEqual(deterministic_revision_id(row), deterministic_revision_id(dict(row)))

    def test_numeric_delta_and_fiscal_basis_are_explicit(self):
        change = revision_fixture()["changed_fields"][0]
        self.assertEqual(change["numeric_delta"]["absolute"], 1500.0)
        self.assertAlmostEqual(change["numeric_delta"]["pct"], 8.823529, places=6)
        self.assertEqual(change["target_fiscal_year"], "FY2027")

    def test_fy_mismatch_fails_closed(self):
        with self.assertRaises(ResearchRevisionError):
            scenario_numeric_change(
                field_path="scenarios.base.eps",
                before=700,
                after=800,
                before_target_fiscal_year="FY2027",
                after_target_fiscal_year="FY2028",
            )

    def test_missing_previous_value_is_not_zero(self):
        with self.assertRaises(ResearchRevisionError):
            scenario_numeric_change(
                field_path="scenarios.base.eps",
                before=None,
                after=800,
                before_target_fiscal_year="FY2027",
                after_target_fiscal_year="FY2027",
            )

    def test_event_without_artifact_change_is_not_a_revision(self):
        row = revision_fixture()
        row["changed_fields"] = []
        with self.assertRaises(ResearchRevisionError):
            validate_revision(row)

    def test_changed_fields_is_deterministic_and_separates_values(self):
        changes = changed_fields(
            {"base_eps": 500, "confidence": "MEDIUM"},
            {"base_eps": 560, "confidence": "HIGH", "new_kpi": "orders"},
        )
        self.assertEqual([item["path"] for item in changes], ["base_eps", "confidence", "new_kpi"])
        self.assertEqual(changes[0]["numeric_delta"]["pct"], 12.0)
        self.assertEqual(changes[2]["change_type"], "ADDED")

    def test_append_only_retry_is_idempotent_and_conflict_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "revisions.jsonl"
            row = revision_fixture()
            self.assertEqual(append_revision(path, row), "INSERTED")
            self.assertEqual(append_revision(path, row), "UNCHANGED")
            conflict = revision_fixture()
            conflict["reasoning"] = "Different reasoning for same identity"
            with self.assertRaises(ResearchRevisionError):
                append_revision(path, conflict)

    def test_evidence_and_reasoning_remain_separate(self):
        validated = validate_revision(revision_fixture())
        self.assertEqual(validated["evidence_refs"], ["fact:6622:fy2027q2:operating-profit"])
        self.assertIn("Margin conversion", validated["reasoning"])
        self.assertNotEqual(validated["evidence_refs"], validated["reasoning"])


if __name__ == "__main__":
    unittest.main()
