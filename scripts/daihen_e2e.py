from __future__ import annotations

from typing import Any, Mapping

from scripts.company_research import CompanyResearchRecord
from scripts.forward_per_simulator import simulate


class DaihenE2EError(ValueError):
    """Raised when the Daihen First E2E cannot safely cross a data boundary."""


def _market_quote(quote: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not quote:
        return None
    value = quote.get("value")
    if value is None or float(value) <= 0:
        raise DaihenE2EError("market quote requires a positive value")
    if not quote.get("as_of") or not quote.get("source"):
        raise DaihenE2EError("market quote requires source and as_of")
    if quote.get("share_basis") != "PRE_SPLIT":
        raise DaihenE2EError("Daihen E2E requires PRE_SPLIT market quote before 2026-10-01 split")
    return {
        "value": float(value),
        "as_of": str(quote["as_of"]),
        "source": str(quote["source"]),
        "share_basis": "PRE_SPLIT",
    }


def _scenario_for_simulator(
    raw: Mapping[str, Any],
    name: str,
    *,
    net_income_unit: str,
) -> dict[str, Any]:
    scenario = raw.get("scenarios", {}).get(name) or {}
    net_income = scenario.get("net_income")
    if net_income is None:
        return {
            "eps": scenario.get("eps"),
            "net_income": None,
            "assumptions": list(scenario.get("assumptions") or []),
            "confidence": scenario.get("confidence"),
            "provenance": {"source_refs": list(scenario.get("source_refs") or [])},
        }
    if net_income_unit != "JPY_MN":
        raise DaihenE2EError("explicit scenario_net_income_unit=JPY_MN is required")
    return {
        "eps": scenario.get("eps"),
        "net_income": float(net_income) * 1_000_000.0,
        "assumptions": list(scenario.get("assumptions") or []),
        "confidence": scenario.get("confidence"),
        "provenance": {
            "source_type": scenario.get("source_type"),
            "source_refs": list(scenario.get("source_refs") or []),
            "net_income_input": net_income,
            "net_income_unit": net_income_unit,
        },
    }


def run_daihen_first_e2e(
    raw: Mapping[str, Any],
    *,
    market_quote: Mapping[str, Any] | None,
    scenario_net_income_unit: str,
    target_pers: list[float] | None = None,
) -> dict[str, Any]:
    """Run the #172 Daihen vertical slice without fabricating market data or units."""
    record = CompanyResearchRecord.from_mapping(raw)
    if record.security_code != "6622":
        raise DaihenE2EError("First E2E canonical identity must be security_code=6622")
    if record.status != "CURRENT":
        raise DaihenE2EError("First E2E requires CURRENT Company Research")
    if scenario_net_income_unit != "JPY_MN":
        raise DaihenE2EError("explicit scenario_net_income_unit=JPY_MN is required")

    gate = record.selection_context.get("research_gate") or {}
    if gate.get("command") != "START_RESEARCH" or gate.get("approved") is not True:
        raise DaihenE2EError("explicit START_RESEARCH gate is required")

    quote = _market_quote(market_quote)
    provenance = {
        "candidate": list(record.selection_context.get("provenance_refs") or []),
        "research_sources": list(record.source_refs),
        "hypothesis_sources": list(record.hypothesis.get("source_refs") or []),
        "scenario_net_income_unit": scenario_net_income_unit,
    }
    if not provenance["candidate"] or not provenance["research_sources"] or not provenance["hypothesis_sources"]:
        raise DaihenE2EError("candidate → research → hypothesis provenance must be complete")

    if quote is None:
        return {
            "security_code": "6622",
            "status": "BLOCKED_MARKET_PRICE_UNAVAILABLE",
            "valuation": None,
            "hypothesis": dict(record.hypothesis),
            "provenance": provenance,
            "missing": ["market_quote.value", "market_quote.as_of", "market_quote.source"],
        }

    share_basis = raw.get("facts", {}).get("share_basis") or {}
    shares = share_basis.get("shares_ex_treasury_pre_split")
    if shares is None or float(shares) <= 0:
        raise DaihenE2EError("explicit pre-split shares ex treasury are required")

    target_years = {
        (raw.get("scenarios", {}).get(name) or {}).get("target_fiscal_year")
        for name in ("bear", "base", "bull")
    }
    if len(target_years) != 1 or None in target_years:
        raise DaihenE2EError("Bear/Base/Bull target fiscal year must match")
    target_fiscal_year = next(iter(target_years))

    simulator_input = {
        "security_code": "6622",
        "company_name": record.company_name,
        "research_as_of": record.as_of,
        "target_fiscal_year": target_fiscal_year,
        "price": quote,
        "share_basis": {
            "diluted_shares": float(shares),
            "basis": "Q1 period-end pre-split shares ex treasury",
            "as_of": share_basis.get("as_of"),
        },
        "scenarios": {
            name: _scenario_for_simulator(raw, name, net_income_unit=scenario_net_income_unit)
            for name in ("bear", "base", "bull")
        },
    }
    valuation = simulate(simulator_input, target_pers=target_pers)
    return {
        "security_code": "6622",
        "status": "COMPLETED",
        "valuation": valuation,
        "hypothesis": dict(record.hypothesis),
        "provenance": {
            **provenance,
            "market_quote": {
                "source": quote["source"],
                "as_of": quote["as_of"],
                "share_basis": quote["share_basis"],
            },
        },
    }
