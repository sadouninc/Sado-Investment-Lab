from __future__ import annotations

import unittest

from scripts.evidence_provenance import ProvenanceValidationError
from scripts.primary_evidence_archive import (
    PrimaryEvidenceArchiveRecord,
    PrimaryEvidenceArchiveRegistry,
)


class PrimaryEvidenceArchiveTests(unittest.TestCase):
    def payload(self, source_id: str = "source:111111111111111111111111") -> dict:
        return {
            "source_id": source_id,
            "access_status": "ARCHIVED",
            "archive_ref": "evidence://companies/6622/FY2027-Q1/results.pdf",
            "ingress_ref": "chat-upload:abc",
            "original_url": "https://example.test/results.pdf",
            "sha256": "a" * 64,
            "original_filename": "results.pdf",
            "received_at": "2026-08-12T22:00:00+09:00",
            "received_by": "ASAHI",
        }

    def test_existing_144_source_id_remains_authority(self) -> None:
        record = PrimaryEvidenceArchiveRecord.from_mapping(self.payload())
        self.assertEqual("source:111111111111111111111111", record.source_id)

    def test_archived_requires_archive_ref(self) -> None:
        payload = self.payload()
        payload["archive_ref"] = None
        with self.assertRaisesRegex(ProvenanceValidationError, "ARCHIVED requires"):
            PrimaryEvidenceArchiveRecord.from_mapping(payload)

    def test_url_only_is_not_archived(self) -> None:
        payload = self.payload()
        payload.update(access_status="URL_ONLY", archive_ref=None)
        record = PrimaryEvidenceArchiveRecord.from_mapping(payload)
        self.assertEqual("URL_ONLY", record.access_status)
        self.assertIsNone(record.archive_ref)

    def test_non_archived_cannot_keep_archive_ref(self) -> None:
        payload = self.payload()
        payload["access_status"] = "NEEDS_RECOVERY"
        with self.assertRaisesRegex(ProvenanceValidationError, "only valid for ARCHIVED"):
            PrimaryEvidenceArchiveRecord.from_mapping(payload)

    def test_same_filename_different_source_and_hash_stay_separate(self) -> None:
        registry = PrimaryEvidenceArchiveRegistry()
        first = self.payload("source:111111111111111111111111")
        second = self.payload("source:222222222222222222222222")
        second["sha256"] = "b" * 64
        registry.ingest(first)
        registry.ingest(second)
        self.assertEqual(2, len(registry.to_dict()["records"]))

    def test_different_filename_same_hash_is_binary_dedup_candidate(self) -> None:
        registry = PrimaryEvidenceArchiveRegistry()
        first = self.payload("source:111111111111111111111111")
        second = self.payload("source:222222222222222222222222")
        second["original_filename"] = "renamed-results.pdf"
        registry.ingest(first)
        registry.ingest(second)
        self.assertEqual(
            {
                "a" * 64: [
                    "source:111111111111111111111111",
                    "source:222222222222222222222222",
                ]
            },
            registry.duplicate_binary_candidates(),
        )

    def test_same_filename_hash_unknown_does_not_merge(self) -> None:
        registry = PrimaryEvidenceArchiveRegistry()
        first = self.payload("source:111111111111111111111111")
        second = self.payload("source:222222222222222222222222")
        first["sha256"] = None
        second["sha256"] = None
        registry.ingest(first)
        registry.ingest(second)
        self.assertEqual(2, len(registry.to_dict()["records"]))
        self.assertEqual({}, registry.duplicate_binary_candidates())

    def test_duplicate_ingestion_is_idempotent(self) -> None:
        registry = PrimaryEvidenceArchiveRegistry()
        payload = self.payload()
        first = registry.ingest(payload)
        second = registry.ingest(dict(payload))
        self.assertIs(first, second)
        self.assertEqual(1, len(registry.to_dict()["records"]))

    def test_same_source_conflicting_archive_metadata_fails_closed(self) -> None:
        registry = PrimaryEvidenceArchiveRegistry()
        registry.ingest(self.payload())
        changed = self.payload()
        changed["original_filename"] = "other.pdf"
        with self.assertRaisesRegex(ProvenanceValidationError, "conflicting archive metadata"):
            registry.ingest(changed)

    def test_received_at_is_canonical_utc(self) -> None:
        record = PrimaryEvidenceArchiveRecord.from_mapping(self.payload())
        self.assertEqual("2026-08-12T13:00:00+00:00", record.received_at)

    def test_sha256_prefix_is_normalized(self) -> None:
        payload = self.payload()
        payload["sha256"] = "sha256:" + "A" * 64
        record = PrimaryEvidenceArchiveRecord.from_mapping(payload)
        self.assertEqual("a" * 64, record.sha256)


if __name__ == "__main__":
    unittest.main()
