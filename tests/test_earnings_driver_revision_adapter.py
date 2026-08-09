from __future__ import annotations

import copy
import math
import unittest

from scripts.earnings_driver_revision_adapter import (
    EarningsDriverRevisionError,
    build_driver_revision_context,
    build_scenario_review_signal,
)
from scripts.research_revision_ledger import validate_revision


def _model(
    *,
    security_code: str = "6622",
    fiscal_year: str = "FY2027",
    value: float | int | None = 100.0,
    assumption_text: str = "Material Processing stays strong",
    confidence: str = "MEDIUM",
) -> dict:
    return {
        "security_code": security_code,
        "target_fiscal_year": fiscal_year,
        "nodes": [
            {
                "node_id": "base_material_processing_driver",
                "node_type": "ASSUMPTION",
                "scenario": "BASE",
                "metric": "KPI",
                "value": value,
                "assumption_text": assumption_text,
                "confidence": confidence,
            },
            {
                "node_id": "base_net_income_terminal",
                "node_type": "ASSUMPTION",
                "scenario": "BASE",
                "metric": "NET_INCOME",
                "value": 17000,
                "assumption_text": "Sado scenario terminal value",
                "confidence": "MEDIUM",
            },
        ],
    }


class EarningsDriverRevisionAdapterTest(unittest.TestCase):
    def test_driver_value_change_builds_revision_ledger_compatible_context(self) -> None:
        before = _model(value=100)
        after = _model(value=112)

        result = build_driver_revision_context(
            before,
            after,
            revised_at="2026-08-09T16:15:00+09:00",
            evidence_refs=["fact:6622:q2-orders"],
            reasoning="受注KPIの新Evidenceを受け、明示driver assumptionを更新した。",
        )

        self.assertEqual(result["status"], "REVISION_CONTEXT_READY")
        self.assertEqual(result["changed_driver_nodes"], ["base_material_processing_driver"])
        record = result["revision_record"]
        self.assertEqual(record["artifact_type"], "SCENARIO")
        self.assertEqual(record["trigger_type"], "KPI")
        self.assertEqual(record["evidence_refs"], ["fact:6622:q2-orders"])
        self.assertEqual(record["changed_fields"][0]["numeric_delta"]["absolute"], 12.0)
        self.assertEqual(record["changed_fields"][0]["numeric_delta"]["pct"], 12.0)

        validated = validate_revision(record)
        self.assertTrue(validated["revision_id"].startswith("revision:6622:"))

    def test_no_driver_change_does_not_create_revision(self) -> None:
        before = _model()
        result = build_driver_revision_context(
            before,
            copy.deepcopy(before),
            revised_at="2026-08-09T16:15:00+09:00",
            evidence_refs=["fact:unchanged"],
            reasoning="Evidenceを確認したがdriver変更は不要。",
        )
        self.assertEqual(result["status"], "NO_REVISION")
        self.assertIsNone(result["revision_record"])
        self.assertEqual(result["changed_driver_nodes"], [])

    def test_assumption_and_confidence_changes_are_explicit(self) -> None:
        before = _model(assumption_text="old", confidence="LOW")
        after = _model(assumption_text="new", confidence="MEDIUM")
        result = build_driver_revision_context(
            before,
            after,
            revised_at="2026-08-09T16:16:00+09:00",
            evidence_refs=["fact:6622:new-evidence"],
            reasoning="仮定と確信度を明示更新。",
        )
        paths = {item["path"] for item in result["revision_record"]["changed_fields"]}
        self.assertEqual(
            paths,
            {
                "nodes.base_material_processing_driver.assumption_text",
                "nodes.base_material_processing_driver.confidence",
            },
        )

    def test_fiscal_year_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(EarningsDriverRevisionError, "fiscal year mismatch"):
            build_driver_revision_context(
                _model(fiscal_year="FY2027"),
                _model(fiscal_year="FY2028"),
                revised_at="2026-08-09T16:15:00+09:00",
                evidence_refs=["fact:x"],
                reasoning="FYを跨いで比較しない。",
            )

    def test_security_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(EarningsDriverRevisionError, "security_code mismatch"):
            build_driver_revision_context(
                _model(security_code="6622"),
                _model(security_code="6504"),
                revised_at="2026-08-09T16:15:00+09:00",
                evidence_refs=["fact:x"],
                reasoning="銘柄を跨いで比較しない。",
            )

    def test_node_add_remove_requires_separate_review(self) -> None:
        before = _model()
        after = _model()
        after["nodes"] = after["nodes"][:-1]
        with self.assertRaisesRegex(EarningsDriverRevisionError, "stable driver node identity"):
            build_driver_revision_context(
                before,
                after,
                revised_at="2026-08-09T16:15:00+09:00",
                evidence_refs=["fact:x"],
                reasoning="構造変更は別Review。",
            )

    def test_noncanonical_changed_numeric_values_fail_closed(self) -> None:
        for bad in (True, "112", math.nan, math.inf):
            with self.subTest(bad=bad):
                after = _model()
                after["nodes"][0]["value"] = bad
                with self.assertRaises(EarningsDriverRevisionError):
                    build_driver_revision_context(
                        _model(value=100),
                        after,
                        revised_at="2026-08-09T16:15:00+09:00",
                        evidence_refs=["fact:x"],
                        reasoning="非canonical数値は拒否。",
                    )

    def test_weakened_kpi_requires_scenario_review_without_mutation(self) -> None:
        model = _model()
        result = build_scenario_review_signal(
            model,
            kpi_id="segment_orders",
            evidence_ref="fact:6622:q2-orders",
            evidence_effect="WEAKENS",
            affected_node_ids=["base_material_processing_driver"],
            observed_at="2026-08-09T16:20:00+09:00",
            note="受注の弱含みがBase driver assumptionへ影響する可能性。",
        )
        self.assertEqual(result["status"], "SCENARIO_REVIEW_REQUIRED")
        self.assertEqual(result["affected_nodes"], ["base_material_processing_driver"])
        self.assertFalse(result["scenario_values_mutated"])
        self.assertIsNone(result["trade_action"])

    def test_invalidating_kpi_requires_scenario_review(self) -> None:
        result = build_scenario_review_signal(
            _model(),
            kpi_id="material_processing_orders",
            evidence_ref="fact:6622:orders-collapse",
            evidence_effect="INVALIDATES",
            affected_node_ids=["base_material_processing_driver"],
            observed_at="2026-08-09T16:21:00+09:00",
            note="反証条件に該当する可能性をReviewへ送る。",
        )
        self.assertEqual(result["status"], "SCENARIO_REVIEW_REQUIRED")

    def test_neutral_kpi_does_not_require_review(self) -> None:
        result = build_scenario_review_signal(
            _model(),
            kpi_id="segment_orders",
            evidence_ref="fact:6622:unchanged",
            evidence_effect="NEUTRAL",
            affected_node_ids=["base_material_processing_driver"],
            observed_at="2026-08-09T16:22:00+09:00",
            note="重要な変化なし。",
        )
        self.assertEqual(result["status"], "NO_SCENARIO_REVIEW")
        self.assertFalse(result["scenario_values_mutated"])

    def test_unknown_or_missing_affected_node_fails_closed(self) -> None:
        for affected in ([], ["unknown-node"]):
            with self.subTest(affected=affected):
                with self.assertRaises(EarningsDriverRevisionError):
                    build_scenario_review_signal(
                        _model(),
                        kpi_id="segment_orders",
                        evidence_ref="fact:x",
                        evidence_effect="WEAKENS",
                        affected_node_ids=affected,
                        observed_at="2026-08-09T16:22:00+09:00",
                        note="明示関係なしでは推測しない。",
                    )

    def test_deterministic_and_non_mutating(self) -> None:
        before = _model(value=100)
        after = _model(value=108)
        before_original = copy.deepcopy(before)
        after_original = copy.deepcopy(after)
        kwargs = {
            "revised_at": "2026-08-09T16:25:00+09:00",
            "evidence_refs": ["fact:6622:q2"],
            "reasoning": "明示Evidenceによりdriverを更新。",
        }
        first = build_driver_revision_context(before, after, **kwargs)
        second = build_driver_revision_context(before, after, **kwargs)
        self.assertEqual(first, second)
        self.assertEqual(before, before_original)
        self.assertEqual(after, after_original)

        signal_kwargs = {
            "kpi_id": "segment_orders",
            "evidence_ref": "fact:6622:q2",
            "evidence_effect": "SUPPORTS",
            "affected_node_ids": ["base_material_processing_driver"],
            "observed_at": "2026-08-09T16:25:00+09:00",
            "note": "強いEvidenceでも利益値を自動変更せずReviewへ送る。",
        }
        signal_first = build_scenario_review_signal(after, **signal_kwargs)
        signal_second = build_scenario_review_signal(after, **signal_kwargs)
        self.assertEqual(signal_first, signal_second)
        self.assertEqual(after, after_original)


if __name__ == "__main__":
    unittest.main()
