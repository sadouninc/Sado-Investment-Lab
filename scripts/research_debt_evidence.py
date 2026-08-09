#!/usr/bin/env python3
"""Evidence availability resolver for Issue #280 PR2.

This module is intentionally read-only.  It maps explicitly related artifact
updates to Research Debt lifecycle suggestions without mutating the debt,
Hypothesis, Decision Journal, or any upstream canonical artifact.
"""
from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import date, datetime
from typing import Any

from research_debt import EVIDENCE_TYPES, ResearchDebtError, validate_debt

ARTIFACT_SCOPE = {"COMPLETE", "INCOMPLETE"}
TIMESTAMP_FIELDS = ("published_at", "observed_at", "as_of")


class ResearchDebtEvidenceError(ValueError):
    pass


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResearchDebtEvidenceError(f"{field} must be a non-empty string")
    return value.strip()


def _temporal(value: Any, field: str) -> tuple[str, date | datetime]:
    text = _text(value, field)
    try:
        if len(text) == 10:
            return "DATE", date.fromisoformat(text)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ResearchDebtEvidenceError(f"{field} must be ISO-8601 date or datetime") from exc
    if parsed.tzinfo is None:
        raise ResearchDebtEvidenceError(f"{field} datetime must include timezone")
    return "DATETIME", parsed


def _date_part(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value


def _strictly_after(candidate: tuple[str, date | datetime], baseline: tuple[str, date | datetime]) -> bool:
    c_kind, c_value = candidate
    b_kind, b_value = baseline
    if c_kind == b_kind == "DATETIME":
        return c_value > b_value
    if c_kind == b_kind == "DATE":
        return c_value > b_value
    # Mixed precision cannot prove intraday order on the same calendar day.
    return _date_part(c_value) > _date_part(b_value)


def _at_or_after(candidate: tuple[str, date | datetime], boundary: tuple[str, date | datetime]) -> bool:
    c_kind, c_value = candidate
    b_kind, b_value = boundary
    if c_kind == b_kind == "DATETIME":
        return c_value >= b_value
    if c_kind == b_kind == "DATE":
        return c_value >= b_value
    c_date = _date_part(c_value)
    b_date = _date_part(b_value)
    if c_date != b_date:
        return c_date > b_date
    # A date-level boundary means the whole day is eligible.  A datetime
    # boundary requires intraday precision, which a date-only artifact lacks.
    return b_kind == "DATE"


def expected_evidence_key(item: dict[str, Any]) -> str:
    if not isinstance(item, dict):
        raise ResearchDebtEvidenceError("expected evidence item must be an object")
    kind = _text(item.get("type"), "expected_evidence.type")
    description = _text(item.get("description"), "expected_evidence.description")
    if kind not in EVIDENCE_TYPES:
        raise ResearchDebtEvidenceError(f"unsupported evidence type: {kind}")
    digest = hashlib.sha256(f"{kind}|{description}".encode("utf-8")).hexdigest()[:16]
    return f"evidence:{kind.lower()}:{digest}"


def _validate_artifact(item: Any, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ResearchDebtEvidenceError(f"artifacts[{index}] must be an object")
    source = deepcopy(item)
    kind = _text(source.get("type"), f"artifacts[{index}].type")
    if kind not in EVIDENCE_TYPES:
        raise ResearchDebtEvidenceError(f"unsupported evidence type: {kind}")
    source_ref = _text(source.get("source_ref"), f"artifacts[{index}].source_ref")
    key = _text(source.get("evidence_key"), f"artifacts[{index}].evidence_key")
    supplied_times = [(field, source.get(field)) for field in TIMESTAMP_FIELDS if source.get(field) is not None]
    if len(supplied_times) != 1:
        raise ResearchDebtEvidenceError(
            f"artifacts[{index}] must provide exactly one of published_at/observed_at/as_of"
        )
    timestamp_field, timestamp_text = supplied_times[0]
    temporal = _temporal(timestamp_text, f"artifacts[{index}].{timestamp_field}")
    return {
        "type": kind,
        "source_ref": source_ref,
        "evidence_key": key,
        "timestamp_field": timestamp_field,
        "artifact_time": _text(timestamp_text, f"artifacts[{index}].{timestamp_field}"),
        "_temporal": temporal,
    }


def resolve_evidence_availability(
    debt_record: dict[str, Any],
    artifacts: list[dict[str, Any]],
    *,
    as_of: str,
    artifact_scope: str = "COMPLETE",
    review_due: bool = False,
) -> dict[str, Any]:
    """Return a deterministic lifecycle suggestion for one Research Debt.

    Artifact-to-debt relation must be explicit via ``evidence_key``.  A merely
    similar artifact type is never treated as satisfying the debt.  ``review_due``
    is an explicit caller signal; this resolver does not invent review deadlines.
    """
    try:
        debt = validate_debt(debt_record)
    except ResearchDebtError as exc:
        raise ResearchDebtEvidenceError(str(exc)) from exc
    if not isinstance(artifacts, list):
        raise ResearchDebtEvidenceError("artifacts must be an array")
    scope = _text(artifact_scope, "artifact_scope")
    if scope not in ARTIFACT_SCOPE:
        raise ResearchDebtEvidenceError(f"unsupported artifact_scope: {scope}")
    if not isinstance(review_due, bool):
        raise ResearchDebtEvidenceError("review_due must be boolean")

    as_of_temporal = _temporal(as_of, "as_of")
    created = _temporal(debt["created_at"], "created_at")
    validated_artifacts = [_validate_artifact(item, index) for index, item in enumerate(artifacts)]

    expected_rows: list[dict[str, Any]] = []
    matching: dict[str, dict[str, Any]] = {}
    any_expected_by_passed = False

    for expected in debt["expected_evidence"]:
        key = expected_evidence_key(expected)
        not_before = _temporal(expected["not_before"], "expected_evidence.not_before") if expected["not_before"] else None
        expected_by = _temporal(expected["expected_by"], "expected_evidence.expected_by") if expected["expected_by"] else None
        if expected_by is not None and _strictly_after(as_of_temporal, expected_by):
            any_expected_by_passed = True

        candidates: list[dict[str, Any]] = []
        for artifact in validated_artifacts:
            if artifact["evidence_key"] != key or artifact["type"] != expected["type"]:
                continue
            if not _strictly_after(artifact["_temporal"], created):
                continue
            if not_before is not None and not _at_or_after(artifact["_temporal"], not_before):
                continue
            candidates.append(artifact)

        candidates.sort(key=lambda row: (row["artifact_time"], row["source_ref"]))
        if candidates:
            chosen = candidates[-1]
            matching[chosen["source_ref"]] = {
                "type": chosen["type"],
                "source_ref": chosen["source_ref"],
                "evidence_key": chosen["evidence_key"],
                "timestamp_field": chosen["timestamp_field"],
                "artifact_time": chosen["artifact_time"],
            }
        expected_rows.append(
            {
                "type": expected["type"],
                "description": expected["description"],
                "evidence_key": key,
                "available": bool(candidates),
            }
        )

    matches = sorted(matching.values(), key=lambda row: (row["artifact_time"], row["source_ref"]))
    expected_count = len(debt["expected_evidence"])
    available = bool(matches)

    current = debt["status"]
    availability_status = "AVAILABLE" if available else ("NOT_AVAILABLE" if scope == "COMPLETE" else "UNKNOWN")

    if current in {"RESOLVED", "RETIRED"}:
        suggested = current
    elif current == "REVIEW_DUE":
        # Do not silently demote an explicitly due review when a later inventory
        # happens to be incomplete or omits the prior evidence artifact.
        suggested = "REVIEW_DUE"
    elif available:
        if review_due:
            if debt["materiality"] not in {"HIGH", "MEDIUM"}:
                raise ResearchDebtEvidenceError("review_due requires explicit HIGH or MEDIUM materiality")
            suggested = "REVIEW_DUE"
        else:
            suggested = "EVIDENCE_AVAILABLE"
    elif scope == "INCOMPLETE":
        # Missing data is not evidence of absence; preserve the current state.
        suggested = current
    elif expected_count:
        # Passing expected_by alone is diagnostic only.  It never mutates Thesis.
        suggested = current if current == "EVIDENCE_AVAILABLE" else "WAITING_FOR_EVIDENCE"
    else:
        suggested = current if current != "WAITING_FOR_EVIDENCE" else "OPEN"

    return {
        "debt_id": debt["debt_id"],
        "security_code": debt["security_code"],
        "current_status": current,
        "suggested_status": suggested,
        "as_of": _text(as_of, "as_of"),
        "artifact_scope": scope,
        "availability_status": availability_status,
        "expected_evidence": expected_rows,
        "matching_evidence": matches,
        "expected_by_passed_without_evidence": bool(any_expected_by_passed and not available),
        "hypothesis_mutation": None,
        "trade_recommendation": None,
    }
