from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from scripts.company_research import CompanyResearchRecord
from scripts.primary_evidence_archive import PrimaryEvidenceArchiveRecord


class CompanyResearchArchiveError(ValueError):
    """Raised when Company Research cannot be linked to archived evidence safely."""


@dataclass(frozen=True)
class CompanyResearchEvidenceLink:
    source_ref: str
    source_id: str
    access_status: str
    archive_ref: str | None
    sha256: str | None
    original_filename: str | None


def link_company_research_evidence(
    raw_research: Mapping[str, Any],
    *,
    source_ids_by_ref: Mapping[str, str],
    archive_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Resolve declared Research sources to #414 archive metadata without guessing.

    `source_ids_by_ref` must come from the #144 provenance projection/catalog. The
    adapter never derives a source identity from filename, URL shape, or archive
    location. Missing archive metadata remains visible as URL_ONLY rather than being
    silently promoted to ARCHIVED.
    """
    record = CompanyResearchRecord.from_mapping(raw_research)
    if record.status != "CURRENT":
        raise CompanyResearchArchiveError("archive linkage requires CURRENT Company Research")

    by_source_id: dict[str, PrimaryEvidenceArchiveRecord] = {}
    for raw in archive_records:
        archive = PrimaryEvidenceArchiveRecord.from_mapping(raw)
        if archive.source_id in by_source_id and by_source_id[archive.source_id] != archive:
            raise CompanyResearchArchiveError(f"conflicting archive metadata: {archive.source_id}")
        by_source_id[archive.source_id] = archive

    links: list[CompanyResearchEvidenceLink] = []
    for source_ref in record.source_refs:
        source_id = source_ids_by_ref.get(source_ref)
        if not source_id:
            raise CompanyResearchArchiveError(f"#144 source_id unavailable for Research source_ref: {source_ref}")
        archive = by_source_id.get(source_id)
        if archive is None:
            links.append(
                CompanyResearchEvidenceLink(
                    source_ref=source_ref,
                    source_id=source_id,
                    access_status="URL_ONLY",
                    archive_ref=None,
                    sha256=None,
                    original_filename=None,
                )
            )
            continue
        links.append(
            CompanyResearchEvidenceLink(
                source_ref=source_ref,
                source_id=source_id,
                access_status=archive.access_status,
                archive_ref=archive.archive_ref,
                sha256=archive.sha256,
                original_filename=archive.original_filename,
            )
        )

    return {
        "security_code": record.security_code,
        "company_name": record.company_name,
        "research_as_of": record.as_of,
        "evidence_links": [asdict(item) for item in sorted(links, key=lambda item: item.source_ref)],
    }
