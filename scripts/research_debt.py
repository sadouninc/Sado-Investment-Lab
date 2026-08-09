#!/usr/bin/env python3
"""Research Debt contract and #271 uncertainty projection for Issue #280 PR1."""
from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any

from reasoning_coverage import SECTION_ORDER, project_reasoning_coverage

ORIGIN_TYPES = {
    "OWNER_ASSUMPTION",
    "UNKNOWN",
    "PARTIAL",
    "STALE",
    "NOT_YET_DEFINED",
    "CONFLICTING",
    "UNAVAILABLE",
}
STATUSES = {
    "OPEN",
    "WAITING_FOR_EVIDENCE",
    "EVIDENCE_AVAILABLE",
    "REVIEW_DUE",
    "RESOLVED",
    "RETIRED",
}
MATERIALITY = {"HIGH", "MEDIUM", "LOW"}
EVIDENCE_TYPES = {"EARNINGS", "KPI", "IR", "POLICY", "PRICE_REFRESH", "OWNER_REVIEW", "OTHER"}

QUESTION_BY_SECTION = {
    "why_candidate": "候補として重要な理由を追加Evidenceで確認する",
    "business_driver": "事業ドライバーの未確認部分を追加Evidenceで確認する",
    "base_scenario": "Baseシナリオの未確認前提を追加Evidenceで検証する",
    "bear_bull_range": "Bear/Bullレンジの未確認前提を追加Evidenceで検証する",
    "valuation": "Valuationを最新の前提・価格で再確認する",
    "hypothesis": "投資仮説の未定義・矛盾部分を確認する",
    "invalidation": "仮説を変える条件を明示する",
    "market_expectation": "市場期待を取得可能なEvidenceで確認する",
    "next_evidence": "次に確認すべきEvidenceを明示する",
}

STATUS_TO_ORIGIN = {
    "OWNER_ASSUMPTION": "OWNER_ASSUMPTION",
    "UNKNOWN": "UNKNOWN",
    "PARTIAL": "PARTIAL",
    "STALE": "STALE",
    "NOT_YET_DEFINED": "NOT_YET_DEFINED",
    "CONFLICTING": "CONFLICTING",
    "UNAVAILABLE": "UNAVAILABLE",
}


class ResearchDebtError(ValueError):
    pass


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResearchDebtError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field)


def _stable_id(security_code: str, section: str, origin_type: str, origin_ref: str, question: str) -> str:
    raw = "|".join((security_code, section, origin_type, origin_ref, question))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"RD-{security_code}-{digest}"


def _validate_expected_evidence(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ResearchDebtError("expected_evidence must be an array")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ResearchDebtError(f"expected_evidence[{index}] must be an object")
        kind = _text(item.get("type"), f"expected_evidence[{index}].type")
        if kind not in EVIDENCE_TYPES:
            raise ResearchDebtError(f"unsupported evidence type: {kind}")
        result.append(
            {
                "type": kind,
                "description": _text(item.get("description"), f"expected_evidence[{index}].description"),
                "not_before": _optional_text(item.get("not_before"), f"expected_evidence[{index}].not_before"),
                "expected_by": _optional_text(item.get("expected_by"), f"expected_evidence[{index}].expected_by"),
            }
        )
    return sorted(result, key=lambda row: (row["type"], row["description"], row["not_before"] or "", row["expected_by"] or ""))


def validate_debt(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ResearchDebtError("debt record must be an object")
    source = deepcopy(record)
    security_code = _text(source.get("security_code"), "security_code")
    section = _text(source.get("section"), "section")
    if section not in SECTION_ORDER:
        raise ResearchDebtError(f"unsupported section: {section}")
    origin_type = _text(source.get("origin_type"), "origin_type")
    if origin_type not in ORIGIN_TYPES:
        raise ResearchDebtError(f"unsupported origin_type: {origin_type}")
    origin_ref = _text(source.get("origin_ref"), "origin_ref")
    question = _text(source.get("question"), "question")
    created_at = _text(source.get("created_at"), "created_at")
    status = _text(source.get("status", "OPEN"), "status")
    if status not in STATUSES:
        raise ResearchDebtError(f"unsupported status: {status}")
    materiality = source.get("materiality")
    if materiality is not None:
        materiality = _text(materiality, "materiality")
        if materiality not in MATERIALITY:
            raise ResearchDebtError(f"unsupported materiality: {materiality}")
    expected = _validate_expected_evidence(source.get("expected_evidence"))
    resolved_at = _optional_text(source.get("resolved_at"), "resolved_at")
    resolution_ref = _optional_text(source.get("resolution_ref"), "resolution_ref")
    resolution = _optional_text(source.get("resolution"), "resolution")
    if status == "RESOLVED" and not (resolved_at and resolution_ref and resolution):
        raise ResearchDebtError("RESOLVED requires resolved_at, resolution_ref and resolution")
    if status != "RESOLVED" and any((resolved_at, resolution_ref, resolution)):
        raise ResearchDebtError("resolution fields are only valid for RESOLVED debt")
    expected_id = _stable_id(security_code, section, origin_type, origin_ref, question)
    if source.get("debt_id") not in (None, expected_id):
        raise ResearchDebtError("debt_id does not match deterministic identity")
    return {
        "schema_version": 1,
        "debt_id": expected_id,
        "security_code": security_code,
        "section": section,
        "question": question,
        "origin_type": origin_type,
        "origin_ref": origin_ref,
        "created_at": created_at,
        "materiality": materiality,
        "expected_evidence": expected,
        "status": status,
        "resolved_at": resolved_at,
        "resolution_ref": resolution_ref,
        "resolution": resolution,
        "trade_recommendation": None,
    }


def project_debt_candidates(coverage_record: dict[str, Any]) -> list[dict[str, Any]]:
    """Map explicit #271 uncertainty states to deterministic OPEN debt candidates.

    PR1 does not infer materiality, expected evidence dates, evidence availability, or trade action.
    Those remain explicit follow-up inputs / later-slice responsibilities.
    """
    coverage = project_reasoning_coverage(coverage_record)
    security_code = coverage["security_code"]
    created_at = coverage["as_of"]
    candidates: list[dict[str, Any]] = []
    canonical_refs = coverage["canonical_refs"]

    for section in SECTION_ORDER:
        data = coverage["sections"][section]
        status = data["status"]
        origin_type = STATUS_TO_ORIGIN.get(status)
        if origin_type is None:
            continue
        section_refs = sorted(set(data.get("refs", []) + data.get("assumption_refs", [])))
        origin_ref = section_refs[0] if section_refs else (canonical_refs[0] if canonical_refs else f"reasoning-coverage:{security_code}:{section}")
        uncertainties = data.get("uncertainties", [])
        questions = [item["text"] for item in uncertainties] or [QUESTION_BY_SECTION[section]]
        for question in questions:
            candidates.append(
                validate_debt(
                    {
                        "security_code": security_code,
                        "section": section,
                        "question": question,
                        "origin_type": origin_type,
                        "origin_ref": origin_ref,
                        "created_at": created_at,
                        "materiality": None,
                        "expected_evidence": [],
                        "status": "OPEN",
                    }
                )
            )

    return sorted(candidates, key=lambda row: (SECTION_ORDER.index(row["section"]), row["origin_type"], row["question"], row["debt_id"]))
