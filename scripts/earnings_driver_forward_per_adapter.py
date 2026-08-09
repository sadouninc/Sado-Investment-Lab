from __future__ import annotations

import copy
import math
from typing import Any, Mapping

from scripts.forward_per_simulator import simulate


class EarningsDriverForwardPerError(ValueError):
    """Raised when an Earnings Driver result cannot be handed to #117 safely."""


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EarningsDriverForwardPerError(f"{field} must be a mapping")
    return value


def _text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise EarningsDriverForwardPerError(f"{field} is required")
    return text


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EarningsDriverForwardPerError(f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise EarningsDriverForwardPerError(f"{field} must be finite")
    return number


def _node_index(model: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    nodes = model.get("nodes") or []
    if not isinstance(nodes, list):
        raise EarningsDriverForwardPerError("model.nodes must be a list")
    result: dict[str, Mapping[str, Any]] = {}
    for raw in nodes:
        node = _mapping(raw, "model.node")
        node_id = _text(node.get("node_id"), "node.node_id")
        if node_id in result:
            raise EarningsDriverForwardPerError(f"duplicate node_id: {node_id}")
        result[node_id] = node
    return result


def _derivation_kind(node: Mapping[str, Any]) -> str:
    node_type = _text(node.get("node_type"), "node.node_type").upper()
    if node_type == "DERIVED":
        return "DERIVED"
    if node_type == "ASSUMPTION":
        return "SCENARIO_TERMINAL_VALUE"
    raise EarningsDriverForwardPerError(
        f"scenario earnings output must be DERIVED or ASSUMPTION, got {node_type}"
    )


def earnings_driver_to_simulator_input(
    bundle: Mapping[str, Any], *, price: Mapping[str, Any]
) -> dict[str, Any]:
    """Convert #214 output into #117 input while preserving derivation semantics.

    `SCENARIO_TERMINAL_VALUE` means the scenario is an explicit Sado Research value,
    not a value fully derived from the driver graph. The adapter converts JPY_MN to
    JPY only because the node unit is explicit, and uses only the explicit share
    denominator retained by PR2's read model.
    """

    source = copy.deepcopy(dict(bundle))
    model = _mapping(source.get("model"), "model")
    evaluated = _mapping(source.get("evaluated"), "evaluated")
    read_model = _mapping(source.get("read_model"), "read_model")

    if _text(model.get("security_code"), "model.security_code") != _text(
        evaluated.get("security_code"), "evaluated.security_code"
    ):
        raise EarningsDriverForwardPerError("model/evaluated security_code mismatch")
    if _text(model.get("target_fiscal_year"), "model.target_fiscal_year") != _text(
        evaluated.get("target_fiscal_year"), "evaluated.target_fiscal_year"
    ):
        raise EarningsDriverForwardPerError("model/evaluated fiscal year mismatch")

    price_value = _number(price.get("value"), "price.value")
    if price_value <= 0:
        raise EarningsDriverForwardPerError("price.value must be positive")
    price_as_of = _text(price.get("as_of"), "price.as_of")
    price_source = _text(price.get("source"), "price.source")

    nodes = _node_index(model)
    outputs = _mapping(model.get("outputs"), "model.outputs")
    read_scenarios = _mapping(read_model.get("scenarios"), "read_model.scenarios")

    simulator_scenarios: dict[str, Any] = {}
    denominators: list[float] = []
    denominator_meta: list[Mapping[str, Any]] = []

    for scenario in ("bear", "base", "bull"):
        output = _mapping(outputs.get(scenario), f"model.outputs.{scenario}")
        net_income_ref = _text(output.get("net_income_ref"), f"{scenario}.net_income_ref")
        node = nodes.get(net_income_ref)
        if node is None:
            raise EarningsDriverForwardPerError(f"unknown net income output ref: {net_income_ref}")
        if _text(node.get("scenario"), f"{scenario}.node.scenario").upper() != scenario.upper():
            raise EarningsDriverForwardPerError(f"scenario mismatch for {net_income_ref}")
        if _text(node.get("metric"), f"{scenario}.node.metric").upper() != "NET_INCOME":
            raise EarningsDriverForwardPerError(f"output {net_income_ref} is not NET_INCOME")
        if _text(node.get("unit"), f"{scenario}.node.unit").upper() != "JPY_MN":
            raise EarningsDriverForwardPerError("#117 handoff currently requires explicit JPY_MN net income")

        net_income_mn = _number(node.get("value"), f"{scenario}.node.value")
        derivation_kind = _derivation_kind(node)
        scenario_read = _mapping(read_scenarios.get(scenario), f"read_model.scenarios.{scenario}")
        basis = _mapping(scenario_read.get("eps_preview_basis"), f"{scenario}.eps_preview_basis")
        denominator = _number(basis.get("share_denominator"), f"{scenario}.share_denominator")
        if denominator <= 0:
            raise EarningsDriverForwardPerError("share denominator must be positive")
        denominators.append(denominator)
        denominator_meta.append(basis)

        simulator_scenarios[scenario] = {
            "eps": None,
            "net_income": net_income_mn * 1_000_000.0,
            "assumptions": copy.deepcopy(scenario_read.get("main_drivers_ja") or []),
            "confidence": node.get("confidence"),
            "provenance": {
                "driver_model_id": evaluated.get("driver_model_id"),
                "earnings_node_ref": net_income_ref,
                "earnings_derivation_kind": derivation_kind,
                "driver_model_status": evaluated.get("status"),
                "source_refs": copy.deepcopy(node.get("source_refs") or []),
                "as_of": node.get("as_of"),
                "net_income_unit_input": "JPY_MN",
                "net_income_unit_output": "JPY",
            },
        }

    if len(set(denominators)) != 1:
        raise EarningsDriverForwardPerError("scenario share denominator mismatch")
    first_basis = denominator_meta[0]
    for other in denominator_meta[1:]:
        if other.get("share_basis") != first_basis.get("share_basis") or other.get("share_as_of") != first_basis.get("share_as_of"):
            raise EarningsDriverForwardPerError("scenario share basis metadata mismatch")

    return {
        "security_code": model.get("security_code"),
        "company_name": read_model.get("company_name"),
        "research_as_of": model.get("as_of"),
        "target_fiscal_year": model.get("target_fiscal_year"),
        "price": {"value": price_value, "as_of": price_as_of, "source": price_source},
        "share_basis": {
            "diluted_shares": denominators[0],
            "as_of": first_basis.get("share_as_of"),
            "assumption": first_basis.get("share_basis"),
            "denominator_role": "valuation_denominator",
        },
        "scenarios": simulator_scenarios,
        "provenance": {
            "driver_model_id": evaluated.get("driver_model_id"),
            "driver_model_status": evaluated.get("status"),
            "derivation_policy": "DERIVED_OR_SCENARIO_TERMINAL_VALUE_EXPLICIT",
            "projection_ja": copy.deepcopy(read_model.get("projection_ja") or {}),
        },
    }


def simulate_earnings_driver(
    bundle: Mapping[str, Any],
    *,
    price: Mapping[str, Any],
    custom_price: float | None = None,
    target_pers: list[float] | None = None,
) -> dict[str, Any]:
    simulator_input = earnings_driver_to_simulator_input(bundle, price=price)
    result = simulate(simulator_input, price=custom_price, target_pers=target_pers)
    result["provenance"] = copy.deepcopy(simulator_input["provenance"])
    return result
