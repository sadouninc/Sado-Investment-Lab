from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping, Sequence

from scripts.primary_evidence_archive import PrimaryEvidenceArchiveRecord


@dataclass(frozen=True)
class CoverageRow:
    security_code: str
    company_name: str
    research_status: str
    source_count: int
    archived_count: int
    url_only_count: int
    unavailable_count: int
    needs_recovery_count: int
    coverage_state: str


def audit_primary_evidence_coverage(
    *,
    targets: Sequence[Mapping[str, str]],
    research_catalog: Mapping[str, Mapping[str, Any]],
    source_ids_by_ref: Mapping[str, str],
    archive_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Audit Primary Evidence coverage without inventing missing Research or Sources.

    Coverage semantics:
    - RESEARCH_MISSING: no canonical Company Research exists for target company.
    - SOURCE_ID_MISSING: Research exists but at least one declared source_ref cannot be
      resolved to existing #144 source identity.
    - ARCHIVED: every declared source has a #414 ARCHIVED record.
    - PARTIAL: mixed explicit archive states.
    - URL_ONLY: all declared sources resolve to #144 but none are archived and all
      are currently URL_ONLY / absent from archive metadata.
    - NEEDS_RECOVERY / UNAVAILABLE: explicit archive state takes precedence.
    """
    archives: dict[str, PrimaryEvidenceArchiveRecord] = {}
    for raw in archive_records:
        record = PrimaryEvidenceArchiveRecord.from_mapping(raw)
        existing = archives.get(record.source_id)
        if existing is not None and existing != record:
            raise ValueError(f"conflicting archive metadata: {record.source_id}")
        archives[record.source_id] = record

    rows: list[CoverageRow] = []
    for target in targets:
        code = str(target["security_code"])
        name = str(target["company_name"])
        research = research_catalog.get(code)
        if research is None:
            rows.append(CoverageRow(code, name, "MISSING", 0, 0, 0, 0, 0, "RESEARCH_MISSING"))
            continue

        refs = list(dict.fromkeys(str(x) for x in research.get("source_refs", []) if str(x).strip()))
        if not refs:
            rows.append(CoverageRow(code, name, str(research.get("status", "UNKNOWN")), 0, 0, 0, 0, 0, "SOURCE_ID_MISSING"))
            continue

        counts = {"ARCHIVED": 0, "URL_ONLY": 0, "UNAVAILABLE": 0, "NEEDS_RECOVERY": 0}
        missing_identity = False
        for ref in refs:
            source_id = source_ids_by_ref.get(ref)
            if not source_id:
                missing_identity = True
                continue
            archive = archives.get(source_id)
            if archive is None:
                counts["URL_ONLY"] += 1
            else:
                counts[archive.access_status] += 1

        if missing_identity:
            state = "SOURCE_ID_MISSING"
        elif counts["NEEDS_RECOVERY"]:
            state = "NEEDS_RECOVERY" if counts["NEEDS_RECOVERY"] == len(refs) else "PARTIAL"
        elif counts["UNAVAILABLE"]:
            state = "UNAVAILABLE" if counts["UNAVAILABLE"] == len(refs) else "PARTIAL"
        elif counts["ARCHIVED"] == len(refs):
            state = "ARCHIVED"
        elif counts["URL_ONLY"] == len(refs):
            state = "URL_ONLY"
        else:
            state = "PARTIAL"

        rows.append(
            CoverageRow(
                security_code=code,
                company_name=name,
                research_status=str(research.get("status", "UNKNOWN")),
                source_count=len(refs),
                archived_count=counts["ARCHIVED"],
                url_only_count=counts["URL_ONLY"],
                unavailable_count=counts["UNAVAILABLE"],
                needs_recovery_count=counts["NEEDS_RECOVERY"],
                coverage_state=state,
            )
        )

    return {
        "schema_version": 1,
        "targets": [asdict(row) for row in sorted(rows, key=lambda row: row.security_code)],
    }
