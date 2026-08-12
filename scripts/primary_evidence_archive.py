from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from scripts.evidence_provenance import ProvenanceValidationError

ACCESS_STATUSES = {"ARCHIVED", "URL_ONLY", "UNAVAILABLE", "NEEDS_RECOVERY"}
SOURCE_ID_RE = re.compile(r"^source:[0-9a-f]{24}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _text(value: Any, field: str, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ProvenanceValidationError(f"{field} is required")
        return None
    text = str(value).strip()
    if not text and required:
        raise ProvenanceValidationError(f"{field} is required")
    return text or None


def _time(value: Any, field: str) -> str | None:
    text = _text(value, field)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProvenanceValidationError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ProvenanceValidationError(f"{field} must include timezone information")
    return parsed.astimezone(timezone.utc).isoformat()


def _source_id(value: Any) -> str:
    source_id = _text(value, "source_id", required=True)
    assert source_id is not None
    if not SOURCE_ID_RE.fullmatch(source_id):
        raise ProvenanceValidationError("source_id must be an existing #144 SourceRecord identity")
    return source_id


def _sha256(value: Any) -> str | None:
    text = _text(value, "sha256")
    if text is None:
        return None
    digest = text.lower().removeprefix("sha256:")
    if not SHA256_RE.fullmatch(digest):
        raise ProvenanceValidationError("sha256 must be 64 hexadecimal characters")
    return digest


@dataclass(frozen=True)
class PrimaryEvidenceArchiveRecord:
    source_id: str
    access_status: str
    archive_ref: str | None
    ingress_ref: str | None
    original_url: str | None
    sha256: str | None
    original_filename: str | None
    received_at: str | None
    received_by: str | None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "PrimaryEvidenceArchiveRecord":
        allowed = set(cls.__dataclass_fields__)
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise ProvenanceValidationError("unsupported archive fields: " + ", ".join(unknown))
        status = (_text(raw.get("access_status"), "access_status", required=True) or "").upper()
        if status not in ACCESS_STATUSES:
            raise ProvenanceValidationError(f"unsupported access_status: {status}")
        archive_ref = _text(raw.get("archive_ref"), "archive_ref")
        if status == "ARCHIVED" and archive_ref is None:
            raise ProvenanceValidationError("ARCHIVED requires retrievable archive_ref")
        if status != "ARCHIVED" and archive_ref is not None:
            raise ProvenanceValidationError("archive_ref is only valid for ARCHIVED")
        received_by = _text(raw.get("received_by"), "received_by")
        return cls(
            source_id=_source_id(raw.get("source_id")),
            access_status=status,
            archive_ref=archive_ref,
            ingress_ref=_text(raw.get("ingress_ref"), "ingress_ref"),
            original_url=_text(raw.get("original_url"), "original_url"),
            sha256=_sha256(raw.get("sha256")),
            original_filename=_text(raw.get("original_filename"), "original_filename"),
            received_at=_time(raw.get("received_at"), "received_at"),
            received_by=received_by.upper() if received_by else None,
        )


class PrimaryEvidenceArchiveRegistry:
    def __init__(self) -> None:
        self._records: dict[str, PrimaryEvidenceArchiveRecord] = {}

    def ingest(self, raw: Mapping[str, Any]) -> PrimaryEvidenceArchiveRecord:
        record = PrimaryEvidenceArchiveRecord.from_mapping(raw)
        existing = self._records.get(record.source_id)
        if existing is None:
            self._records[record.source_id] = record
            return record
        if existing == record:
            return existing
        raise ProvenanceValidationError(f"conflicting archive metadata: {record.source_id}")

    def duplicate_binary_candidates(self) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for record in self._records.values():
            if record.sha256:
                grouped.setdefault(record.sha256, []).append(record.source_id)
        return {key: sorted(ids) for key, ids in grouped.items() if len(ids) > 1}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "records": [asdict(self._records[key]) for key in sorted(self._records)],
        }
