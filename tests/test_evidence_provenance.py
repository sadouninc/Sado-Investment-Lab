from __future__ import annotations

import unittest

from scripts.evidence_provenance import (
    FactRecord,
    ProvenanceLedger,
    ProvenanceValidationError,
    SourceRecord,
    deterministic_edge_id,
    deterministic_fact_id,
    deterministic_source_id,
)


class EvidenceProvenanceTests(unittest.TestCase):
    def source_payload(self) -> dict:
        return {
            "source_type": "IR",
            "publisher": "株式会社ダイヘン",
            "published_at": "2026-08-07T15:00:00+09:00",
            "observed_at": "2026-08-07T15:12:00+09:00",
            "canonical_ref": "https://example.test/daihen/2026q1.pdf",
            "content_hash": "sha256:abc",
            "authority": "PRIMARY",
            "status": "CURRENT",
        }

    def fact_payload(self, source_id: str) -> dict:
        return {
            "source_id": source_id,
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

    def test_same_source_metadata_produces_same_identity(self) -> None:
        payload = self.source_payload()
        first = SourceRecord.from_mapping(payload)
        second_payload = dict(payload)
        second_payload["observed_at"] = "2026-08-07T16:00:00+09:00"
        second = SourceRecord.from_mapping(second_payload)
        self.assertEqual(first.source_id, second.source_id)
        self.assertEqual(
            first.source_id,
            deterministic_source_id(
                source_type=payload["source_type"],
                publisher=payload["publisher"],
                published_at=payload["published_at"],
                canonical_ref=payload["canonical_ref"],
                content_hash=payload["content_hash"],
            ),
        )

    def test_equivalent_timestamp_spellings_share_source_identity(self) -> None:
        payload = self.source_payload()
        zulu = deterministic_source_id(
            source_type=payload["source_type"],
            publisher=payload["publisher"],
            published_at="2026-08-07T06:00:00Z",
            canonical_ref=payload["canonical_ref"],
            content_hash=payload["content_hash"],
        )
        utc_offset = deterministic_source_id(
            source_type=payload["source_type"],
            publisher=payload["publisher"],
            published_at="2026-08-07T06:00:00+00:00",
            canonical_ref=payload["canonical_ref"],
            content_hash=payload["content_hash"],
        )
        jst = deterministic_source_id(
            source_type=payload["source_type"],
            publisher=payload["publisher"],
            published_at="2026-08-07T15:00:00+09:00",
            canonical_ref=payload["canonical_ref"],
            content_hash=payload["content_hash"],
        )
        self.assertEqual(zulu, utc_offset)
        self.assertEqual(zulu, jst)

    def test_source_timestamps_serialize_in_canonical_utc_form(self) -> None:
        record = SourceRecord.from_mapping(self.source_payload())
        self.assertEqual("2026-08-07T06:00:00+00:00", record.published_at)
        self.assertEqual("2026-08-07T06:12:00+00:00", record.observed_at)
        payload = ProvenanceLedger()
        payload.ingest_source(self.source_payload())
        serialized = payload.to_dict()["sources"][0]
        self.assertEqual("2026-08-07T06:00:00+00:00", serialized["published_at"])
        self.assertEqual("2026-08-07T06:12:00+00:00", serialized["observed_at"])

    def test_changed_content_hash_changes_source_identity(self) -> None:
        payload = self.source_payload()
        first = SourceRecord.from_mapping(payload)
        changed = dict(payload, content_hash="sha256:def")
        self.assertNotEqual(first.source_id, SourceRecord.from_mapping(changed).source_id)

    def test_same_fact_key_produces_same_fact_identity(self) -> None:
        source = SourceRecord.from_mapping(self.source_payload())
        first = FactRecord.from_mapping(self.fact_payload(source.source_id))
        second_payload = dict(self.fact_payload(source.source_id), value=19.5)
        second = FactRecord.from_mapping(second_payload)
        self.assertEqual(first.fact_id, second.fact_id)
        self.assertEqual(
            first.fact_id,
            deterministic_fact_id(
                source_id=source.source_id,
                entity_type="COMPANY",
                entity_id="6622",
                field="orders_yoy_pct",
                period="FY2027-Q1",
            ),
        )

    def test_fact_rejects_interpretation_fields(self) -> None:
        source = SourceRecord.from_mapping(self.source_payload())
        payload = self.fact_payload(source.source_id)
        payload["interpretation"] = "電力インフラ需要継続を支持"
        with self.assertRaisesRegex(ProvenanceValidationError, "cannot contain interpretation"):
            FactRecord.from_mapping(payload)

    def test_unknown_fields_are_rejected(self) -> None:
        payload = self.source_payload()
        payload["score"] = 100
        with self.assertRaisesRegex(ProvenanceValidationError, "unsupported fields"):
            SourceRecord.from_mapping(payload)

    def test_timezone_is_required_for_source_timestamps(self) -> None:
        payload = self.source_payload()
        payload["published_at"] = "2026-08-07T15:00:00"
        with self.assertRaisesRegex(ProvenanceValidationError, "timezone"):
            SourceRecord.from_mapping(payload)

    def test_duplicate_ingestion_is_idempotent(self) -> None:
        ledger = ProvenanceLedger()
        source_payload = self.source_payload()
        source = ledger.ingest_source(source_payload)
        fact_payload = self.fact_payload(source.source_id)
        fact = ledger.ingest_fact(fact_payload)
        edge_payload = {
            "from": fact.fact_id,
            "to": "hypothesis:6622:dc-power-growth:2026-08",
            "relation": "SUPPORTS",
            "created_at": "2026-08-09T09:00:00+09:00",
            "actor": "NAGI",
            "note": "受注成長がmust_happen条件を支持",
        }
        edge = ledger.ingest_edge(edge_payload)
        self.assertIs(source, ledger.ingest_source(source_payload))
        self.assertIs(fact, ledger.ingest_fact(fact_payload))
        self.assertIs(edge, ledger.ingest_edge(edge_payload))
        self.assertEqual(ledger.ingest(), {"sources": 1, "facts": 1, "edges": 1})

    def test_conflicting_payload_for_same_fact_identity_is_rejected(self) -> None:
        ledger = ProvenanceLedger()
        source = ledger.ingest_source(self.source_payload())
        ledger.ingest_fact(self.fact_payload(source.source_id))
        changed = dict(self.fact_payload(source.source_id), value=999.0)
        with self.assertRaisesRegex(ProvenanceValidationError, "conflicting payload"):
            ledger.ingest_fact(changed)

    def test_fact_requires_registered_source(self) -> None:
        unknown_source = "source:" + "0" * 24
        with self.assertRaisesRegex(ProvenanceValidationError, "not registered"):
            ProvenanceLedger().ingest_fact(self.fact_payload(unknown_source))

    def test_edge_identity_ignores_note_and_timestamp(self) -> None:
        expected = deterministic_edge_id(
            from_id="fact:abc",
            to_id="hypothesis:def",
            relation="SUPPORTS",
        )
        same = deterministic_edge_id(
            from_id="fact:abc",
            to_id="hypothesis:def",
            relation="supports",
        )
        self.assertEqual(expected, same)

    def test_edge_source_must_exist_but_downstream_target_may_be_external(self) -> None:
        ledger = ProvenanceLedger()
        source = ledger.ingest_source(self.source_payload())
        fact = ledger.ingest_fact(self.fact_payload(source.source_id))
        edge = ledger.ingest_edge(
            {
                "from": fact.fact_id,
                "to": "decision:2026-08-09-6622-BUY-001",
                "relation": "REFERENCES",
                "created_at": "2026-08-09T09:00:00+09:00",
                "actor": "SADO",
                "note": None,
            }
        )
        self.assertEqual(edge.from_id, fact.fact_id)
        self.assertEqual("2026-08-09T00:00:00+00:00", edge.created_at)

    def test_serialized_contract_uses_from_and_to_keys(self) -> None:
        ledger = ProvenanceLedger()
        source = ledger.ingest_source(self.source_payload())
        fact = ledger.ingest_fact(self.fact_payload(source.source_id))
        ledger.ingest_edge(
            {
                "from": fact.fact_id,
                "to": "hypothesis:6622:dc-power-growth:2026-08",
                "relation": "SUPPORTS",
                "created_at": "2026-08-09T09:00:00+09:00",
                "actor": "SYSTEM",
                "note": None,
            }
        )
        payload = ledger.to_dict()
        self.assertEqual(payload["schema_version"], 1)
        self.assertIn("from", payload["edges"][0])
        self.assertIn("to", payload["edges"][0])
        self.assertNotIn("from_id", payload["edges"][0])


if __name__ == "__main__":
    unittest.main()
