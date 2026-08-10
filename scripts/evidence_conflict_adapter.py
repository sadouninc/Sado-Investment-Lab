#!/usr/bin/env python3
"""Read-only adapters from Evidence Conflict into #271/#280 contracts."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from evidence_conflict import CONFLICT_TYPES
from research_debt import validate_debt


class EvidenceConflictAdapterError(ValueError):
    pass


def _validated_conflict(conflict: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(conflict, dict):
        raise EvidenceConflictAdapterError("conflict must be an object")
    item = deepcopy(conflict)
    if item.get("conflict_type") not in CONFLICT_TYPES:
        raise EvidenceConflictAdapterError("unsupported conflict_type")
    if item.get("status") not in {"OPEN", "WAITING_FOR_EVIDENCE", "RESOLVED", "RETIRED"}:
        raise EvidenceConflictAdapterError("unsupported conflict status")
    if not item.get("conflict_id") or not item.get("security_code"):
        raise EvidenceConflictAdapterError("conflict_id and security_code are required")
    return item


def project_reasoning_conflict_detail(conflict: dict[str, Any]) -> dict[str, Any]:
    """Project an unresolved conflict as #271 CONFLICTING detail without mutation."""
    item = _validated_conflict(conflict)
    unresolved = item["status"] in {"OPEN", "WAITING_FOR_EVIDENCE"}
    return {
        "status": "CONFLICTING" if unresolved else "SUPPORTED",
        "conflict_ref": item["conflict_id"],
        "conflict_type": item["conflict_type"],
        "claim_refs": sorted({claim["claim_ref"] for claim in item.get("claims", [])}),
        "evidence_refs": sorted({claim["evidence_ref"] for claim in item.get("claims", [])}),
        "resolution_requirement": list(item.get("resolution_requirement", [])),
        "resolution_ref": item.get("resolution_ref"),
        "trade_recommendation": None,
    }


def project_research_debt_candidate(
    conflict: dict[str, Any], *, materiality: str | None, created_at: str
) -> dict[str, Any] | None:
    """Map a material unresolved conflict to #280 debt; never infer materiality."""
    item = _validated_conflict(conflict)
    if item["status"] not in {"OPEN", "WAITING_FOR_EVIDENCE"}:
        return None
    if materiality is None:
        return None
    if materiality not in {"HIGH", "MEDIUM"}:
        return None
    requirements = item.get("resolution_requirement", [])
    question = " / ".join(requirements) if requirements else "矛盾するEvidenceの解消条件を確認する"
    return validate_debt(
        {
            "security_code": item["security_code"],
            "section": "hypothesis",
            "question": question,
            "origin_type": "CONFLICTING",
            "origin_ref": item["conflict_id"],
            "created_at": created_at,
            "materiality": materiality,
            "expected_evidence": [],
            "status": "OPEN",
        }
    )
