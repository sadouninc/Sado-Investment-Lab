"""Pure deterministic Outcome Attribution projector for Issue #300 PR1.

This module deliberately does not fetch data, infer missing history, score decisions,
or generate investment recommendations.  It only projects explicitly supplied
canonical references and observations into the six-axis v1 read model.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


AXIS_ORDER = (
    "thesis",
    "timing",
    "allocation",
    "execution",
    "market_context",
    "data_quality",
)

_ALLOWED_STATUS = {
    "thesis": {"SUPPORTED", "MIXED", "INVALIDATED", "NOT_JUDGABLE"},
    "timing": {"OBSERVED", "PARTIAL", "NOT_JUDGABLE"},
    "allocation": {"OBSERVED", "PARTIAL", "NOT_JUDGABLE"},
    "execution": {"MATCH", "PARTIAL_MATCH", "MISMATCH", "NOT_JUDGABLE"},
    "market_context": {"AVAILABLE", "PARTIAL", "UNAVAILABLE"},
    "data_quality": {"KNOWN", "PARTIAL", "CONFLICTING"},
}

_MISSING_STATUS = {
    "thesis": "NOT_JUDGABLE",
    "timing": "NOT_JUDGABLE",
    "allocation": "NOT_JUDGABLE",
    "execution": "NOT_JUDGABLE",
    "market_context": "UNAVAILABLE",
    "data_quality": "PARTIAL",
}

_AXIS_FIELDS = {
    "thesis": ("refs",),
    "timing": ("metrics", "refs"),
    "allocation": ("opportunity_set_ref", "refs"),
    "execution": ("fidelity_ref", "refs"),
    "market_context": ("benchmark_refs", "refs"),
    "data_quality": ("coverage_ref", "refs"),
}


def _canonical_ref(value: Any) -> str | None:
    """Accept only explicit non-empty string references; never synthesize one."""
    if isinstance(value, str) and value.strip():
        return value
    return None


def _canonical_refs(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [ref for item in value if (ref := _canonical_ref(item)) is not None]


def _project_axis(name: str, raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, Mapping) else {}
    status = source.get("status", _MISSING_STATUS[name])
    if status not in _ALLOWED_STATUS[name]:
        status = _MISSING_STATUS[name]

    projected: dict[str, Any] = {"status": status}
    for field in _AXIS_FIELDS[name]:
        value = source.get(field)
        if field in {"refs", "benchmark_refs"}:
            projected[field] = _canonical_refs(value)
        elif field == "metrics":
            projected[field] = deepcopy(dict(value)) if isinstance(value, Mapping) else {}
        else:
            projected[field] = _canonical_ref(value)
    return projected


def project_outcome_attribution(source: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deterministic, non-mutating six-axis Outcome Attribution read model.

    Missing history remains explicit.  In particular, missing opportunity-set and
    execution-fidelity references are not reconstructed, and missing market context
    is UNAVAILABLE rather than a synthetic neutral/zero observation.
    """
    if not isinstance(source, Mapping):
        raise TypeError("source must be a mapping")

    axes = source.get("axes")
    axes_source = axes if isinstance(axes, Mapping) else {}

    return {
        "episode_ref": _canonical_ref(source.get("episode_ref")),
        "decision_refs": _canonical_refs(source.get("decision_refs")),
        "evaluation_as_of": _canonical_ref(source.get("evaluation_as_of")),
        "axes": {name: _project_axis(name, axes_source.get(name)) for name in AXIS_ORDER},
        "observations": deepcopy(source.get("observations", []))
        if isinstance(source.get("observations", []), list)
        else [],
        "owner_reflection": deepcopy(source.get("owner_reflection")),
    }
