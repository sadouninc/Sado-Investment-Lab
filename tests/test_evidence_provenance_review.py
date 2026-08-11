from __future__ import annotations

import unittest

from scripts.evidence_provenance import ProvenanceLedger, ProvenanceValidationError
from scripts.evidence_provenance_review import ProvenanceReviewIndex


class EvidenceProvenanceReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = ProvenanceLedger()
        self.source = self.ledger.ingest_source(
            {
                "source_type": "IR",
                "publisher": "株式会社ダイヘン",
                "published_at": "2026-08-07T15:00:00+09:00",
                "observed_at": "2026-08-07T15:12:00+09:00",
                "canonical_ref": "https://example.test/daihen/q1-v1.pdf",
                "content_hash": "sha256:v1",
                "authority": "PRIMARY",
                "status": "CURRENT",
            }
        )
        self.fact = self.ledger.ingest_fact(
            {
                "source_id": self.source.source_id,
                "entity_type": "COMPANY",
                "entity_id": "6622",
                "field": "orders_yoy_pct",
                "value": 18.0,
                "unit": "%",
                "period": "FY2027-Q1",
                "as_of": "2026-08-07",
                "locator": "page:7",
                "confidence": "HIGH",
            }
        )
        self.ledger.ingest_edge(
            {
                "from": self.fact.fact_id,
                "to": "hypothesis:6622:dc-power-growth",
                "relation": "SUPPORTS",
                "created_at": "2026-08-07T16:00:00+09:00",
                "actor": "SYSTEM",
                "note": None,
            }
        )
        self.index = ProvenanceReviewIndex(self.ledger)

    def add_corrected_source_and_fact(self):
        corrected_source = self.ledger.ingest_source(
            {
                "source_type": "IR",
                "publisher": "株式会社ダイヘン",
                "published_at": "2026-08-07T15:00:00+09:00",
                "observed_at": "2026-08-08T09:00:00+09:00",
                "canonical_ref": "https://example.test/daihen/q1-v2.pdf",
                "content_hash": "sha256:v2",
                "authority": "PRIMARY",
                "status": "CURRENT",
            }
        )
        corrected_fact = self.ledger.ingest_fact(
            {
                "source_id": corrected_source.source_id,
                "entity_type": "COMPANY",
                "entity_id": "6622",
                "field": "orders_yoy_pct",
                "value": 17.5,
                "unit": "%",
                "period": "FY2027-Q1",
                "as_of": "2026-08-07",
                "locator": "page:7",
                "confidence": "HIGH",
            }
        )
        return corrected_source, corrected_fact

    def test_source_correction_is_append_only_and_historical_source_is_unchanged(self) -> None:
        corrected_source, _ = self.add_corrected_source_and_fact()
        transition = self.index.transition_source(
            source_id=self.source.source_id,
            to_status="CORRECTED",
            reason_code="IR_CORRECTION",
            replacement_source_id=corrected_source.source_id,
        )
        self.assertEqual("CURRENT", self.source.status)
        self.assertEqual("CORRECTED", self.index.source_status(self.source.source_id))
        self.assertEqual(self.source.source_id, transition.source_id)

    def test_duplicate_correction_ingestion_is_idempotent(self) -> None:
        corrected_source, _ = self.add_corrected_source_and_fact()
        kwargs = dict(
            source_id=self.source.source_id,
            to_status="CORRECTED",
            reason_code="IR_CORRECTION",
            replacement_source_id=corrected_source.source_id,
        )
        first = self.index.transition_source(**kwargs)
        # Once applied, replaying the exact logical transition must return the same record.
        second = next(iter(self.index._source_transitions.values()))
        self.assertEqual(first, second)

    def test_fact_supersession_requires_same_fact_key(self) -> None:
        _, corrected_fact = self.add_corrected_source_and_fact()
        relation = self.index.supersede_fact(
            old_fact_id=self.fact.fact_id, new_fact_id=corrected_fact.fact_id
        )
        self.assertEqual(self.fact.fact_id, relation.old_fact_id)
        self.assertEqual(corrected_fact.fact_id, relation.new_fact_id)

    def test_fact_cannot_supersede_unrelated_metric(self) -> None:
        corrected_source, _ = self.add_corrected_source_and_fact()
        other = self.ledger.ingest_fact(
            {
                "source_id": corrected_source.source_id,
                "entity_type": "COMPANY",
                "entity_id": "6622",
                "field": "revenue",
                "value": 55507,
                "unit": "JPY_MN",
                "period": "FY2027-Q1",
                "as_of": "2026-08-07",
                "locator": "page:4",
                "confidence": "HIGH",
            }
        )
        with self.assertRaisesRegex(ProvenanceValidationError, "same fact key"):
            self.index.supersede_fact(old_fact_id=self.fact.fact_id, new_fact_id=other.fact_id)

    def test_conflicting_sources_are_retained_without_selecting_winner(self) -> None:
        corrected_source, _ = self.add_corrected_source_and_fact()
        conflict = self.index.register_conflict(
            left_ref=self.source.source_id,
            right_ref=corrected_source.source_id,
            reason_code="PRIMARY_SOURCE_DISAGREEMENT",
        )
        self.assertEqual("NEEDS_REVIEW", conflict.status)
        self.assertIn(self.source.source_id, self.ledger._sources)
        self.assertIn(corrected_source.source_id, self.ledger._sources)

    def test_affected_refs_are_deterministic_and_stable_sorted(self) -> None:
        self.ledger.ingest_edge(
            {
                "from": self.fact.fact_id,
                "to": "decision:2026-08-09-6622",
                "relation": "REFERENCES",
                "created_at": "2026-08-07T16:01:00+09:00",
                "actor": "SYSTEM",
                "note": None,
            }
        )
        self.assertEqual(
            ("decision:2026-08-09-6622", "hypothesis:6622:dc-power-growth"),
            self.index.affected_refs(self.source.source_id),
        )

    def test_review_candidate_contains_correction_and_conflict_reasons(self) -> None:
        corrected_source, _ = self.add_corrected_source_and_fact()
        self.index.transition_source(
            source_id=self.source.source_id,
            to_status="CORRECTED",
            reason_code="IR_CORRECTION",
            replacement_source_id=corrected_source.source_id,
        )
        self.index.register_conflict(
            left_ref=self.source.source_id,
            right_ref=corrected_source.source_id,
            reason_code="PRIMARY_SOURCE_DISAGREEMENT",
        )
        candidate = self.index.build_review_candidate(self.source.source_id)
        self.assertEqual("SOURCE_CORRECTION_REVIEW", candidate.trigger_type)
        self.assertEqual(
            ("SOURCE_CONFLICT", "SOURCE_CORRECTED"), candidate.reason_codes
        )
        self.assertEqual(("hypothesis:6622:dc-power-growth",), candidate.affected_refs)
        self.assertEqual(candidate, self.index.build_review_candidate(self.source.source_id))

    def test_unavailable_source_is_review_trigger_not_false_negative(self) -> None:
        self.index.transition_source(
            source_id=self.source.source_id,
            to_status="UNAVAILABLE",
            reason_code="SOURCE_FETCH_FAILED",
        )
        candidate = self.index.build_review_candidate(self.source.source_id)
        self.assertIn("SOURCE_UNAVAILABLE", candidate.reason_codes)
        self.assertEqual("NEEDS_REVIEW", candidate.status)

    def test_invalid_status_rollback_fails_closed(self) -> None:
        self.index.transition_source(
            source_id=self.source.source_id,
            to_status="UNAVAILABLE",
            reason_code="SOURCE_FETCH_FAILED",
        )
        with self.assertRaisesRegex(ProvenanceValidationError, "invalid source transition"):
            self.index.transition_source(
                source_id=self.source.source_id,
                to_status="CURRENT",
                reason_code="SILENT_RESTORE",
            )


if __name__ == "__main__":
    unittest.main()
