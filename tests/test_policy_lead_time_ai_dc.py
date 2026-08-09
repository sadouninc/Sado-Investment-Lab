from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.money_flow_history import load_history
from scripts.policy_lead_time_ai_dc import build_ai_dc_policy_lead_time_v2


ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data/generated/public/money-flow/history.jsonl"
V1 = ROOT / "data/generated/public/money-flow/policy-lead-time-ai-dc.json"
EXPECTED = ROOT / "tests/fixtures/policy-lead-time-ai-dc-v2-expected.json"


class PolicyLeadTimeAIDCTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.history = load_history(HISTORY)
        cls.v1 = json.loads(V1.read_text(encoding="utf-8"))
        cls.expected = json.loads(EXPECTED.read_text(encoding="utf-8"))

    def test_canonical_ai_dc_raw_and_reliable_dates_are_separated(self):
        result = build_ai_dc_policy_lead_time_v2(history=self.history, v1_lead_time=self.v1)
        evaluation = result["evaluation"]
        self.assertEqual(evaluation["raw_first"]["inflow_date"], self.expected["raw_first_inflow_date"])
        self.assertEqual(evaluation["raw_first"]["warming_date"], self.expected["raw_first_warming_date"])
        self.assertEqual(evaluation["reliable_first"]["warming_date"], self.expected["reliable_first_warming_date"])
        self.assertEqual(evaluation["reliable_first"]["inflow_date"], self.expected["reliable_first_inflow_date"])

    def test_retrospective_membership_keeps_classification_data_limited(self):
        result = build_ai_dc_policy_lead_time_v2(history=self.history, v1_lead_time=self.v1)
        evaluation = result["evaluation"]
        self.assertEqual(evaluation["classification"], self.expected["classification"])
        self.assertEqual(evaluation["data_quality"], "LIMITED")
        self.assertEqual(evaluation["limitations"], self.expected["limitations"])

    def test_policy_deltas_preserve_v1_and_add_reliable_dates(self):
        result = build_ai_dc_policy_lead_time_v2(history=self.history, v1_lead_time=self.v1)
        evaluation = result["evaluation"]
        self.assertEqual(evaluation["raw_first"]["policy_to_inflow_days"], self.expected["raw_policy_to_inflow_days"])
        self.assertEqual(evaluation["raw_first"]["policy_to_warming_days"], self.expected["raw_policy_to_warming_days"])
        self.assertEqual(evaluation["reliable_first"]["policy_to_warming_days"], self.expected["reliable_policy_to_warming_days"])
        self.assertEqual(evaluation["reliable_first"]["policy_to_inflow_days"], self.expected["reliable_policy_to_inflow_days"])

    def test_sequence_summary_preserves_partial_pre_policy_signal_without_promoting_it(self):
        result = build_ai_dc_policy_lead_time_v2(history=self.history, v1_lead_time=self.v1)
        summary = result["sequence_summary"]
        self.assertEqual(summary["strongest_pre_policy_state"], "INFLOW")
        self.assertIsNone(summary["reliable_strongest_pre_policy_state"])
        self.assertFalse(result["evaluation"]["post_policy_persistence"])
        self.assertFalse(result["evaluation"]["post_policy_reacceleration"])

    def test_v1_is_not_mutated(self):
        original = copy.deepcopy(self.v1)
        build_ai_dc_policy_lead_time_v2(history=self.history, v1_lead_time=self.v1)
        self.assertEqual(self.v1, original)

    def test_deterministic_rerun(self):
        first = build_ai_dc_policy_lead_time_v2(history=self.history, v1_lead_time=self.v1)
        second = build_ai_dc_policy_lead_time_v2(history=self.history, v1_lead_time=self.v1)
        self.assertEqual(first, second)

    def test_policy_evidence_is_not_in_market_score(self):
        result = build_ai_dc_policy_lead_time_v2(history=self.history, v1_lead_time=self.v1)
        self.assertFalse(result["policy_evidence_in_market_score"])
        self.assertFalse(result["evaluation"]["policy_evidence_in_market_score"])


if __name__ == "__main__":
    unittest.main()
