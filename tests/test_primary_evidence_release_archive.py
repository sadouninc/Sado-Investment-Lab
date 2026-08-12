from __future__ import annotations

import hashlib
import unittest

from scripts.evidence_provenance import ProvenanceValidationError
from scripts.primary_evidence_release_archive import (
    GitHubReleaseArchiveAdapter,
    archive_ref_for,
    release_asset_name,
    release_tag_for,
    validate_uploaded_asset,
    verify_payload,
)


SOURCE_ID = "source:111111111111111111111111"
FILENAME = "FY2027-Q1-results.pdf"
PAYLOAD = b"primary evidence pdf bytes"
SHA256 = hashlib.sha256(PAYLOAD).hexdigest()


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.payload


class ReleaseArchiveTests(unittest.TestCase):
    def asset(self) -> dict:
        return {
            "state": "uploaded",
            "size": len(PAYLOAD),
            "name": release_asset_name(SOURCE_ID, FILENAME),
            "browser_download_url": archive_ref_for(SOURCE_ID, FILENAME),
            "digest": "sha256:" + SHA256,
        }

    def test_source_id_determines_release_tag_without_becoming_new_source_identity(self) -> None:
        self.assertEqual(
            "evidence-source-111111111111111111111111",
            release_tag_for(SOURCE_ID),
        )

    def test_asset_name_is_namespaced_by_existing_source_id(self) -> None:
        self.assertEqual(
            "source-111111111111111111111111__FY2027-Q1-results.pdf",
            release_asset_name(SOURCE_ID, FILENAME),
        )

    def test_valid_immutable_uploaded_asset_can_be_promoted_to_archived(self) -> None:
        evidence = validate_uploaded_asset(
            source_id=SOURCE_ID,
            original_filename=FILENAME,
            expected_sha256=SHA256,
            asset=self.asset(),
            release_is_immutable=True,
        )
        self.assertEqual(SHA256, evidence.sha256)
        self.assertEqual(archive_ref_for(SOURCE_ID, FILENAME), evidence.archive_ref)

    def test_mutable_release_fails_closed(self) -> None:
        with self.assertRaisesRegex(ProvenanceValidationError, "must be immutable"):
            validate_uploaded_asset(
                source_id=SOURCE_ID,
                original_filename=FILENAME,
                expected_sha256=SHA256,
                asset=self.asset(),
                release_is_immutable=False,
            )

    def test_github_digest_mismatch_fails_closed(self) -> None:
        asset = self.asset()
        asset["digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ProvenanceValidationError, "digest does not match"):
            validate_uploaded_asset(
                source_id=SOURCE_ID,
                original_filename=FILENAME,
                expected_sha256=SHA256,
                asset=asset,
                release_is_immutable=True,
            )

    def test_wrong_asset_name_fails_closed(self) -> None:
        asset = self.asset()
        asset["name"] = "results.pdf"
        with self.assertRaisesRegex(ProvenanceValidationError, "name does not match"):
            validate_uploaded_asset(
                source_id=SOURCE_ID,
                original_filename=FILENAME,
                expected_sha256=SHA256,
                asset=asset,
                release_is_immutable=True,
            )

    def test_retrieve_rehashes_downloaded_bytes(self) -> None:
        opened = []

        def opener(url, timeout):
            opened.append((url, timeout))
            return FakeResponse(PAYLOAD)

        adapter = GitHubReleaseArchiveAdapter(opener=opener)
        restored = adapter.retrieve(
            archive_ref=archive_ref_for(SOURCE_ID, FILENAME),
            expected_sha256=SHA256,
        )
        self.assertEqual(PAYLOAD, restored)
        self.assertEqual(1, len(opened))

    def test_retrieve_detects_tampering(self) -> None:
        adapter = GitHubReleaseArchiveAdapter(opener=lambda url, timeout: FakeResponse(b"changed"))
        with self.assertRaisesRegex(ProvenanceValidationError, "sha256 mismatch"):
            adapter.retrieve(
                archive_ref=archive_ref_for(SOURCE_ID, FILENAME),
                expected_sha256=SHA256,
            )

    def test_external_archive_ref_is_rejected(self) -> None:
        adapter = GitHubReleaseArchiveAdapter(opener=lambda url, timeout: FakeResponse(PAYLOAD))
        with self.assertRaisesRegex(ProvenanceValidationError, "this repository"):
            adapter.retrieve(
                archive_ref="https://example.test/results.pdf",
                expected_sha256=SHA256,
            )

    def test_verify_payload_accepts_sha256_prefix(self) -> None:
        self.assertEqual(SHA256, verify_payload(PAYLOAD, "sha256:" + SHA256))


if __name__ == "__main__":
    unittest.main()
