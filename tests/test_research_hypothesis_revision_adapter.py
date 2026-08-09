from __future__ import annotations

import copy
import unittest

from scripts.evidence_provenance import ProvenanceLedger
from scripts.research_hypothesis_revision_adapter import (
    HypothesisRevisionAdapterError,
    attach_revision_evidence_lineage,
    build_hypothesis_revision,
)


def research(*, security_code: str = "6622", thesis: str = "Data-center power demand is underestimated", confidence: str = "MEDIUM"):
    return {
        "security_code": security_code,
        "company_name": "ダイヘン",
        "as_of": "2026-08-09",
        "status": "CURRENT",
        "selection_context": {
            "selection_reason": "First E2E validation",
            "candidate_sources": ["candidate:6622"],
        },
        "facts": {
            "business_summary": {"summary": "Power equipment and factory automation"},
            "latest_financials": {
                "revenue": 100,
                "source_ref": "ir://6622/q1",
                "as_of": "2026-08-07",
            },
            "earnings_engine": {"drivers": ["data-center", "grid"]},
        },
        "interpretation": {
            "growth_drivers": ["data-center power demand"],
            "risks": ["investment slowdown"],
            "valuation_context": {},
        },
        "scenarios": {
            "bear": {
                "target_fiscal_year": "FY2027",
                "eps": 570,
                "assumptions": ["slower demand"],
                "source_type": "SADO_SCENARIO",
            },
            "base": {
                "target_fiscal_year": "FY2027",
                "eps": 720,
                "assumptions": ["continued demand"],
                "source_type": "SADO_SCENARIO",
            },
            "bull": {
                "target_fiscal_year": "FY2027",
                "eps": 850,
                "assumptions": ["strong demand"],
                "source_type": "SADO_SCENARIO",
            },
        },
        "hypothesis": {
            "what_market_may_be_underestimating": thesis,
            "must_happen": ["orders remain strong"],
            "key_kpis": ["orders"],
            "invalidation_conditions": ["orders deteriorate materially"],
            "expected_time_horizon": "1-3Y",
            "current_confidence": confidence,
        },
        "source_refs": ["ir://6622/q1"],
        "data_completeness": "COMPLETE",
    }


def ledger_with_fact() -> tuple[ProvenanceLedger, str]:
    ledger = ProvenanceLedger()
    source = ledger.ingest_source(
        {
            "source_type": "IR",
            "publisher": "株式会社ダイヘン",
            "published_at": "2026-08-07T15:00:00+09:00",
            "observed_at": "2026-08-07T15:10:00+09:00",
            "canonical_ref": "ir://6622/q1",
            "content_hash": None,
            "authority": "PRIMARY",
            "status": "CURRENT",
        }
    )
    fact = ledger.ingest_fact(
        {
            "source_id": source.source_id,
            "entity_type": "COMPANY",
            "entity_id": "6622",
            "field": "orders_yoy_pct",
            "value": 18.0,
            "unit": "%",
            "period": "FY2027-Q1",
            "as_of": "2026-08-07",
            "locator": "page:7/table:orders",
            "confidence": "HIGH",
        }
    )
    return ledger, fact.fact_id


class HypothesisRevisionAdapterTests(unittest.TestCase):
    def test_meaningful_hypothesis_change_creates_revision(self):
        before = research()
        after = research(thesis="Data-center and grid demand are underestimated")
        revision = build_hypothesis_revision(
            before,
            after,
            revised_at="2026-08-09T16:20:00+09:00",
            trigger_type="IR",
            trigger_ref="event:6622:q1",
            reasoning="New evidence broadened the growth thesis.",
        )
        self.assertIsNotNone(revision)
        self.assertEqual(revision["artifact_type"], "HYPOTHESIS")
        self.assertEqual(revision["artifact_ref"], "hypothesis:6622")
        self.assertEqual(revision["changed_fields"][0]["path"], "hypothesis.what_market_may_be_underestimating")
        self.assertEqual(revision["materiality"], "MATERIAL")

    def test_confidence_change_is_preserved_before_and_after(self):
        before = research(confidence="MEDIUM")
        after = research(confidence="HIGH")
        revision = build_hypothesis_revision(
            before,
            after,
            revised_at="2026-08-09T16:20:00+09:00",
            trigger_type="EARNINGS",
            trigger_ref="event:6622:q1",
            reasoning="Evidence confidence improved.",
        )
        self.assertEqual(revision["confidence_before"], "MEDIUM")
        self.assertEqual(revision["confidence_after"], "HIGH")
        self.assertEqual(revision["changed_fields"][0]["path"], "hypothesis.current_confidence")

    def test_whitespace_only_text_change_does_not_create_revision(self):
        before = research(thesis="Data-center power demand is underestimated")
        after = research(thesis="  Data-center   power demand is underestimated  ")
        revision = build_hypothesis_revision(
            before,
            after,
            revised_at="2026-08-09T16:20:00+09:00",
            trigger_type="MANUAL_REVIEW",
            trigger_ref="review:6622",
            reasoning="Formatting cleanup only.",
        )
        self.assertIsNone(revision)

    def test_identical_artifact_does_not_create_event_only_revision(self):
        before = research()
        after = copy.deepcopy(before)
        revision = build_hypothesis_revision(
            before,
            after,
            revised_at="2026-08-09T16:20:00+09:00",
            trigger_type="EARNINGS",
            trigger_ref="event:6622:q1",
            reasoning="Event occurred but thesis did not change.",
        )
        self.assertIsNone(revision)

    def test_security_mismatch_fails_closed(self):
        with self.assertRaises(HypothesisRevisionAdapterError):
            build_hypothesis_revision(
                research(security_code="6622"),
                research(security_code="9999"),
                revised_at="2026-08-09T16:20:00+09:00",
                trigger_type="IR",
                trigger_ref=None,
                reasoning="Should fail.",
            )

    def test_reasoning_is_required_for_actual_change(self):
        with self.assertRaises(HypothesisRevisionAdapterError):
            build_hypothesis_revision(
                research(),
                research(confidence="HIGH"),
                revised_at="2026-08-09T16:20:00+09:00",
                trigger_type="IR",
                trigger_ref=None,
                reasoning="",
            )

    def test_materiality_is_explicit_not_auto_promoted(self):
        revision = build_hypothesis_revision(
            research(),
            research(thesis="Completely rewritten thesis wording"),
            revised_at="2026-08-09T16:20:00+09:00",
            trigger_type="MANUAL_REVIEW",
            trigger_ref="review:6622",
            reasoning="Owner revised thesis wording and scope.",
            materiality="NON_MATERIAL",
        )
        self.assertEqual(revision["materiality"], "NON_MATERIAL")
        self.assertNotEqual(revision["materiality"], "THESIS_CHANGING")

    def test_explicit_fact_relation_creates_hypothesis_and_revision_edges(self):
        ledger, fact_id = ledger_with_fact()
        revision = build_hypothesis_revision(
            research(),
            research(confidence="HIGH"),
            revised_at="2026-08-09T16:20:00+09:00",
            trigger_type="EARNINGS",
            trigger_ref="event:6622:q1",
            reasoning="Orders evidence increased confidence.",
            evidence_fact_refs=[fact_id],
        )
        projection = attach_revision_evidence_lineage(
            ledger,
            revision,
            evidence_relations={fact_id: "SUPPORTS"},
            created_at="2026-08-09T16:21:00+09:00",
            actor="SORA",
        )
        self.assertEqual(projection["fact_refs"], [fact_id])
        edges = ledger.to_dict()["edges"]
        self.assertEqual(len(edges), 2)
        relation_by_to = {edge["to"]: edge["relation"] for edge in edges}
        self.assertEqual(relation_by_to[revision["artifact_ref"]], "SUPPORTS")
        self.assertEqual(relation_by_to[revision["revision_id"]], "REFERENCES")

    def test_missing_fact_ref_is_not_invented(self):
        ledger, _ = ledger_with_fact()
        missing = "fact:missing"
        revision = build_hypothesis_revision(
            research(),
            research(confidence="HIGH"),
            revised_at="2026-08-09T16:20:00+09:00",
            trigger_type="EARNINGS",
            trigger_ref="event:6622:q1",
            reasoning="Evidence claimed but not registered.",
            evidence_fact_refs=[missing],
        )
        with self.assertRaises(HypothesisRevisionAdapterError):
            attach_revision_evidence_lineage(
                ledger,
                revision,
                evidence_relations={missing: "SUPPORTS"},
                created_at="2026-08-09T16:21:00+09:00",
                actor="SORA",
            )

    def test_relation_map_must_cover_exact_evidence_set(self):
        ledger, fact_id = ledger_with_fact()
        revision = build_hypothesis_revision(
            research(),
            research(confidence="HIGH"),
            revised_at="2026-08-09T16:20:00+09:00",
            trigger_type="EARNINGS",
            trigger_ref="event:6622:q1",
            reasoning="Evidence increased confidence.",
            evidence_fact_refs=[fact_id],
        )
        with self.assertRaises(HypothesisRevisionAdapterError):
            attach_revision_evidence_lineage(
                ledger,
                revision,
                evidence_relations={},
                created_at="2026-08-09T16:21:00+09:00",
                actor="SORA",
            )

    def test_invalid_evidence_relation_fails_closed(self):
        ledger, fact_id = ledger_with_fact()
        revision = build_hypothesis_revision(
            research(),
            research(confidence="HIGH"),
            revised_at="2026-08-09T16:20:00+09:00",
            trigger_type="EARNINGS",
            trigger_ref="event:6622:q1",
            reasoning="Evidence increased confidence.",
            evidence_fact_refs=[fact_id],
        )
        with self.assertRaises(HypothesisRevisionAdapterError):
            attach_revision_evidence_lineage(
                ledger,
                revision,
                evidence_relations={fact_id: "DERIVED_FROM"},
                created_at="2026-08-09T16:21:00+09:00",
                actor="SORA",
            )

    def test_lineage_rerun_is_idempotent_and_inputs_are_unchanged(self):
        ledger, fact_id = ledger_with_fact()
        before = research()
        after = research(confidence="HIGH")
        before_copy = copy.deepcopy(before)
        after_copy = copy.deepcopy(after)
        revision = build_hypothesis_revision(
            before,
            after,
            revised_at="2026-08-09T16:20:00+09:00",
            trigger_type="EARNINGS",
            trigger_ref="event:6622:q1",
            reasoning="Orders evidence increased confidence.",
            evidence_fact_refs=[fact_id],
        )
        first = attach_revision_evidence_lineage(
            ledger,
            revision,
            evidence_relations={fact_id: "SUPPORTS"},
            created_at="2026-08-09T16:21:00+09:00",
            actor="SORA",
        )
        second = attach_revision_evidence_lineage(
            ledger,
            revision,
            evidence_relations={fact_id: "SUPPORTS"},
            created_at="2026-08-09T16:21:00+09:00",
            actor="SORA",
        )
        self.assertEqual(first, second)
        self.assertEqual(len(ledger.to_dict()["edges"]), 2)
        self.assertEqual(before, before_copy)
        self.assertEqual(after, after_copy)


if __name__ == "__main__":
    unittest.main()
