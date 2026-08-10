#!/usr/bin/env python3
"""Pure Evidence Conflict contract/detector for Issue #299 PR1."""
from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any

CONFLICT_TYPES = {
    "VALUE_MISMATCH", "BASIS_MISMATCH", "PERIOD_MISMATCH",
    "DEFINITION_CHANGE", "INTERPRETATION_DIVERGENCE", "UNKNOWN",
}
SUBJECT_KINDS = {"FACT", "KPI", "GUIDANCE", "EXPECTATION", "INTERPRETATION", "HYPOTHESIS_EVIDENCE"}


class EvidenceConflictError(ValueError):
    pass


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceConflictError(f"{field} must be a non-empty string")
    return value.strip()


def _claim(raw: Any, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise EvidenceConflictError(f"claims[{index}] must be an object")
    item = deepcopy(raw)
    kind = _text(item.get("kind"), f"claims[{index}].kind")
    if kind not in SUBJECT_KINDS:
        raise EvidenceConflictError(f"unsupported subject kind: {kind}")
    return {
        "claim_ref": _text(item.get("claim_ref"), f"claims[{index}].claim_ref"),
        "evidence_ref": _text(item.get("evidence_ref"), f"claims[{index}].evidence_ref"),
        "kind": kind,
        "metric": _text(item.get("metric"), f"claims[{index}].metric"),
        "fiscal_period": _text(item.get("fiscal_period"), f"claims[{index}].fiscal_period"),
        "unit": _text(item.get("unit"), f"claims[{index}].unit"),
        "basis": _text(item.get("basis"), f"claims[{index}].basis"),
        "definition": _text(item.get("definition"), f"claims[{index}].definition"),
        "value": item.get("value"),
        "as_of": _text(item.get("as_of"), f"claims[{index}].as_of"),
    }


def _identity(security_code: str, claims: list[dict[str, Any]]) -> str:
    parts = [security_code]
    for claim in sorted(claims, key=lambda row: (row["claim_ref"], row["evidence_ref"])):
        parts.append("|".join((claim["kind"], claim["metric"], claim["fiscal_period"], claim["unit"], claim["basis"], claim["definition"], claim["claim_ref"], claim["evidence_ref"])))
    return f"EC-{security_code}-{hashlib.sha256('||'.join(parts).encode('utf-8')).hexdigest()[:16]}"


def detect_conflict(security_code: str, raw_claims: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify claims without mutation, conversion, averaging, or newest-source preference."""
    security_code = _text(security_code, "security_code")
    if not isinstance(raw_claims, list) or len(raw_claims) < 2:
        raise EvidenceConflictError("claims must contain at least two items")
    claims = [_claim(raw, i) for i, raw in enumerate(raw_claims)]

    metrics = {c["metric"] for c in claims}
    if len(metrics) != 1:
        conflict_type, requirements = "UNKNOWN", ["ALIGN_METRIC_IDENTITY"]
    elif len({c["fiscal_period"] for c in claims}) != 1:
        conflict_type, requirements = "PERIOD_MISMATCH", ["ALIGN_FISCAL_PERIOD"]
    elif len({c["unit"] for c in claims}) != 1:
        conflict_type, requirements = "UNKNOWN", ["ALIGN_UNIT"]
    elif len({c["basis"] for c in claims}) != 1:
        conflict_type, requirements = "BASIS_MISMATCH", ["VERIFY_METRIC_BASIS"]
    elif len({c["definition"] for c in claims}) != 1:
        conflict_type, requirements = "DEFINITION_CHANGE", ["VERIFY_METRIC_DEFINITION"]
    elif any(c["kind"] == "INTERPRETATION" for c in claims) and len({repr(c["value"]) for c in claims}) != 1:
        conflict_type, requirements = "INTERPRETATION_DIVERGENCE", ["OWNER_INTERPRETATION_REQUIRED"]
    elif len({repr(c["value"]) for c in claims}) != 1:
        conflict_type, requirements = "VALUE_MISMATCH", ["CHECK_CORRECTION_DISCLOSURE"]
    else:
        conflict_type, requirements = "UNKNOWN", ["VERIFY_NO_CONFLICT"]

    return {
        "schema_version": 1,
        "conflict_id": _identity(security_code, claims),
        "security_code": security_code,
        "claims": sorted(claims, key=lambda row: (row["claim_ref"], row["evidence_ref"])),
        "conflict_type": conflict_type,
        "status": "OPEN",
        "resolution_requirement": requirements,
        "resolution_ref": None,
        "trade_recommendation": None,
    }
