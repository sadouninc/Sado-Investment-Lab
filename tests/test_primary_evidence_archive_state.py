from __future__ import annotations

import unittest

from scripts.primary_evidence_archive import PrimaryEvidenceArchiveRecord
from scripts.primary_evidence_archive_state import transition_access_status


class PrimaryEvidenceArchiveStateTests(unittest.TestCase):
    def archived(self) -> PrimaryEvidenceArchiveRecord:
        return PrimaryEvidenceArchiveRecord.from_mapping(
            {
                "source_id": "source:111111111111111111111111",
                "access_status": "ARCHIVED",
                "archive_ref": "evidence://results.pdf",
                "ingress_ref": "drive:file-1",
                "original_url": "https://example.test/results.pdf",
                "sha256": "a" * 64,
                "original_filename": "results.pdf",
                "received_at": "2026-08-12T22:00:00+09:00",
                "received_by": "ASAHI",
            }
        )

    def test_missing_external_object_can_be_marked_needs_recovery(self) -> None:
        original = self.archived()
        updated, transition = transition_access_status(
            original,
            to_status="NEEDS_RECOVERY",
            changed_at="2026-08-12T23:00:00+09:00",
            reason="archive object missing",
        )
        self.assertEqual("ARCHIVED", original.access_status)
        self.assertEqual("NEEDS_RECOVERY", updated.access_status)
        self.assertIsNone(updated.archive_ref)
        self.assertIsNotNone(transition)
        assert transition is not None
        self.assertEqual("ARCHIVED", transition.from_status)
        self.assertEqual("NEEDS_RECOVERY", transition.to_status)

    def test_recovery_can_restore_archived_with_new_ref(self) -> None:
        missing, _ = transition_access_status(
            self.archived(),
            to_status="UNAVAILABLE",
            changed_at="2026-08-12T23:00:00+09:00",
            reason="external object removed",
        )
        restored, transition = transition_access_status(
            missing,
            to_status="ARCHIVED",
            changed_at="2026-08-13T09:00:00+09:00",
            reason="binary recovered",
            archive_ref="evidence://recovered/results.pdf",
        )
        self.assertEqual("ARCHIVED", restored.access_status)
        self.assertEqual("evidence://recovered/results.pdf", restored.archive_ref)
        self.assertIsNotNone(transition)

    def test_same_transition_is_idempotent(self) -> None:
        original = self.archived()
        same, transition = transition_access_status(
            original,
            to_status="ARCHIVED",
            changed_at="2026-08-12T23:00:00+09:00",
            reason="retry",
            archive_ref=original.archive_ref,
        )
        self.assertIs(original, same)
        self.assertIsNone(transition)


if __name__ == "__main__":
    unittest.main()
