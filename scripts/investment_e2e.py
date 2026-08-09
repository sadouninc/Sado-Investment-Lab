from __future__ import annotations

import copy
from typing import Any, Mapping

from scripts.company_research import CompanyResearchRecord, quality_gate_failures
from scripts.company_research_queue import ResearchQueueRecord, ResearchQueueRegistry, complete_research, start_research
from scripts.forward_per_research_adapter import ForwardPerAdapterError, research_to_simulator_input
from scripts.forward_per_simulator import simulate


class InvestmentE2EError(ValueError):
    """Raised when the production-shaped E2E handoff cannot be proven safely."""


def build_simulator_input(
    research_raw: Mapping[str, Any],
    valuation_input: Mapping[str, Any],
) -> dict[str, Any]:
    """Adapt Company Research to #117 through the canonical generic adapter.

    Unit and share-basis normalization must be declared explicitly by the valuation
    handoff metadata. The E2E path does not maintain a second conversion implementation.
    """
    price = valuation_input.get("reference_price")
    if not isinstance(price, Mapping) or price.get("value_jpy") is None or not price.get("as_of") or not price.get("source"):
        raise InvestmentE2EError("reference price value/as_of/source are required")
    if valuation_input.get("security_code") and valuation_input.get("security_code") != research_raw.get("security_code"):
        raise InvestmentE2EError("research/valuation security_code mismatch")

    normalization = {
        "scenario_net_income_unit": valuation_input.get("scenario_net_income_unit"),
        "scenario_net_income_unit_source": valuation_input.get("scenario_net_income_unit_source"),
        "share_basis_field": valuation_input.get("share_basis_field"),
        "share_basis_role": valuation_input.get("share_basis_role"),
    }
    try:
        return research_to_simulator_input(
            research_raw,
            price={
                "value": float(price["value_jpy"]),
                "as_of": str(price["as_of"]),
                "source": str(price["source"]),
            },
            normalization=normalization,
        )
    except ForwardPerAdapterError as exc:
        raise InvestmentE2EError(str(exc)) from exc


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
