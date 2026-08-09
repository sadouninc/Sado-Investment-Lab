from __future__ import annotations

import copy
from typing import Any

SCENARIOS = ("bear", "base", "bull")


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


def calculate_scenario(
    scenario: dict[str, Any],
    *,
    price: float,
    diluted_shares: float | None,
    target_pers: list[float],
) -> dict[str, Any]:
    warnings: list[str] = []
    explicit_eps = _number(scenario.get("eps"))
    net_income = _number(scenario.get("net_income"))
    derived_eps = None
    if net_income is not None and diluted_shares is not None and diluted_shares > 0:
        derived_eps = net_income / diluted_shares

    eps = explicit_eps if explicit_eps is not None else derived_eps
    eps_source = "EXPLICIT_EPS" if explicit_eps is not None else ("NET_INCOME_DIV_SHARES" if derived_eps is not None else None)

    if explicit_eps is not None and derived_eps is not None:
        denominator = max(abs(explicit_eps), 1e-12)
        if abs(explicit_eps - derived_eps) / denominator > 0.02:
            warnings.append("EPS_NET_INCOME_SHARE_INCONSISTENCY")

    if eps is None:
        warnings.append("EPS_UNAVAILABLE")
        forward_per: float | str | None = None
        implied = {f"per_{target:g}": None for target in target_pers}
    elif eps <= 0:
        warnings.append("PER_NOT_MEANINGFUL_NON_POSITIVE_EPS")
        forward_per = "N/M"
        implied = {f"per_{target:g}": None for target in target_pers}
    else:
        forward_per = _round(price / eps)
        implied = {f"per_{target:g}": _round(eps * target) for target in target_pers}

    return {
        "eps": _round(eps),
        "eps_source": eps_source,
        "forward_per": forward_per,
        "implied_prices": implied,
        "assumptions": copy.deepcopy(scenario.get("assumptions") or []),
        "confidence": scenario.get("confidence"),
        "provenance": copy.deepcopy(scenario.get("provenance") or {}),
        "warnings": warnings,
    }


def simulate(
    research_input: dict[str, Any],
    *,
    price: float | None = None,
    target_pers: list[float] | None = None,
) -> dict[str, Any]:
    """Calculate Bear/Base/Bull Forward PER without mutating canonical Research input."""
    source = copy.deepcopy(research_input)
    market = source.get("price") or {}
    selected_price = _number(price if price is not None else market.get("value"))
    if selected_price is None or selected_price <= 0:
        raise ValueError("positive price is required")

    share_basis = source.get("share_basis") or {}
    diluted_shares = _number(share_basis.get("diluted_shares"))
    warnings: list[str] = []
    if diluted_shares is None or diluted_shares <= 0:
        diluted_shares = None
        warnings.append("DILUTED_SHARES_UNAVAILABLE")
    if not market.get("as_of"):
        warnings.append("PRICE_AS_OF_MISSING")
    if not source.get("research_as_of"):
        warnings.append("RESEARCH_AS_OF_MISSING")
    if not source.get("target_fiscal_year"):
        warnings.append("TARGET_FISCAL_YEAR_MISSING")

    targets = target_pers or [15.0, 20.0, 25.0, 30.0]
    if any(value <= 0 for value in targets):
        raise ValueError("target PER must be positive")

    scenarios = source.get("scenarios") or {}
    results = {
        name: calculate_scenario(
            scenarios.get(name) or {},
            price=selected_price,
            diluted_shares=diluted_shares,
            target_pers=targets,
        )
        for name in SCENARIOS
    }
    for name, result in results.items():
        warnings.extend(f"{name.upper()}:{warning}" for warning in result["warnings"])

    return {
        "security_code": source.get("security_code"),
        "company_name": source.get("company_name"),
        "research_as_of": source.get("research_as_of"),
        "target_fiscal_year": source.get("target_fiscal_year"),
        "price": {
            "value": _round(selected_price),
            "as_of": market.get("as_of"),
            "source": market.get("source"),
            "mode": "CUSTOM" if price is not None else "CURRENT",
        },
        "share_basis": copy.deepcopy(share_basis),
        "scenario_results": results,
        "warnings": sorted(set(warnings)),
    }


def sensitivity_matrix(eps_values: list[float], per_values: list[float]) -> list[dict[str, Any]]:
    if any(eps <= 0 for eps in eps_values) or any(per <= 0 for per in per_values):
        raise ValueError("EPS and PER sensitivity values must be positive")
    return [
        {
            "eps": eps,
            "implied_prices": {f"per_{per:g}": _round(eps * per) for per in per_values},
        }
        for eps in eps_values
    ]
