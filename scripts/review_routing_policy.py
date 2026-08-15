from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


TECHNICAL = "TECHNICAL"
DESIGN = "DESIGN"
RESEARCH = "RESEARCH"
PRODUCT = "PRODUCT"
SECURITY_FLOW = "SECURITY_FLOW"
RELEVANT_SPECIALIST = "RELEVANT_SPECIALIST"


@dataclass(frozen=True)
class ReviewRoute:
    category: str
    blocking_gates: tuple[str, ...]
    non_blocking_gates: tuple[str, ...]
    primary_sla_minutes: int = 60
    specialist_sla_minutes: int = 120


ROUTES = {
    "BACKEND": ReviewRoute("BACKEND", (TECHNICAL,), (DESIGN, RESEARCH, PRODUCT)),
    "PROCESS_FLOW": ReviewRoute("PROCESS_FLOW", (TECHNICAL,), (DESIGN, RESEARCH, PRODUCT)),
    "UI_VISUAL": ReviewRoute("UI_VISUAL", (TECHNICAL, DESIGN), (RESEARCH, PRODUCT)),
    "MARKET_RESEARCH_TRUTH": ReviewRoute(
        "MARKET_RESEARCH_TRUTH", (TECHNICAL, RESEARCH), (DESIGN, PRODUCT)
    ),
    "PRODUCT_SEMANTICS": ReviewRoute(
        "PRODUCT_SEMANTICS", (TECHNICAL, PRODUCT), (DESIGN, RESEARCH)
    ),
    "SECURITY_WORKFLOW": ReviewRoute(
        "SECURITY_WORKFLOW", (TECHNICAL, SECURITY_FLOW), (DESIGN, RESEARCH, PRODUCT)
    ),
    "DOCS_ONLY": ReviewRoute("DOCS_ONLY", (RELEVANT_SPECIALIST,), (TECHNICAL, DESIGN, RESEARCH, PRODUCT)),
}


SECURITY_PREFIXES = (".github/workflows/", ".github/actions/")
UI_PREFIXES = ("docs/", "site/", "web/", "frontend/", "assets/")
PROCESS_HINTS = ("flow", "queue", "telemetry", "router", "routing", "process", "productivity")
RESEARCH_HINTS = ("research", "market", "price", "jquants", "policy", "evidence")
PRODUCT_HINTS = ("valuation", "portfolio", "framework", "product_contract", "decision_contract")


def _normalized_paths(paths: Iterable[str]) -> tuple[str, ...]:
    return tuple(str(path).strip() for path in paths if str(path).strip())


def classify_review_surface(raw: Mapping[str, Any]) -> str:
    """Classify the changed semantic surface. UNKNOWN fails closed."""
    explicit = str(raw.get("category", "")).strip().upper()
    if explicit:
        return explicit if explicit in ROUTES else "UNKNOWN"

    paths = _normalized_paths(raw.get("changed_paths", ()))
    if not paths:
        return "UNKNOWN"

    lowered = tuple(path.lower() for path in paths)
    if any(path.startswith(SECURITY_PREFIXES) for path in paths) or bool(
        raw.get("security_sensitive", False)
    ):
        return "SECURITY_WORKFLOW"

    semantic = str(raw.get("semantic_surface", "")).lower()
    joined = " ".join(lowered) + " " + semantic
    if any(hint in joined for hint in PRODUCT_HINTS):
        return "PRODUCT_SEMANTICS"
    if any(hint in joined for hint in RESEARCH_HINTS):
        return "MARKET_RESEARCH_TRUTH"
    if bool(raw.get("ui_visual_change", False)):
        return "UI_VISUAL"
    if any(hint in joined for hint in PROCESS_HINTS):
        return "PROCESS_FLOW"

    docs_only = all(path.endswith((".md", ".txt", ".rst")) for path in lowered)
    if docs_only:
        return "DOCS_ONLY"
    if any(path.startswith(UI_PREFIXES) for path in paths):
        return "UI_VISUAL"
    return "BACKEND"


def route_reviews(raw: Mapping[str, Any]) -> dict[str, Any]:
    category = classify_review_surface(raw)
    if category == "UNKNOWN":
        return {
            "status": "BLOCK",
            "reason": "UNKNOWN_REVIEW_SURFACE",
            "category": category,
            "blocking_gates": (),
            "non_blocking_gates": (),
        }

    route = ROUTES[category]
    gates = list(route.blocking_gates)
    # Product semantics that also alter market/research truth require the Research gate.
    if category == "PRODUCT_SEMANTICS" and bool(raw.get("market_truth_changed", False)):
        gates.append(RESEARCH)

    # Default invariant is <=2. An explicit cross-authority Product+Market change is the
    # narrow documented exception and is surfaced instead of silently dropping a gate.
    max_expected = 3 if category == "PRODUCT_SEMANTICS" and raw.get("market_truth_changed") else 2
    if len(gates) > max_expected:
        return {
            "status": "BLOCK",
            "reason": "REVIEW_FANOUT_EXCESS",
            "category": category,
            "blocking_gates": tuple(gates),
            "non_blocking_gates": route.non_blocking_gates,
        }

    return {
        "status": "ROUTED",
        "reason": "RISK_SCOPE_MATCH",
        "category": category,
        "blocking_gates": tuple(gates),
        "non_blocking_gates": route.non_blocking_gates,
        "blocking_gate_count": len(gates),
        "primary_sla_minutes": route.primary_sla_minutes,
        "specialist_sla_minutes": route.specialist_sla_minutes,
    }


def carry_forward_gate(
    *,
    gate: str,
    previous_pass: bool,
    changed_surfaces: Iterable[str],
    gate_surfaces: Mapping[str, Iterable[str]],
) -> dict[str, Any]:
    """Decide whether a previous PASS can carry forward to a new head."""
    if not previous_pass:
        return {"carry_forward": False, "reason": "NO_PREVIOUS_PASS"}
    changed = {str(item).upper() for item in changed_surfaces}
    if not changed:
        return {"carry_forward": False, "reason": "UNKNOWN_CHANGE_SURFACE"}
    owned = {str(item).upper() for item in gate_surfaces.get(gate, ())}
    if not owned:
        return {"carry_forward": False, "reason": "UNKNOWN_GATE_SURFACE"}
    if changed & owned:
        return {"carry_forward": False, "reason": "GATE_SURFACE_CHANGED"}
    return {"carry_forward": True, "reason": "UNAFFECTED_GATE"}


def review_wait_action(
    *,
    gate_required: bool,
    wait_age_minutes: int,
    is_primary: bool,
) -> dict[str, Any]:
    """Return SLA action without silently removing a required gate."""
    if not gate_required:
        return {"status": "NON_BLOCKING", "action": "REMOVE_FROM_BLOCKING_SET"}
    threshold = 60 if is_primary else 120
    if wait_age_minutes >= threshold:
        return {"status": "SLA_EXCEEDED", "action": "REROUTE_QUALIFIED_REVIEWER"}
    return {"status": "WAIT", "action": "NONE"}
