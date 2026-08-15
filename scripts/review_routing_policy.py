from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


KNOWN_SURFACES = frozenset(
    {
        "backend",
        "test",
        "refactor",
        "process_flow",
        "ui_visual",
        "research_truth",
        "product_semantics",
        "workflow_security",
        "docs_nonsemantic",
    }
)

SURFACE_GATES = {
    "backend": ("TECHNICAL",),
    "test": ("TECHNICAL",),
    "refactor": ("TECHNICAL",),
    "process_flow": ("TECHNICAL_FLOW",),
    "ui_visual": ("TECHNICAL", "DESIGN"),
    "research_truth": ("TECHNICAL", "RESEARCH"),
    "product_semantics": ("TECHNICAL", "PRODUCT"),
    "workflow_security": ("TECHNICAL", "SECURITY_FLOW"),
    "docs_nonsemantic": ("RELEVANT_SPECIALIST",),
}

PRIMARY_REVIEW_TARGET_MINUTES = 60
SPECIALIST_REVIEW_TARGET_MINUTES = 120


@dataclass(frozen=True)
class ReviewRoutingInput:
    change_surfaces: tuple[str, ...]
    market_truth_changed: bool = False
    owner_authority_required: bool = False
    explicit_security_sensitive: bool = False


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def classify_blocking_gates(
    raw: Mapping[str, Any] | ReviewRoutingInput,
) -> dict[str, Any]:
    """Return the minimum blocking review set for explicit semantic surfaces.

    Unknown/empty surfaces fail closed instead of guessing review requirements.
    Combined authority surfaces may legitimately require more than two gates; the
    <=2 rule is the default, not permission to drop a required Authority gate.
    """
    if isinstance(raw, ReviewRoutingInput):
        item = raw
    else:
        item = ReviewRoutingInput(
            change_surfaces=tuple(str(v).strip().lower() for v in raw.get("change_surfaces", ())),
            market_truth_changed=bool(raw.get("market_truth_changed", False)),
            owner_authority_required=bool(raw.get("owner_authority_required", False)),
            explicit_security_sensitive=bool(raw.get("explicit_security_sensitive", False)),
        )

    surfaces = _ordered_unique(surface for surface in item.change_surfaces if surface)
    unknown = tuple(surface for surface in surfaces if surface not in KNOWN_SURFACES)
    if not surfaces or unknown:
        return {
            "status": "UNKNOWN",
            "blocking_gates": (),
            "non_blocking_specialists": (),
            "reason": "UNKNOWN_CHANGE_SURFACE" if unknown else "MISSING_CHANGE_SURFACE",
            "unknown_surfaces": unknown,
            "blocking_gate_count": None,
        }

    gates: list[str] = []
    for surface in surfaces:
        gates.extend(SURFACE_GATES[surface])

    if "product_semantics" in surfaces and item.market_truth_changed:
        gates.append("RESEARCH")
    if item.explicit_security_sensitive and "SECURITY_FLOW" not in gates:
        gates.extend(("TECHNICAL", "SECURITY_FLOW"))
    if item.owner_authority_required:
        gates.append("OWNER_AUTHORITY")

    blocking = _ordered_unique(gates)
    all_specialists = {"DESIGN", "RESEARCH", "PRODUCT", "SECURITY_FLOW", "RELEVANT_SPECIALIST"}
    required_specialists = set(blocking) & all_specialists
    non_blocking = tuple(sorted(all_specialists - required_specialists))

    default_limit_exceeded = len(blocking) > 2
    exception_reasons: list[str] = []
    if default_limit_exceeded:
        if item.owner_authority_required:
            exception_reasons.append("OWNER_AUTHORITY_REQUIRED")
        if item.market_truth_changed and "product_semantics" in surfaces:
            exception_reasons.append("PRODUCT_AND_RESEARCH_TRUTH_COMBINED")
        if item.explicit_security_sensitive:
            exception_reasons.append("SECURITY_SENSITIVE")
        if len(set(surfaces)) > 1:
            exception_reasons.append("MULTI_SURFACE_CHANGE")

    return {
        "status": "ROUTED",
        "blocking_gates": blocking,
        "non_blocking_specialists": non_blocking,
        "blocking_gate_count": len(blocking),
        "default_limit_exceeded": default_limit_exceeded,
        "limit_exception_reasons": tuple(dict.fromkeys(exception_reasons)),
        "change_surfaces": surfaces,
    }


def evaluate_gate_carry_forward(
    *,
    gate: str,
    gate_surfaces: Iterable[str] | None,
    changed_surfaces: Iterable[str] | None,
    prior_status: str,
    prior_evidence_known: bool,
) -> dict[str, Any]:
    """Decide whether prior review evidence survives a new head.

    CI is deliberately excluded: latest-head CI is always required outside this
    function. Unknown surface/evidence never carries forward.
    """
    gate_surface_set = {
        str(value).strip().lower() for value in (gate_surfaces or ()) if str(value).strip()
    }
    changed_surface_set = {
        str(value).strip().lower() for value in (changed_surfaces or ()) if str(value).strip()
    }
    normalized_status = str(prior_status).upper()

    if not prior_evidence_known or normalized_status not in {"PASS", "PASS_WITH_NOTES"}:
        return {"decision": "RE_REVIEW", "reason": "PRIOR_EVIDENCE_UNKNOWN_OR_NOT_PASS"}
    if not gate_surface_set or not changed_surface_set:
        return {"decision": "RE_REVIEW", "reason": "CHANGE_IMPACT_UNKNOWN"}
    if not gate_surface_set.issubset(KNOWN_SURFACES) or not changed_surface_set.issubset(KNOWN_SURFACES):
        return {"decision": "RE_REVIEW", "reason": "CHANGE_IMPACT_UNKNOWN"}
    if gate_surface_set.intersection(changed_surface_set):
        return {"decision": "RE_REVIEW", "reason": "GATE_SURFACE_CHANGED"}
    return {"decision": "CARRY_FORWARD", "reason": "UNAFFECTED_SURFACE", "gate": gate}


def evaluate_review_wait_sla(
    *,
    blocking: bool,
    reviewer_kind: str,
    wait_age_minutes: int | None,
    alternate_available: bool,
) -> dict[str, Any]:
    """Detect review wait that must escape or be rerouted."""
    if not blocking:
        return {"status": "NON_BLOCKING", "action": "NONE", "target_minutes": None}
    kind = str(reviewer_kind).upper()
    if kind == "PRIMARY":
        target = PRIMARY_REVIEW_TARGET_MINUTES
    elif kind == "SPECIALIST":
        target = SPECIALIST_REVIEW_TARGET_MINUTES
    else:
        return {"status": "UNKNOWN", "action": "FAIL_CLOSED", "target_minutes": None}
    if wait_age_minutes is None:
        return {"status": "UNKNOWN", "action": "COLLECT_WAIT_AGE", "target_minutes": target}
    if wait_age_minutes < target:
        return {"status": "WITHIN_TARGET", "action": "NONE", "target_minutes": target}
    if alternate_available:
        return {"status": "SLA_EXCEEDED", "action": "REROUTE_REVIEW", "target_minutes": target}
    return {
        "status": "SLA_EXCEEDED",
        "action": "BLOCKED_ESCAPE_KEEP_REQUIRED_GATE",
        "target_minutes": target,
    }
