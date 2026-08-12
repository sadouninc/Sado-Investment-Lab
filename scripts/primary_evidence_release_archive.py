from __future__ import annotations

import hashlib
import re
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import quote

from scripts.evidence_provenance import ProvenanceValidationError

REPOSITORY = "sadouninc/Sado-Investment-Lab"
MAX_RELEASE_ASSET_BYTES = 2 * 1024 * 1024 * 1024
SOURCE_ID_RE = re.compile(r"^source:([0-9a-f]{24})$")
DIGEST_RE = re.compile(r"^sha256:([0-9a-f]{64})$")


def _source_hex(source_id: str) -> str:
    match = SOURCE_ID_RE.fullmatch(str(source_id or "").strip())
    if not match:
        raise ProvenanceValidationError("source_id must be an existing #144 SourceRecord identity")
    return match.group(1)


def _sha256(value: str) -> str:
    digest = str(value or "").strip().lower().removeprefix("sha256:")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ProvenanceValidationError("sha256 must be 64 hexadecimal characters")
    return digest


def release_tag_for(source_id: str) -> str:
    return f"evidence-source-{_source_hex(source_id)}"


def release_asset_name(source_id: str, original_filename: str) -> str:
    filename = str(original_filename or "").strip().replace("/", "_").replace("\\", "_")
    if not filename:
        raise ProvenanceValidationError("original_filename is required")
    return f"source-{_source_hex(source_id)}__{filename}"


def archive_ref_for(source_id: str, original_filename: str) -> str:
    tag = quote(release_tag_for(source_id), safe="")
    asset = quote(release_asset_name(source_id, original_filename), safe="")
    return f"https://github.com/{REPOSITORY}/releases/download/{tag}/{asset}"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def verify_payload(payload: bytes, expected_sha256: str) -> str:
    expected = _sha256(expected_sha256)
    actual = sha256_bytes(payload)
    if actual != expected:
        raise ProvenanceValidationError(f"archive payload sha256 mismatch: expected={expected} actual={actual}")
    return actual


def reusable_archive_ref(records: Iterable[Mapping[str, Any]], sha256: str) -> str | None:
    """Return one existing immutable binary ref without merging Source identities."""

    digest = _sha256(sha256)
    refs = {
        str(record.get("archive_ref") or "").strip()
        for record in records
        if str(record.get("access_status") or "").upper() == "ARCHIVED"
        and str(record.get("sha256") or "").lower().removeprefix("sha256:") == digest
        and str(record.get("archive_ref") or "").strip()
    }
    if not refs:
        return None
    if len(refs) > 1:
        raise ProvenanceValidationError("same sha256 points to multiple ARCHIVED binaries")
    return next(iter(refs))


@dataclass(frozen=True)
class ReleaseAssetEvidence:
    source_id: str
    archive_ref: str
    sha256: str
    size: int
    release_tag: str
    asset_name: str


def validate_uploaded_asset(
    *,
    source_id: str,
    original_filename: str,
    expected_sha256: str,
    asset: Mapping[str, Any],
    release_is_immutable: bool,
) -> ReleaseAssetEvidence:
    if release_is_immutable is not True:
        raise ProvenanceValidationError("release must be immutable before access_status can become ARCHIVED")

    expected_ref = archive_ref_for(source_id, original_filename)
    expected_name = release_asset_name(source_id, original_filename)
    expected_tag = release_tag_for(source_id)
    state = str(asset.get("state") or "").strip().lower()
    if state != "uploaded":
        raise ProvenanceValidationError("release asset state must be uploaded")

    size = asset.get("size")
    if not isinstance(size, int) or size < 0:
        raise ProvenanceValidationError("release asset size must be a non-negative integer")
    if size >= MAX_RELEASE_ASSET_BYTES:
        raise ProvenanceValidationError("release asset must be smaller than 2 GiB")

    if str(asset.get("name") or "") != expected_name:
        raise ProvenanceValidationError("release asset name does not match canonical #414 name")
    if str(asset.get("browser_download_url") or "") != expected_ref:
        raise ProvenanceValidationError("release asset download URL does not match canonical archive_ref")

    expected = _sha256(expected_sha256)
    digest_match = DIGEST_RE.fullmatch(str(asset.get("digest") or "").strip().lower())
    if not digest_match:
        raise ProvenanceValidationError("release asset must expose a sha256 digest")
    digest = digest_match.group(1)
    if digest != expected:
        raise ProvenanceValidationError("release asset digest does not match local sha256")

    return ReleaseAssetEvidence(
        source_id=source_id,
        archive_ref=expected_ref,
        sha256=digest,
        size=size,
        release_tag=expected_tag,
        asset_name=expected_name,
    )


class GitHubReleaseArchiveAdapter:
    """Read adapter for immutable GitHub Release assets.

    Publishing is intentionally performed by a release-capable caller. This adapter
    validates the GitHub response before a registry record can be promoted to
    ARCHIVED, and always re-hashes retrieved bytes.
    """

    def __init__(self, opener: Callable[..., Any] | None = None) -> None:
        self._opener = opener or urllib.request.urlopen

    def retrieve(self, *, archive_ref: str, expected_sha256: str, timeout: int = 30) -> bytes:
        ref = str(archive_ref or "").strip()
        prefix = f"https://github.com/{REPOSITORY}/releases/download/"
        if not ref.startswith(prefix):
            raise ProvenanceValidationError("archive_ref must point to this repository's GitHub Release asset")
        with self._opener(ref, timeout=timeout) as response:
            payload = response.read()
        verify_payload(payload, expected_sha256)
        return payload
