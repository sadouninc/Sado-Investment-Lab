from __future__ import annotations

import copy
import re
from typing import Any, Iterable, Mapping

from scripts.company_research import CompanyResearchRecord
from scripts.evidence_provenance import LINEAGE_RELATIONS, ProvenanceLedger, ProvenanceValidationError
from scripts.research_revision_ledger import ResearchRevisionError, validate_revision


class HypothesisRevisionAdapterError(ValueError):
    """Raised when a hypothesis revision cannot be constructed safely."""


HYPOTHESIS_FIELDS = (
    "what_market_may_be_underestimating",
    "must_happen",
    "key_kpis",
    "invalidation_conditions",
    "expected_time_horizon",
    "current_confidence",
)


def _canonical_text(value: Any) -> str:
    """Normalize presentation-only whitespace without guessing semantic equivalence."""
    return re.sub(r"\s+", " ", str(value or "").strip())


def _normalized_value(path: str, value: Any) -> Any:
    if path in {"what_market_may_be_underestimating", "expected_time_horizon"}:
        return _canonical_text(value)
    if isinstance(value, list):
        # Preserve order because must-happen / KPI ordering can carry human meaning.
        return [copy.deepcopy(item) for item in value]
    return copy.deepcopy(value)


def _hypothesis(record: Mapping[str, Any]) -> dict[str, Any]:
    parsed = CompanyResearchRecord.from_mapping(record)
    return {field: copy.deepcopy(parsed.hypothesis.get(field)) for field in HYPOTHESIS_FIELDS}


def _changes(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for field in HYPOTHESIS_FIELDS:
        old = _normalized_value(field, before.get(field))
        new = _normalized_value(field, after.get(field))
        if old == new:
            continue
        if before.get(field) is None and after.get(field) is not None:
            change_type = "ADDED"
        elif before.get(field) is not None and after.get(field) is None:
            change_type = "REMOVED"
        else:
            change_type = "UPDATED"
        changes.append(
            {
                "path": f"hypothesis.{field}",
                "before": copy.deepcopy(before.get(field)),
                "after": copy.deepcopy(after.get(field)),
                "change_type": change_type,
            }
        )
    return changes


def build_hypothesis_revision(
    before_research: Mapping[str, Any],
    after_research: Mapping[str, Any],
    *,
    revised_at: str,
    trigger_type: str,
    trigger_ref: str | None,
    reasoning: str,
    evidence_fact_refs: Iterable[str] = (),
    previous_revision_ref: str | None = None,
    materiality: str = "MATERIAL",
    author_type: str = "ANALYST",
    hypothesis_ref: str | None = None,
) -> dict[str, Any] | None:
    """Create an append-ready HYPOTHESIS Revision only when canonical content changed.

    This adapter deliberately does not decide Thesis Health. In particular, a text
    change is never auto-promoted to THESIS_CHANGING; callers must explicitly supply
    that materiality under the authority of the owning research process.
    """

    before_record = CompanyResearchRecord.from_mapping(before_research)
    after_record = CompanyResearchRecord.from_mapping(after_research)
    if before_record.security_code != after_record.security_code:
        raise HypothesisRevisionAdapterError("security_code mismatch")

    reasoning_text = str(reasoning or "").strip()
    if not reasoning_text:
        raise HypothesisRevisionAdapterError("reasoning is required")

    before = _hypothesis(before_research)
    after = _hypothesis(after_research)
    changed = _changes(before, after)
    if not changed:
        return None

    fact_refs = sorted({str(ref).strip() for ref in evidence_fact_refs if str(ref).strip()})
    security_code = after_record.security_code
    artifact_ref = str(hypothesis_ref or f"hypothesis:{security_code}").strip()
    if not artifact_ref:
        raise HypothesisRevisionAdapterError("hypothesis_ref is required")

    record: dict[str, Any] = {
        "entity_type": "COMPANY",
        "entity_id": security_code,
        "artifact_type": "HYPOTHESIS",
        "artifact_ref": artifact_ref,
        "revised_at": revised_at,
        "trigger_type": trigger_type,
        "trigger_ref": trigger_ref,
        "previous_revision_ref": previous_revision_ref,
        "change_summary": "Investment hypothesis updated",
        "changed_fields": changed,
        "reasoning": reasoning_text,
        "evidence_refs": fact_refs,
        "confidence_before": before.get("current_confidence"),
        "confidence_after": after.get("current_confidence"),
        "materiality": materiality,
        "author_type": author_type,
        "as_of": after_record.as_of,
    }
    try:
        return validate_revision(record)
    except ResearchRevisionError as exc:
        raise HypothesisRevisionAdapterError(str(exc)) from exc


def attach_revision_evidence_lineage(
    ledger: ProvenanceLedger,
    revision: Mapping[str, Any],
    *,
    evidence_relations: Mapping[str, str],
    created_at: str,
    actor: str,
) -> dict[str, Any]:
    """Attach explicit Fact lineage to both Hypothesis and Revision identities.

    Presence of a fact ref alone does not imply SUPPORTS/CHALLENGES. A caller must
    explicitly provide the relation for each evidence fact. Every evidence ref must
    already exist in the #144 Provenance Ledger; otherwise this function fails closed.
    """

    validated = validate_revision(revision)
    if validated.get("artifact_type") != "HYPOTHESIS":
        raise HypothesisRevisionAdapterError("artifact_type=HYPOTHESIS is required")

    expected_refs = set(validated.get("evidence_refs") or [])
    supplied_refs = {str(ref).strip() for ref in evidence_relations}
    if expected_refs != supplied_refs:
        raise HypothesisRevisionAdapterError(
            "evidence_relations must explicitly cover exactly the revision evidence_refs"
        )

    known_fact_ids = {row["fact_id"] for row in ledger.to_dict().get("facts", [])}
    missing = sorted(expected_refs - known_fact_ids)
    if missing:
        raise HypothesisRevisionAdapterError(
            "evidence fact is not registered in Provenance Ledger: " + ", ".join(missing)
        )

    hypothesis_edges: list[str] = []
    revision_edges: list[str] = []
    for fact_id in sorted(expected_refs):
        relation = str(evidence_relations[fact_id] or "").upper()
        if relation not in LINEAGE_RELATIONS - {"DERIVED_FROM", "SUPERSEDES"}:
            raise HypothesisRevisionAdapterError(f"unsupported hypothesis evidence relation: {relation}")
        try:
            hypothesis_edge = ledger.ingest_edge(
                {
                    "from": fact_id,
                    "to": validated["artifact_ref"],
                    "relation": relation,
                    "created_at": created_at,
                    "actor": actor,
                    "note": "Explicit evidence relation for hypothesis revision",
                }
            )
            revision_edge = ledger.ingest_edge(
                {
                    "from": fact_id,
                    "to": validated["revision_id"],
                    "relation": "REFERENCES",
                    "created_at": created_at,
                    "actor": actor,
                    "note": "Fact referenced by immutable Research Revision",
                }
            )
        except ProvenanceValidationError as exc:
            raise HypothesisRevisionAdapterError(str(exc)) from exc
        hypothesis_edges.append(hypothesis_edge.edge_id)
        revision_edges.append(revision_edge.edge_id)

    return {
        "revision_id": validated["revision_id"],
        "hypothesis_ref": validated["artifact_ref"],
        "fact_refs": sorted(expected_refs),
        "hypothesis_edge_refs": hypothesis_edges,
        "revision_edge_refs": revision_edges,
    }
