from __future__ import annotations

import copy
from typing import Any, Mapping

from scripts.company_research import build_forward_valuation_handoff
from scripts.forward_per_simulator import simulate


class ForwardPerAdapterError(ValueError):
    pass


def _target_fiscal_year(handoff: Mapping[str, Any]) -> str | None:
    years = {
        str(item.get("target_fiscal_year"))
        for item in (handoff.get("scenarios") or {}).values()
        if isinstance(item, Mapping) and item.get("target_fiscal_year")
    }
    if not years:
        return None
    if len(years) != 1:
        raise ForwardPerAdapterError("scenario target_fiscal_year mismatch")
    return next(iter(years))


def _share_basis(handoff: Mapping[str, Any]) -> dict[str, Any]:
    candidates = []
    for scenario in (handoff.get("scenarios") or {}).values():
        if not isinstance(scenario, Mapping):
            continue
        basis = scenario.get("share_basis")
        if isinstance(basis, Mapping) and basis:
            candidates.append(dict(basis))
    if not candidates:
        return {"diluted_shares": None, "assumption": "UNAVAILABLE"}
    canonical = candidates[0]
    for other in candidates[1:]:
        if other != canonical:
            raise ForwardPerAdapterError("scenario share_basis mismatch")
    return canonical


def research_to_simulator_input(
    research: Mapping[str, Any],
    *,
    price: Mapping[str, Any],
) -> dict[str, Any]:
    """Convert CURRENT Company Research into #117 simulator input without inventing data."""
    handoff = build_forward_valuation_handoff(research)
    if price.get("value") is None:
        raise ForwardPerAdapterError("price.value is required")
    if not price.get("as_of"):
        raise ForwardPerAdapterError("price.as_of is required")

    scenarios: dict[str, Any] = {}
    for name, source in (handoff.get("scenarios") or {}).items():
        if source.get("unavailable_reason"):
            scenarios[name] = {
                "eps": None,
                "net_income": None,
                "assumptions": [f"UNAVAILABLE: {source['unavailable_reason']}"],
                "confidence": None,
                "provenance": {"source_refs": list(handoff.get("source_refs") or [])},
            }
            continue
        scenarios[name] = {
            "eps": source.get("eps"),
            "net_income": source.get("net_income"),
            "assumptions": copy.deepcopy(source.get("assumptions") or []),
            "confidence": source.get("confidence"),
            "provenance": {
                "source_type": source.get("source_type"),
                "source_refs": copy.deepcopy(source.get("source_refs") or []),
                "as_of": source.get("as_of"),
            },
        }

    return {
        "security_code": handoff.get("security_code"),
        "company_name": handoff.get("company_name"),
        "research_as_of": handoff.get("as_of"),
        "target_fiscal_year": _target_fiscal_year(handoff),
        "price": copy.deepcopy(dict(price)),
        "share_basis": _share_basis(handoff),
        "scenarios": scenarios,
        "provenance": {
            "research_source_refs": list(handoff.get("source_refs") or []),
            "selection_context": copy.deepcopy(research.get("selection_context") or {}),
        },
    }


def simulate_research(
    research: Mapping[str, Any],
    *,
    price: Mapping[str, Any],
    custom_price: float | None = None,
    target_pers: list[float] | None = None,
) -> dict[str, Any]:
    simulator_input = research_to_simulator_input(research, price=price)
    result = simulate(simulator_input, price=custom_price, target_pers=target_pers)
    result["provenance"] = copy.deepcopy(simulator_input["provenance"])
    return result
