from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Mapping

from scripts.earnings_driver_bridge import DriverModelValidationError, evaluate_driver_model


class EarningsDriverAdapterError(ValueError):
    """Raised when Company Research cannot be mapped without guessing."""


def _required_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EarningsDriverAdapterError(f"{field} must be a mapping")
    return value


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise EarningsDriverAdapterError(f"{field} is required")
    return text


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EarningsDriverAdapterError(f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise EarningsDriverAdapterError(f"{field} must be finite")
    return number


def _node(
    *,
    node_id: str,
    node_type: str,
    metric: str,
    scenario: str,
    value: float | int | None,
    unit: str,
    fiscal_year: str,
    source_ref: str,
    as_of: str,
    scope: str = "COMPANY",
    scope_id: str | None = None,
    assumption_text: str | None = None,
    formula: Mapping[str, Any] | None = None,
    confidence: str = "HIGH",
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "node_type": node_type,
        "metric": metric,
        "scope": scope,
        "scope_id": scope_id,
        "scenario": scenario,
        "value": value,
        "unit": unit,
        "target_fiscal_year": fiscal_year,
        "formula": deepcopy(formula),
        "source_refs": [source_ref],
        "assumption_text": assumption_text,
        "as_of": as_of,
        "confidence": confidence,
    }


def calculate_eps_preview(*, net_income_million_jpy: Any, shares: Any) -> float:
    """Explicit unit-normalized EPS preview for the human read model.

    This does not promote the scenario terminal value to DERIVED in the canonical
    driver graph. It only demonstrates the arithmetic using an explicit JPY_MN
    -> JPY conversion and an explicit share denominator.
    """

    net_income = _number(net_income_million_jpy, "net_income_million_jpy")
    denominator = _number(shares, "shares")
    if denominator <= 0:
        raise EarningsDriverAdapterError("shares must be positive")
    return (net_income * 1_000_000.0) / denominator


def build_company_research_driver_model(
    research: Mapping[str, Any], mapping: Mapping[str, Any]
) -> dict[str, Any]:
    """Map a CURRENT Company Research artifact into the #214 PR1 driver graph.

    The adapter is deliberately narrow: it consumes only explicit canonical
    fields and mapping labels. It never annualizes Q1, infers order conversion,
    converts operating profit to net income, or turns qualitative drivers into
    invented growth rates.
    """

    source = deepcopy(dict(research))
    map_cfg = deepcopy(dict(mapping))

    if _required_text(source.get("status"), "status").upper() != "CURRENT":
        raise EarningsDriverAdapterError("Company Research must be CURRENT")

    security_code = _required_text(source.get("security_code"), "security_code")
    if security_code != _required_text(map_cfg.get("security_code"), "mapping.security_code"):
        raise EarningsDriverAdapterError("mapping security_code does not match research")

    facts = _required_mapping(source.get("facts"), "facts")
    latest = _required_mapping(facts.get("latest_financials"), "facts.latest_financials")
    engine = _required_mapping(facts.get("earnings_engine"), "facts.earnings_engine")
    guidance = _required_mapping(engine.get("company_guidance_fy2027"), "company_guidance_fy2027")
    segments = _required_mapping(engine.get("segment_q1"), "earnings_engine.segment_q1")
    share_basis = _required_mapping(facts.get("share_basis"), "facts.share_basis")
    scenarios = _required_mapping(source.get("scenarios"), "scenarios")

    target_fiscal_year = _required_text(map_cfg.get("target_fiscal_year"), "mapping.target_fiscal_year")
    source_ref = _required_text(latest.get("source_ref"), "latest_financials.source_ref")
    q1_as_of = _required_text(latest.get("as_of"), "latest_financials.as_of")
    model_as_of = _required_text(source.get("as_of"), "research.as_of")

    nodes: list[dict[str, Any]] = []
    company_fields = {
        "orders": ("orders_million_jpy", "ORDERS"),
        "revenue": ("revenue_million_jpy", "REVENUE"),
        "operating_profit": ("operating_profit_million_jpy", "OPERATING_PROFIT"),
        "net_income": ("net_income_attributable_million_jpy", "NET_INCOME"),
    }
    for suffix, (field, metric) in company_fields.items():
        nodes.append(
            _node(
                node_id=f"q1_company_{suffix}",
                node_type="OBSERVED",
                metric=metric,
                scenario="COMMON",
                value=_number(latest.get(field), f"latest_financials.{field}"),
                unit="JPY_MN",
                fiscal_year=target_fiscal_year,
                source_ref=source_ref,
                as_of=q1_as_of,
            )
        )

    segment_labels = _required_mapping(map_cfg.get("segment_labels_ja"), "mapping.segment_labels_ja")
    revenue_refs: list[str] = []
    op_refs: list[str] = []
    for segment_id in sorted(segments):
        segment = _required_mapping(segments[segment_id], f"segment_q1.{segment_id}")
        if segment_id not in segment_labels:
            raise EarningsDriverAdapterError(f"missing Japanese segment label: {segment_id}")
        for suffix, field, metric in (
            ("orders", "orders_million_jpy", "ORDERS"),
            ("revenue", "revenue_million_jpy", "REVENUE"),
            ("operating_profit", "operating_profit_million_jpy", "OPERATING_PROFIT"),
        ):
            node_id = f"segment_{segment_id}_{suffix}"
            nodes.append(
                _node(
                    node_id=node_id,
                    node_type="OBSERVED",
                    metric=metric,
                    scenario="COMMON",
                    value=_number(segment.get(field), f"segment_q1.{segment_id}.{field}"),
                    unit="JPY_MN",
                    fiscal_year=target_fiscal_year,
                    source_ref=source_ref,
                    as_of=q1_as_of,
                    scope="SEGMENT",
                    scope_id=segment_id,
                )
            )
            if suffix == "revenue":
                revenue_refs.append(node_id)
            elif suffix == "operating_profit":
                op_refs.append(node_id)

    for node_id, metric, refs in (
        ("segment_revenue_sum", "REVENUE", revenue_refs),
        ("segment_operating_profit_sum", "OPERATING_PROFIT", op_refs),
    ):
        nodes.append(
            _node(
                node_id=node_id,
                node_type="DERIVED",
                metric=metric,
                scenario="COMMON",
                value=None,
                unit="JPY_MN",
                fiscal_year=target_fiscal_year,
                source_ref=source_ref,
                as_of=q1_as_of,
                formula={"operation": "SUM", "input_refs": refs},
            )
        )

    for suffix, field, metric in (
        ("revenue", "revenue_million_jpy", "REVENUE"),
        ("operating_profit", "operating_profit_million_jpy", "OPERATING_PROFIT"),
        ("ordinary_profit", "ordinary_profit_million_jpy", "OTHER"),
        ("net_income", "net_income_million_jpy", "NET_INCOME"),
    ):
        nodes.append(
            _node(
                node_id=f"guidance_{suffix}",
                node_type="EXTERNAL",
                metric=metric,
                scenario="COMMON",
                value=_number(guidance.get(field), f"guidance.{field}"),
                unit="JPY_MN",
                fiscal_year=target_fiscal_year,
                source_ref=_required_text(engine.get("source_ref"), "earnings_engine.source_ref"),
                as_of=_required_text(engine.get("as_of"), "earnings_engine.as_of"),
            )
        )

    assumption_labels = _required_mapping(map_cfg.get("assumption_labels_ja"), "mapping.assumption_labels_ja")
    output_refs: dict[str, dict[str, str | None]] = {}
    read_scenarios: dict[str, Any] = {}
    shares = _number(share_basis.get("shares_ex_treasury_pre_split"), "share_basis.shares_ex_treasury_pre_split")

    for scenario_name in ("bear", "base", "bull"):
        scenario = _required_mapping(scenarios.get(scenario_name), f"scenarios.{scenario_name}")
        if _required_text(scenario.get("target_fiscal_year"), f"{scenario_name}.target_fiscal_year") != target_fiscal_year:
            raise EarningsDriverAdapterError(f"fiscal year mismatch in {scenario_name}")
        scenario_upper = scenario_name.upper()
        net_income = _number(scenario.get("net_income"), f"{scenario_name}.net_income")
        assumptions = scenario.get("assumptions")
        if not isinstance(assumptions, list) or not assumptions:
            raise EarningsDriverAdapterError(f"{scenario_name}.assumptions must be non-empty")

        driver_refs: list[str] = []
        labels_ja: list[str] = []
        for index, assumption in enumerate(assumptions, start=1):
            assumption_text = _required_text(assumption, f"{scenario_name}.assumptions[{index - 1}]")
            label = assumption_labels.get(assumption_text)
            if not label:
                raise EarningsDriverAdapterError(f"missing Japanese label for assumption: {assumption_text}")
            labels_ja.append(str(label))
            ref = f"{scenario_name}_driver_{index}"
            driver_refs.append(ref)
            nodes.append(
                _node(
                    node_id=ref,
                    node_type="ASSUMPTION",
                    metric="OTHER",
                    scenario=scenario_upper,
                    value=None,
                    unit="OTHER",
                    fiscal_year=target_fiscal_year,
                    source_ref=_required_text(scenario.get("source_refs", [None])[0], f"{scenario_name}.source_refs[0]"),
                    as_of=_required_text(scenario.get("as_of"), f"{scenario_name}.as_of"),
                    assumption_text=assumption_text,
                    confidence=_required_text(scenario.get("confidence"), f"{scenario_name}.confidence").upper(),
                )
            )

        terminal_ref = f"{scenario_name}_net_income_terminal"
        nodes.append(
            _node(
                node_id=terminal_ref,
                node_type="ASSUMPTION",
                metric="NET_INCOME",
                scenario=scenario_upper,
                value=net_income,
                unit="JPY_MN",
                fiscal_year=target_fiscal_year,
                source_ref=_required_text(scenario.get("source_refs", [None])[0], f"{scenario_name}.source_refs[0]"),
                as_of=_required_text(scenario.get("as_of"), f"{scenario_name}.as_of"),
                assumption_text="Sado scenario terminal value; not fully formula-derived from current driver graph",
                confidence=_required_text(scenario.get("confidence"), f"{scenario_name}.confidence").upper(),
            )
        )
        output_refs[scenario_name] = {"net_income_ref": terminal_ref, "eps_ref": None}
        read_scenarios[scenario_name] = {
            "net_income_million_jpy": net_income,
            "eps_preview_jpy": calculate_eps_preview(net_income_million_jpy=net_income, shares=shares),
            "eps_preview_basis": {
                "net_income_unit": "JPY_MN",
                "share_denominator": shares,
                "share_basis": _required_text(scenario.get("share_basis", {}).get("basis"), f"{scenario_name}.share_basis.basis"),
                "share_as_of": _required_text(scenario.get("share_basis", {}).get("as_of"), f"{scenario_name}.share_basis.as_of"),
                "canonical_status": "READ_MODEL_ONLY",
            },
            "driver_refs": driver_refs,
            "main_drivers_ja": labels_ja,
        }

    model = {
        "security_code": security_code,
        "target_fiscal_year": target_fiscal_year,
        "version": _required_text(map_cfg.get("version"), "mapping.version"),
        "as_of": model_as_of,
        "status": "PARTIAL",
        "nodes": nodes,
        "outputs": output_refs,
    }
    evaluated = evaluate_driver_model(model)
    if evaluated["status"] != "PARTIAL":
        raise EarningsDriverAdapterError("initial Company Research driver model must remain PARTIAL")

    guidance_net_income = _number(guidance.get("net_income_million_jpy"), "guidance.net_income_million_jpy")
    base_net_income = read_scenarios["base"]["net_income_million_jpy"]
    company_name = _required_text(source.get("company_name"), "company_name")
    projection = {
        "headline_ja": (
            f"{company_name} FY2027 Base純利益{base_net_income / 100:.0f}億円は、"
            f"会社予想{guidance_net_income / 100:.0f}億円を基準点として参照しつつ、"
            "事業ドライバーの継続・利益化を見込むSado Researchのシナリオです。"
        ),
        "main_drivers_ja": read_scenarios["base"]["main_drivers_ja"],
        "main_risks_ja": list(map_cfg.get("main_risks_ja") or []),
        "derivation_status_ja": (
            "一部の観測値集計は数式化済みですが、純利益シナリオ全額を事業KPIから"
            "機械的に算出しているわけではありません。"
        ),
    }

    return {
        "model": model,
        "evaluated": evaluated,
        "read_model": {
            "company_name": company_name,
            "security_code": security_code,
            "target_fiscal_year": target_fiscal_year,
            "status": "PARTIAL",
            "scenarios": read_scenarios,
            "projection_ja": projection,
            "safety_notes_ja": [
                "Q1実績を4倍して通期値にはしていません。",
                "営業利益から純利益を推測変換していません。",
                "定性的なAI/DC需要の強さを任意の成長率へ変換していません。",
                "会社予想とSado Baseシナリオを同一視していません。",
            ],
        },
    }
