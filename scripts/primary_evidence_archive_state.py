from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone

from scripts.evidence_provenance import ProvenanceValidationError
from scripts.primary_evidence_archive import ACCESS_STATUSES, PrimaryEvidenceArchiveRecord


@dataclass(frozen=True)
class ArchiveStateTransition:
    source_id: str
    from_status: str
    to_status: str
    changed_at: str
    reason: str


def transition_access_status(
    record: PrimaryEvidenceArchiveRecord,
    *,
    to_status: str,
    changed_at: str,
    reason: str,
    archive_ref: str | None = None,
) -> tuple[PrimaryEvidenceArchiveRecord, ArchiveStateTransition | None]:
    status = str(to_status or "").strip().upper()
    if status not in ACCESS_STATUSES:
        raise ProvenanceValidationError(f"unsupported access_status: {status}")
    reason_text = str(reason or "").strip()
    if not reason_text:
        raise ProvenanceValidationError("transition reason is required")
    try:
        parsed = datetime.fromisoformat(str(changed_at).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProvenanceValidationError("changed_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ProvenanceValidationError("changed_at must include timezone information")
    canonical_changed_at = parsed.astimezone(timezone.utc).isoformat()

    next_archive_ref = str(archive_ref).strip() if archive_ref is not None else None
    if status == "ARCHIVED" and not next_archive_ref:
        raise ProvenanceValidationError("ARCHIVED requires retrievable archive_ref")
    if status != "ARCHIVED":
        next_archive_ref = None

    if record.access_status == status and record.archive_ref == next_archive_ref:
        return record, None

    updated = replace(record, access_status=status, archive_ref=next_archive_ref)
    transition = ArchiveStateTransition(
        source_id=record.source_id,
        from_status=record.access_status,
        to_status=status,
        changed_at=canonical_changed_at,
        reason=reason_text,
    )
    return updated, transition
