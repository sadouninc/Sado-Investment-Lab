from __future__ import annotations

import copy
import unittest

from scripts.expectation_revision_leadtime import RevisionLeadTimeError, measure_revision_lead_time


MAPPING = {
    "security_code": "6622",
    "field_path": "scenarios.base.eps",
    "target_fiscal_period": "FY2027",
    "metric": "EPS",
    "unit": "JPY",
}


def sado_revision(*, revised_at: str = "2026-07-01T09:00:00+09:00", before=430, after=500, artifact_type="SCENARIO"):
    return {
        "entity_type": "COMPANY",
        "entity_id": "6622",
        "artifact_type": artifact_type,
        "artifact_ref": "research:6622:scenario:base:FY2027",
        "revised_at": revised_at,
        "trigger_type": "EARNINGS",
        "trigger_ref": "event:6622:q1",
        "change_summary": "Base EPS revised",
        "changed_fields": [
            {
                "path": "scenarios.base.eps",
                "before": before,
                "after": after,
                "change_type": "UPDATED",
            }
        ],
        "reasoning": "updated research view",
        "evidence_refs": ["fact:6622:q1"],
        "materiality": "MATERIAL",
        "author_type": "OWNER",
        "as_of": "2026-07-01",
    }


def consensus(*, as_of: str, observed_at: str, value, fiscal="FY2027", unit="JPY", status="OK"):
    return {
        "security_code": "6622",
        "target_fiscal_period": fiscal,
        "as_of": as_of,
        "expectation_type": "CONSENSUS",
        "metric": "EPS",
        "value": value,
        "unit": unit,
        "source_ref": f"fixture://consensus/{as_of}",
        "source_authority": "SECONDARY",
        "observed_at": observed_at,
        "coverage": {"analyst_count": 8, "dispersion": None, "status": status},
        "provenance": {},
    }


class RevisionLeadTimeTests(unittest.TestCase):
    def test_sado_revision_precedes_first_later_same_direction_consensus_revision(self):
        history = [
            consensus(as_of="2026-06-01", observed_at="2026-06-01T09:00:00+09:00", value=400),
            consensus(as_of="2026-07-10", observed_at="2026-07-10T09:00:00+09:00", value=450),
            consensus(as_of="2026-07-20", observed_at="2026-07-20T09:00:00+09:00", value=470),
        ]
        result = measure_revision_lead_time(sado_revision(), history, mapping=MAPPING)
        self.assertEqual(result["status"], "SADO_REVISION_PRECEDED_MATCHING_CONSENSUS")
        self.assertEqual(result["sado_direction"], "UP")
        self.assertEqual(result["lead_time_hours"], 216.0)
        self.assertIn("timing evidence", result["interpretation"])

    def test_consensus_already_moved_is_not_classified_as_sado_led(self):
        history = [
            consensus(as_of="2026-06-01", observed_at="2026-06-01T09:00:00+09:00", value=400),
            consensus(as_of="2026-06-20", observed_at="2026-06-20T09:00:00+09:00", value=450),
            consensus(as_of="2026-07-10", observed_at="2026-07-10T09:00:00+09:00", value=470),
        ]
        result = measure_revision_lead_time(sado_revision(), history, mapping=MAPPING)
        self.assertEqual(result["status"], "CONSENSUS_ALREADY_MOVED")
        self.assertIsNone(result["lead_time_hours"])
        self.assertGreater(result["consensus_lead_hours"], 0)

    def test_only_latest_prior_consensus_direction_controls_already_moved_status(self):
        history = [
            consensus(as_of="2026-05-01", observed_at="2026-05-01T09:00:00+09:00", value=400),
            consensus(as_of="2026-05-20", observed_at="2026-05-20T09:00:00+09:00", value=450),
            consensus(as_of="2026-06-20", observed_at="2026-06-20T09:00:00+09:00", value=420),
            consensus(as_of="2026-07-10", observed_at="2026-07-10T09:00:00+09:00", value=460),
        ]
        result = measure_revision_lead_time(sado_revision(), history, mapping=MAPPING)
        self.assertEqual(result["status"], "SADO_REVISION_PRECEDED_MATCHING_CONSENSUS")
        self.assertEqual(result["lead_time_hours"], 216.0)

    def test_opposite_direction_does_not_count_as_matching_revision(self):
        history = [
            consensus(as_of="2026-06-01", observed_at="2026-06-01T09:00:00+09:00", value=500),
            consensus(as_of="2026-07-10", observed_at="2026-07-10T09:00:00+09:00", value=450),
        ]
        result = measure_revision_lead_time(sado_revision(), history, mapping=MAPPING)
        self.assertEqual(result["status"], "NO_MATCHING_CONSENSUS_REVISION")
        self.assertIsNone(result["matching_consensus_revision_ref"])

    def test_fiscal_or_unit_mismatch_is_not_silently_compared(self):
        history = [
            consensus(as_of="2026-06-01", observed_at="2026-06-01T09:00:00+09:00", value=400, fiscal="FY2028"),
            consensus(as_of="2026-07-10", observed_at="2026-07-10T09:00:00+09:00", value=450, unit="JPY_MN"),
        ]
        result = measure_revision_lead_time(sado_revision(), history, mapping=MAPPING)
        self.assertEqual(result["status"], "NO_MATCHING_CONSENSUS_REVISION")

    def test_unavailable_consensus_is_not_zero_or_revision(self):
        history = [
            consensus(as_of="2026-06-01", observed_at="2026-06-01T09:00:00+09:00", value=400),
            consensus(as_of="2026-07-10", observed_at="2026-07-10T09:00:00+09:00", value=None, status="UNAVAILABLE"),
        ]
        result = measure_revision_lead_time(sado_revision(), history, mapping=MAPPING)
        self.assertEqual(result["status"], "NO_MATCHING_CONSENSUS_REVISION")

    def test_down_revision_matches_only_later_down_consensus(self):
        history = [
            consensus(as_of="2026-06-01", observed_at="2026-06-01T09:00:00+09:00", value=500),
            consensus(as_of="2026-07-05", observed_at="2026-07-05T09:00:00+09:00", value=480),
        ]
        result = measure_revision_lead_time(sado_revision(before=500, after=450), history, mapping=MAPPING)
        self.assertEqual(result["status"], "SADO_REVISION_PRECEDED_MATCHING_CONSENSUS")
        self.assertEqual(result["sado_direction"], "DOWN")
        self.assertEqual(result["lead_time_hours"], 96.0)

    def test_flat_sado_value_is_not_a_revision_event(self):
        with self.assertRaises(RevisionLeadTimeError):
            measure_revision_lead_time(sado_revision(before=500, after=500), [], mapping=MAPPING)

    def test_mapping_requires_exact_changed_field(self):
        mapping = dict(MAPPING)
        mapping["field_path"] = "scenarios.bull.eps"
        with self.assertRaises(RevisionLeadTimeError):
            measure_revision_lead_time(sado_revision(), [], mapping=mapping)

    def test_non_scenario_revision_is_rejected(self):
        with self.assertRaises(RevisionLeadTimeError):
            measure_revision_lead_time(sado_revision(artifact_type="HYPOTHESIS"), [], mapping=MAPPING)

    def test_security_mapping_mismatch_is_rejected(self):
        mapping = dict(MAPPING)
        mapping["security_code"] = "9999"
        with self.assertRaises(RevisionLeadTimeError):
            measure_revision_lead_time(sado_revision(), [], mapping=mapping)

    def test_rerun_is_deterministic_and_inputs_are_not_mutated(self):
        revision = sado_revision()
        history = [
            consensus(as_of="2026-06-01", observed_at="2026-06-01T09:00:00+09:00", value=400),
            consensus(as_of="2026-07-10", observed_at="2026-07-10T09:00:00+09:00", value=450),
        ]
        original_revision = copy.deepcopy(revision)
        original_history = copy.deepcopy(history)
        first = measure_revision_lead_time(revision, history, mapping=MAPPING)
        second = measure_revision_lead_time(revision, history, mapping=MAPPING)
        self.assertEqual(first, second)
        self.assertEqual(revision, original_revision)
        self.assertEqual(history, original_history)


if __name__ == "__main__":
    unittest.main()
