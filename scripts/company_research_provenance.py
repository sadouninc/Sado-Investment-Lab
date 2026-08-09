from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from scripts.company_research import CompanyResearchRecord
from scripts.evidence_provenance import ProvenanceLedger, ProvenanceValidationError


class CompanyResearchProvenanceError(ValueError):
    """Raised when Company Research cannot be mapped to provenance without guessing."""


@dataclass(frozen=True)
class CompanyFactSpec:
    """Explicit mapping from one canonical Research value to one Fact Record.

    The adapter deliberately requires paths/period/unit/source instead of inferring
    them from field names. That keeps provenance deterministic and fail-closed.
    """

    path: str
    field: str
    period: str
    unit: str | None
    source_ref: str
    as_of: str
    locator: str | None = None
    confidence: str = "HIGH"


def _resolve_path(raw: Mapping[str, Any], path: str) -> Any:
    current: Any = raw
    for token in path.split("."):
        if not isinstance(current, Mapping) or token not in current:
            raise CompanyResearchProvenanceError(f"fact path is unavailable: {path}")
        current = current[token]
    return current


def _source_metadata(source_ref: str, source_catalog: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    raw = source_catalog.get(source_ref)
    if raw is None:
        raise CompanyResearchProvenanceError(f"source metadata unavailable: {source_ref}")
    candidate = dict(raw)
    if candidate.get("canonical_ref") not in (None, source_ref):
        raise CompanyResearchProvenanceError("source catalog canonical_ref does not match Research source_ref")
    candidate["canonical_ref"] = source_ref
    return candidate


def adapt_company_research_facts(
    raw_research: Mapping[str, Any],
    *,
    source_catalog: Mapping[str, Mapping[str, Any]],
    fact_specs: Sequence[CompanyFactSpec],
) -> dict[str, Any]:
    """Register explicit Company Research Facts and return a non-mutating projection.

    Important safety boundary:
    - Company Research must pass its CURRENT quality gate.
    - every Fact mapping is explicit (path/period/unit/source/as_of)
    - source metadata is supplied by an authority-aware upstream catalog
    - no publisher/date/unit/period is inferred from a URL or field name
    - the canonical Company Research object is never modified
    """

    before = copy.deepcopy(raw_research)
    record = CompanyResearchRecord.from_mapping(raw_research)
    if record.status != "CURRENT":
        raise CompanyResearchProvenanceError("provenance adapter requires CURRENT Company Research")
    if not fact_specs:
        raise CompanyResearchProvenanceError("at least one explicit fact spec is required")

    research_source_refs = set(record.source_refs)
    ledger = ProvenanceLedger()
    source_ids: dict[str, str] = {}
    fact_refs: list[dict[str, Any]] = []

    for spec in fact_specs:
        if spec.source_ref not in research_source_refs:
            raise CompanyResearchProvenanceError(
                f"fact source_ref is not declared by Company Research: {spec.source_ref}"
            )
        if spec.source_ref not in source_ids:
            try:
                source = ledger.ingest_source(_source_metadata(spec.source_ref, source_catalog))
            except ProvenanceValidationError as exc:
                raise CompanyResearchProvenanceError(f"invalid source metadata for {spec.source_ref}: {exc}") from exc
            source_ids[spec.source_ref] = source.source_id

        value = _resolve_path(raw_research, spec.path)
        try:
            fact = ledger.ingest_fact(
                {
                    "source_id": source_ids[spec.source_ref],
                    "entity_type": "COMPANY",
                    "entity_id": record.security_code,
                    "field": spec.field,
                    "value": copy.deepcopy(value),
                    "unit": spec.unit,
                    "period": spec.period,
                    "as_of": spec.as_of,
                    "locator": spec.locator,
                    "confidence": spec.confidence,
                }
            )
        except ProvenanceValidationError as exc:
            raise CompanyResearchProvenanceError(f"invalid Fact mapping for {spec.path}: {exc}") from exc
        fact_refs.append(
            {
                "path": spec.path,
                "fact_id": fact.fact_id,
                "source_id": fact.source_id,
                "source_ref": spec.source_ref,
            }
        )

    if raw_research != before:
        raise CompanyResearchProvenanceError("canonical Company Research was mutated")

    fact_refs = sorted(fact_refs, key=lambda item: (item["path"], item["fact_id"]))
    return {
        "security_code": record.security_code,
        "research_as_of": record.as_of,
        "fact_refs": fact_refs,
        "ledger": ledger.to_dict(),
    }
