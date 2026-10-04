"""Pure Decision Pattern / Insight contract validation for Issue #135 PR1."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Mapping

LIFECYCLE_STATES = frozenset(
    {
        "OBSERVATION",
        "POSSIBLE_PATTERN",
        "REPEATED_PATTERN",
        "ACTIONABLE_INSIGHT",
        "RETIRED",
    }
)
DATA_SUFFICIENCY_STATES = frozenset({"INSUFFICIENT_DATA", "SUFFICIENT_DATA"})
CONFIDENCE_STATES = frozenset({"LOW", "MEDIUM", "HIGH", "UNKNOWN"})

_REQUIRED_FIELDS = frozenset(
    {
        "pattern_id",
        "status",
        "definition",
        "supporting_episode_refs",
        "counterexample_episode_refs",
        "sample_size",
        "data_sufficiency",
    }
)
_ALLOWED_FIELDS = _REQUIRED_FIELDS | frozenset(
    {
        "first_observed_at",
        "last_updated_at",
        "confidence",
        "insight",
        "suggested_guardrail",
        "decision_quality_refs",
        "outcome_refs",
        "execution_fidelity_refs",
        "retrospective_episode_refs",
        "explicit_psychology_context_refs",
        "owner_acknowledged",
    }
)
_REF_LIST_FIELDS = (
    "supporting_episode_refs",
    "counterexample_episode_refs",
    "decision_quality_refs",
    "outcome_refs",
    "execution_fidelity_refs",
    "retrospective_episode_refs",
    "explicit_psychology_context_refs",
)


class PatternContractValidationError(ValueError):
    """Raised when a Pattern Record violates the explicit PR1 contract."""


def _require_ref_list(record: Mapping[str, Any], field: str) -> list[str]:
    value = record.get(field, [])
    if not isinstance(value, list):
        raise PatternContractValidationError(f"{field} must be a list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise PatternContractValidationError(f"{field} must contain non-empty string refs")
    if len(value) != len(set(value)):
        raise PatternContractValidationError(f"{field} must not contain duplicate refs")
    return list(value)


def validate_pattern_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return a deep-copied canonical Pattern Record.

    Validation is fail-closed. This function does not detect patterns, promote
    lifecycle state, infer psychology, infer Decision Quality from Outcome/P&L,
    generate Owner acknowledgement, or emit trade instructions.
    """
    if not isinstance(record, Mapping):
        raise PatternContractValidationError("record must be a mapping")

    keys = set(record)
    missing = _REQUIRED_FIELDS - keys
    unknown = keys - _ALLOWED_FIELDS
    if missing:
        raise PatternContractValidationError(f"missing required fields: {sorted(missing)}")
    if unknown:
        raise PatternContractValidationError(f"unsupported fields: {sorted(unknown)}")

    pattern_id = record["pattern_id"]
    definition = record["definition"]
    if not isinstance(pattern_id, str) or not pattern_id.strip():
        raise PatternContractValidationError("pattern_id must be a non-empty string")
    if not isinstance(definition, str) or not definition.strip():
        raise PatternContractValidationError("definition must be a non-empty string")

    status = record["status"]
    if status not in LIFECYCLE_STATES:
        raise PatternContractValidationError(f"unsupported status: {status!r}")

    sufficiency = record["data_sufficiency"]
    if sufficiency not in DATA_SUFFICIENCY_STATES:
        raise PatternContractValidationError(
            f"unsupported data_sufficiency: {sufficiency!r}"
        )

    sample_size = record["sample_size"]
    if isinstance(sample_size, bool) or not isinstance(sample_size, int) or sample_size < 0:
        raise PatternContractValidationError("sample_size must be a non-negative integer")

    refs = {}
    for field in _REF_LIST_FIELDS:
        if field in record or field in ("supporting_episode_refs", "counterexample_episode_refs"):
            refs[field] = _require_ref_list(record, field)
    support = refs["supporting_episode_refs"]
    counter = refs["counterexample_episode_refs"]
    if set(support) & set(counter):
        raise PatternContractValidationError(
            "supporting_episode_refs and counterexample_episode_refs must be independent"
        )
    if sample_size != len(set(support + counter)):
        raise PatternContractValidationError(
            "sample_size must equal unique supporting + counterexample episode refs"
        )

    retrospective = set(refs.get("retrospective_episode_refs", []))
    observed = set(support + counter)
    if not retrospective <= observed:
        raise PatternContractValidationError(
            "retrospective_episode_refs must refer to observed supporting/counterexample episodes"
        )

    confidence = record.get("confidence", "UNKNOWN")
    if confidence not in CONFIDENCE_STATES:
        raise PatternContractValidationError(f"unsupported confidence: {confidence!r}")

    if "owner_acknowledged" in record and record["owner_acknowledged"] not in (True, False, None):
        raise PatternContractValidationError("owner_acknowledged must be true, false, or null")

    guardrail = record.get("suggested_guardrail")
    if guardrail is not None and (not isinstance(guardrail, str) or not guardrail.strip()):
        raise PatternContractValidationError("suggested_guardrail must be null or non-empty text")

    canonical = deepcopy(dict(record))
    canonical["confidence"] = confidence
    for field, value in refs.items():
        canonical[field] = value
    return canonical


def pattern_identity(record: Mapping[str, Any]) -> str:
    """Return deterministic identity for a valid record without mutating input."""
    canonical = validate_pattern_record(record)
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "decision-pattern:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
