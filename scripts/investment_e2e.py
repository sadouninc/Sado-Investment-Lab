from __future__ import annotations

import copy
from typing import Any, Mapping

from scripts.company_research import CompanyResearchRecord, build_forward_valuation_handoff, quality_gate_failures
from scripts.company_research_queue import ResearchQueueRecord, ResearchQueueRegistry, complete_research, start_research
from scripts.forward_per_simulator import simulate


class InvestmentE2EError(ValueError):
    """Raised when the production-shaped E2E handoff cannot be proven safely."""


_UNIT_MULTIPLIERS = {
    "jpy": 1.0,
    "million_jpy": 1_000_000.0,
}


def _single_target_fiscal_year(scenarios: Mapping[str, Any]) -> str:
    years = {
        str(item.get("target_fiscal_year"))
        for item in scenarios.values()
        if isinstance(item, Mapping) and item.get("target_fiscal_year")
    }
    if len(years) != 1:
        raise InvestmentE2EError("Bear/Base/Bull target_fiscal_year must resolve to one explicit value")
    return next(iter(years))


def _single_share_basis(scenarios: Mapping[str, Any]) -> tuple[float, str | None, str | None]:
    values: set[float] = set()
    as_of_values: set[str] = set()
    basis_values: set[str] = set()
    for item in scenarios.values():
        if not isinstance(item, Mapping) or item.get("unavailable_reason"):
            continue
        basis = item.get("share_basis")
        if not isinstance(basis, Mapping) or basis.get("shares") is None:
            raise InvestmentE2EError("explicit scenario share_basis.shares is required")
        values.add(float(basis["shares"]))
        if basis.get("as_of"):
            as_of_values.add(str(basis["as_of"]))
        if basis.get("basis"):
            basis_values.add(str(basis["basis"]))
    if len(values) != 1:
        raise InvestmentE2EError("Bear/Base/Bull share basis mismatch")
    return (
        next(iter(values)),
        next(iter(as_of_values)) if len(as_of_values) == 1 else None,
        next(iter(basis_values)) if len(basis_values) == 1 else None,
    )


def build_simulator_input(
    research_raw: Mapping[str, Any],
    valuation_input: Mapping[str, Any],
) -> dict[str, Any]:
    """Adapt Company Research to #117 without implicit unit or share-basis conversion."""
    handoff = build_forward_valuation_handoff(research_raw)
    unit = str(valuation_input.get("scenario_net_income_unit") or "")
    multiplier = _UNIT_MULTIPLIERS.get(unit)
    if multiplier is None:
        raise InvestmentE2EError("explicit supported scenario_net_income_unit is required")
    if not valuation_input.get("scenario_net_income_unit_source"):
        raise InvestmentE2EError("scenario net-income unit provenance is required")

    price = valuation_input.get("reference_price")
    if not isinstance(price, Mapping) or price.get("value_jpy") is None or not price.get("as_of") or not price.get("source"):
        raise InvestmentE2EError("reference price value/as_of/source are required")

    shares, share_as_of, share_basis = _single_share_basis(handoff["scenarios"])
    target_year = _single_target_fiscal_year(handoff["scenarios"])

    scenarios: dict[str, Any] = {}
    for name in ("bear", "base", "bull"):
        source = handoff["scenarios"][name]
        if source.get("unavailable_reason"):
            scenarios[name] = copy.deepcopy(source)
            continue
        net_income = source.get("net_income")
        scenarios[name] = {
            "eps": source.get("eps"),
            "net_income": None if net_income is None else float(net_income) * multiplier,
            "assumptions": copy.deepcopy(source.get("assumptions") or []),
            "confidence": research_raw["scenarios"][name].get("confidence"),
            "provenance": {
                "source_type": source.get("source_type"),
                "source_refs": copy.deepcopy(source.get("source_refs") or []),
                "scenario_as_of": source.get("as_of"),
                "net_income_unit_input": unit,
                "net_income_unit_output": "jpy",
                "unit_source": valuation_input["scenario_net_income_unit_source"],
            },
        }

    return {
        "security_code": handoff["security_code"],
        "company_name": handoff["company_name"],
        "research_as_of": handoff["as_of"],
        "target_fiscal_year": target_year,
        "price": {
            "value": float(price["value_jpy"]),
            "as_of": str(price["as_of"]),
            "source": str(price["source"]),
        },
        "share_basis": {
            "diluted_shares": shares,
            "as_of": share_as_of,
            "assumption": share_basis,
        },
        "scenarios": scenarios,
    }


def build_monitor_ready_hypothesis(
    research_raw: Mapping[str, Any],
    valuation_result: Mapping[str, Any],
) -> dict[str, Any]:
    hypothesis = research_raw.get("hypothesis")
    if not isinstance(hypothesis, Mapping):
        raise InvestmentE2EError("hypothesis contract is required")
    must_happen = list(hypothesis.get("must_happen") or [])
    invalidation = list(hypothesis.get("invalidation_conditions") or [])
    checkpoints = list(hypothesis.get("next_checkpoints") or hypothesis.get("checkpoint") or [])
    if not hypothesis.get("what_market_may_be_underestimating"):
        raise InvestmentE2EError("hypothesis statement is required")
    if not must_happen or not invalidation or not checkpoints:
        raise InvestmentE2EError("MONITOR_READY requires must_happen, invalidation_conditions and next_checkpoints")
    if valuation_result.get("security_code") != research_raw.get("security_code"):
        raise InvestmentE2EError("research/valuation security_code mismatch")

    return {
        "security_code": research_raw["security_code"],
        "hypothesis_statement": hypothesis["what_market_may_be_underestimating"],
        "must_happen": must_happen,
        "key_kpis": list(hypothesis.get("key_kpis") or []),
        "invalidation_conditions": invalidation,
        "next_checkpoints": checkpoints,
        "expected_time_horizon": hypothesis.get("expected_time_horizon"),
        "current_confidence": hypothesis.get("current_confidence"),
        "source_research_ref": f"company-research:{research_raw['security_code']}:{research_raw['as_of']}",
        "source_valuation_ref": f"forward-per:{valuation_result['security_code']}:{valuation_result['target_fiscal_year']}:{valuation_result['price']['as_of']}",
        "system_status": "INTACT",
        "owner_review_state": "NOT_REVIEWED",
        "monitor_status": "MONITOR_READY",
    }


def run_first_e2e(
    research_raw: Mapping[str, Any],
    valuation_input: Mapping[str, Any],
) -> dict[str, Any]:
    """Run Candidate → Research Queue → CURRENT → Forward PER → MONITOR_READY deterministically."""
    raw = copy.deepcopy(research_raw)
    record = CompanyResearchRecord.from_mapping(raw)
    failures = quality_gate_failures(raw)
    if failures:
        raise InvestmentE2EError("research quality gate failed: " + "; ".join(failures))

    selection = raw["selection_context"]
    candidate = {
        "security_code": raw["security_code"],
        "company_name": raw["company_name"],
        "candidate_sources": selection["candidate_sources"],
        "selection_reason": selection["selection_reason"],
        "owner_pick": selection.get("owner_pick", False),
        "candidate_as_of": selection["candidate_as_of"],
        "research_status": selection.get("research_status_before"),
        "research_gap": selection.get("research_gap"),
        "money_flow_context": selection.get("money_flow_context"),
    }
    queue_record = ResearchQueueRecord.from_candidate_handoff(candidate)
    registry = ResearchQueueRegistry()
    first_enqueue = registry.enqueue(queue_record)
    second_enqueue = registry.enqueue(queue_record)
    started = start_research(queue_record, command="START_RESEARCH")
    completed = complete_research(started, quality_gate_passed=(record.status == "CURRENT"))

    simulator_input = build_simulator_input(raw, valuation_input)
    valuation_result = simulate(
        simulator_input,
        target_pers=[float(value) for value in valuation_input.get("target_pers") or [15, 20, 25]],
    )
    warnings = list(valuation_result["warnings"])
    if valuation_input.get("price_warning"):
        warnings.append(str(valuation_input["price_warning"]))
    valuation_result = dict(valuation_result)
    valuation_result["warnings"] = sorted(set(warnings))

    hypothesis = build_monitor_ready_hypothesis(raw, valuation_result)
    return {
        "security_code": raw["security_code"],
        "company_name": raw["company_name"],
        "candidate": candidate,
        "queue": {
            "identity": queue_record.identity,
            "first_enqueue": first_enqueue,
            "second_enqueue": second_enqueue,
            "start_status": started.status,
            "final_status": completed.status,
        },
        "research": {
            "status": record.status,
            "as_of": record.as_of,
            "source_refs": list(record.source_refs),
        },
        "valuation": valuation_result,
        "hypothesis": hypothesis,
        "provenance_chain": [
            "OWNER_DECISION",
            queue_record.identity,
            hypothesis["source_research_ref"],
            hypothesis["source_valuation_ref"],
            "MONITOR_READY",
        ],
    }
