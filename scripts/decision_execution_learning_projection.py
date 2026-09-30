"""Deterministic, read-only learning projection for decision/execution/outcome axes.

This module deliberately preserves the three axes independently.  It does not
infer decision quality from P/L, reconstruct owner intent from fills, promote
patterns, or emit investment recommendations/order instructions.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


PROJECTION_VERSION = "EXECUTION_FIDELITY_LEARNING_PROJECTION_V1"

FIDELITY_VALUES = frozenset(
    {
        "MATCH",
        "PARTIAL_MATCH",
        "MISMATCH",
        "NOT_EXECUTED",
        "NOT_JUDGABLE",
        "UNKNOWN",
    }
)
DECISION_QUALITY_VALUES = frozenset(
    {
        "SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "NOT_SUPPORTED",
        "NOT_JUDGABLE",
        "UNKNOWN",
    }
)
OUTCOME_VALUES = frozenset(
    {
        "POSITIVE",
        "NEGATIVE",
        "NEUTRAL",
        "NOT_JUDGABLE",
        "UNKNOWN",
    }
)


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping")
    return value


def _validated_enum(axis: Mapping[str, Any], field: str, allowed: frozenset[str]) -> str:
    value = axis.get("status")
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"unsupported or missing {field} status: {value!r}")
    return value


def _canonical_refs(axis: Mapping[str, Any], field: str) -> list[str]:
    refs = axis.get("canonical_refs", [])
    if not isinstance(refs, (list, tuple)):
        raise ValueError(f"{field}.canonical_refs must be a list or tuple")
    if any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        raise ValueError(f"{field}.canonical_refs must contain non-empty strings")
    return list(refs)


def _project_axis(axis: Mapping[str, Any], field: str, allowed: frozenset[str]) -> dict[str, Any]:
    status = _validated_enum(axis, field, allowed)
    projected: dict[str, Any] = {
        "status": status,
        "canonical_refs": _canonical_refs(axis, field),
    }
    # Preserve explicit, already-authoritative details without deriving new facts.
    if "details" in axis:
        projected["details"] = deepcopy(axis["details"])
    return projected


def project_execution_fidelity_learning(record: Mapping[str, Any]) -> dict[str, Any]:
    """Project explicit learning axes without cross-axis inference.

    Required input keys are ``decision_quality``, ``execution_fidelity`` and
    ``outcome``.  Each is projected only from its own explicit status and
    canonical refs.  In particular, outcome/P&L never changes decision quality,
    and execution/fill evidence never creates owner intent.
    """

    source = _require_mapping(record, "record")
    decision = _require_mapping(source.get("decision_quality"), "decision_quality")
    fidelity = _require_mapping(source.get("execution_fidelity"), "execution_fidelity")
    outcome = _require_mapping(source.get("outcome"), "outcome")

    return {
        "projection_version": PROJECTION_VERSION,
        "decision_quality": _project_axis(
            decision, "decision_quality", DECISION_QUALITY_VALUES
        ),
        "execution_fidelity": _project_axis(
            fidelity, "execution_fidelity", FIDELITY_VALUES
        ),
        "outcome": _project_axis(outcome, "outcome", OUTCOME_VALUES),
    }
