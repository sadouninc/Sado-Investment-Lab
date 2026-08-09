from __future__ import annotations

import copy
from datetime import datetime
from typing import Any, Iterable, Mapping

from scripts.company_research import build_forward_valuation_handoff
from scripts.expectation_revision import latest_revision_view, validate_snapshot


class ExpectationContextError(ValueError):
    """Raised when Research / Expectation comparison cannot be proven on the same basis."""


def _observed_at(snapshot: Mapping[str, Any]) -> datetime:
    return datetime.fromisoformat(str(snapshot["observed_at"]).replace("Z", "+00:00"))


def _share_basis_key(value: Any) -> tuple[tuple[str, str], ...] | None:
    if value in (None, {}, ""):
        return None
    if not isinstance(value, Mapping):
        return (("value", str(value)),)
    comparable = {
        str(key): str(item)
        for key, item in value.items()
        if key in {"basis", "share_basis", "dilution", "split_adjustment", "shares", "diluted_shares"}
        and item is not None
    }
    return tuple(sorted(comparable.items())) or None


def _sado_value(handoff: Mapping[str, Any], *, scenario_name: str, metric: str) -> tuple[Any, Mapping[str, Any]]:
    scenario = (handoff.get("scenarios") or {}).get(scenario_name)
    if not isinstance(scenario, Mapping):
        raise ExpectationContextError(f"missing Sado scenario: {scenario_name}")
    if scenario.get("unavailable_reason"):
        return None, scenario
    if metric == "EPS":
        return scenario.get("eps"), scenario
    if metric == "NET_INCOME":
        return scenario.get("net_income"), scenario
    raise ExpectationContextError("PR3 supports EPS or NET_INCOME comparison")


def latest_external_expectation(
    history: Iterable[Mapping[str, Any]],
    *,
    security_code: str,
    target_fiscal_period: str,
    metric: str,
    unit: str,
) -> dict[str, Any]:
    """Return the latest validated CONSENSUS snapshot on one explicit comparison basis."""
    rows: list[dict[str, Any]] = []
    for raw in history:
        if str(raw.get("expectation_type")) != "CONSENSUS":
            continue
        snapshot = validate_snapshot(dict(raw))
        if (
            str(snapshot.get("security_code")) == str(security_code)
            and str(snapshot.get("target_fiscal_period")) == str(target_fiscal_period)
            and str(snapshot.get("metric")) == str(metric)
            and str(snapshot.get("unit")) == str(unit)
        ):
            rows.append(snapshot)

    if not rows:
        return {
            "status": "UNAVAILABLE",
            "snapshot": None,
            "direction": "UNKNOWN",
            "observation_count": 0,
            "reason_codes": ["NO_COMPATIBLE_EXTERNAL_EXPECTATION"],
        }

    rows.sort(key=lambda row: (_observed_at(row), str(row["expectation_id"])))
    latest_time = _observed_at(rows[-1])
    latest_rows = [row for row in rows if _observed_at(row) == latest_time]
    signatures = {(row["expectation_id"], row.get("value")) for row in latest_rows}
    if len(signatures) > 1:
        return {
            "status": "NEEDS_REVIEW",
            "snapshot": None,
            "direction": "UNKNOWN",
            "observation_count": len(rows),
            "reason_codes": ["CONFLICTING_LATEST_EXPECTATION"],
        }

    template = latest_rows[0]
    revision = latest_revision_view(rows, template=template)
    latest = revision["latest"]
    coverage_status = str((latest.get("coverage") or {}).get("status") or "")
    reasons: list[str] = []
    if coverage_status == "STALE":
        reasons.append("STALE_EXPECTATION")
    if coverage_status == "UNAVAILABLE":
        reasons.append("EXPECTATION_UNAVAILABLE")
        status = "UNAVAILABLE"
    else:
        status = "OK"

    return {
        "status": status,
        "snapshot": copy.deepcopy(latest),
        "direction": revision["direction"],
        "observation_count": revision["observation_count"],
        "revision_since_previous": copy.deepcopy(revision["revision_since_previous"]),
        "reason_codes": reasons,
    }


def build_research_expectation_context(
    research: Mapping[str, Any],
    expectation_history: Iterable[Mapping[str, Any]],
    *,
    metric: str,
    unit: str,
    sado_value_unit: str,
    scenario_name: str = "base",
) -> dict[str, Any]:
    """Compare Sado Research scenario with External CONSENSUS without mutating either source."""
    handoff = build_forward_valuation_handoff(research)
    value, scenario = _sado_value(handoff, scenario_name=scenario_name, metric=metric)
    years = {
        str(item.get("target_fiscal_year"))
        for item in (handoff.get("scenarios") or {}).values()
        if isinstance(item, Mapping) and item.get("target_fiscal_year")
    }
    if len(years) != 1:
        raise ExpectationContextError("Sado scenarios must resolve to one target fiscal period")
    target_period = next(iter(years))

    if str(sado_value_unit) != str(unit):
        return {
            "status": "NEEDS_REVIEW",
            "security_code": handoff.get("security_code"),
            "target_fiscal_period": target_period,
            "metric": metric,
            "unit": unit,
            "scenario_name": scenario_name,
            "sado_value": value,
            "external_expectation": None,
            "sado_vs_consensus_abs": None,
            "sado_vs_consensus_pct": None,
            "reason_codes": ["UNIT_MISMATCH"],
        }

    external = latest_external_expectation(
        expectation_history,
        security_code=str(handoff.get("security_code")),
        target_fiscal_period=target_period,
        metric=metric,
        unit=unit,
    )
    if external["status"] != "OK" or value is None:
        reasons = list(external.get("reason_codes") or [])
        if value is None:
            reasons.append("SADO_SCENARIO_VALUE_UNAVAILABLE")
        return {
            "status": "UNAVAILABLE" if external["status"] == "UNAVAILABLE" else "NEEDS_REVIEW",
            "security_code": handoff.get("security_code"),
            "target_fiscal_period": target_period,
            "metric": metric,
            "unit": unit,
            "scenario_name": scenario_name,
            "sado_value": value,
            "external_expectation": copy.deepcopy(external),
            "sado_vs_consensus_abs": None,
            "sado_vs_consensus_pct": None,
            "reason_codes": sorted(set(reasons)),
        }

    snapshot = external["snapshot"]
    expectation_value = snapshot.get("value")
    if expectation_value is None:
        raise ExpectationContextError("available expectation must contain value")

    if metric == "EPS":
        research_basis = _share_basis_key(scenario.get("share_basis"))
        external_basis = _share_basis_key((snapshot.get("provenance") or {}).get("share_basis"))
        if research_basis is not None and external_basis is not None and research_basis != external_basis:
            return {
                "status": "NEEDS_REVIEW",
                "security_code": handoff.get("security_code"),
                "target_fiscal_period": target_period,
                "metric": metric,
                "unit": unit,
                "scenario_name": scenario_name,
                "sado_value": value,
                "external_expectation": copy.deepcopy(external),
                "sado_vs_consensus_abs": None,
                "sado_vs_consensus_pct": None,
                "reason_codes": ["SHARE_BASIS_MISMATCH"],
            }

    sado_num = float(value)
    expectation_num = float(expectation_value)
    absolute = sado_num - expectation_num
    pct = None if expectation_num == 0 else (sado_num / expectation_num) - 1.0
    reasons = list(external.get("reason_codes") or [])
    if expectation_num == 0:
        reasons.append("ZERO_EXPECTATION_DENOMINATOR")

    return {
        "status": "NEEDS_REVIEW" if pct is None else "OK",
        "security_code": handoff.get("security_code"),
        "target_fiscal_period": target_period,
        "metric": metric,
        "unit": unit,
        "scenario_name": scenario_name,
        "sado_value": sado_num,
        "sado_source_type": scenario.get("source_type"),
        "sado_source_refs": copy.deepcopy(scenario.get("source_refs") or []),
        "external_expectation": copy.deepcopy(external),
        "sado_vs_consensus_abs": round(absolute, 10),
        "sado_vs_consensus_pct": None if pct is None else round(pct, 10),
        "reason_codes": sorted(set(reasons)),
    }


def attach_expectation_to_forward_per(
    valuation_result: Mapping[str, Any],
    expectation_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach expectation context to #117 output without changing valuation calculations."""
    if str(valuation_result.get("security_code")) != str(expectation_context.get("security_code")):
        raise ExpectationContextError("valuation/expectation security_code mismatch")
    if str(valuation_result.get("target_fiscal_year")) != str(expectation_context.get("target_fiscal_period")):
        raise ExpectationContextError("valuation/expectation target fiscal period mismatch")
    result = copy.deepcopy(dict(valuation_result))
    result["expectation_context"] = copy.deepcopy(dict(expectation_context))
    return result


def build_company_research_expectation_view(
    research: Mapping[str, Any],
    expectation_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Expose Fundamental and External Expectation as separate view axes for #175/#113."""
    if str(research.get("security_code")) != str(expectation_context.get("security_code")):
        raise ExpectationContextError("research/expectation security_code mismatch")
    return {
        "security_code": research.get("security_code"),
        "company_name": research.get("company_name"),
        "fundamental_context": {
            "research_status": research.get("status"),
            "research_as_of": research.get("as_of"),
            "hypothesis_confidence": (research.get("hypothesis") or {}).get("current_confidence"),
        },
        "external_expectation_context": copy.deepcopy(dict(expectation_context)),
    }
