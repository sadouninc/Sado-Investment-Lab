from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class CompanyResearchError(ValueError):
    """Raised when canonical Company Research violates the v1 contract."""


RESEARCH_STATUSES = {"IN_PROGRESS", "CURRENT", "NEEDS_REVIEW"}
CONFIDENCE = {"LOW", "MEDIUM", "HIGH"}
DATA_COMPLETENESS = {"COMPLETE", "PARTIAL", "UNKNOWN"}


def _text(value: Any, field: str, *, required: bool = True) -> str | None:
    if value is None:
        if required:
            raise CompanyResearchError(f"{field} is required")
        return None
    text = str(value).strip()
    if required and not text:
        raise CompanyResearchError(f"{field} is required")
    return text or None


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CompanyResearchError(f"{field} must be an object")
    return value


def _array(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise CompanyResearchError(f"{field} must be an array")
    return value


def _has_source_as_of(value: Any) -> bool:
    if isinstance(value, Mapping):
        return bool(value.get("source_ref")) and bool(value.get("as_of"))
    return False


def quality_gate_failures(raw: Mapping[str, Any]) -> list[str]:
    """Return deterministic CURRENT quality-gate failures without inventing missing facts."""
    failures: list[str] = []
    selection = _mapping(raw.get("selection_context", {}), "selection_context")
    facts = _mapping(raw.get("facts", {}), "facts")
    interpretation = _mapping(raw.get("interpretation", {}), "interpretation")
    scenarios = _mapping(raw.get("scenarios", {}), "scenarios")
    hypothesis = _mapping(raw.get("hypothesis", {}), "hypothesis")

    if not selection.get("selection_reason") or not selection.get("candidate_sources"):
        failures.append("missing selection provenance / Why Now")

    latest_financials = facts.get("latest_financials")
    if not isinstance(latest_financials, Mapping) or not latest_financials:
        failures.append("missing latest financial fact")
    elif not _has_source_as_of(latest_financials):
        failures.append("latest financial fact missing source_ref/as_of")

    earnings_engine = facts.get("earnings_engine")
    if not isinstance(earnings_engine, Mapping) or not earnings_engine:
        failures.append("missing earnings engine")

    growth = interpretation.get("growth_drivers")
    if not isinstance(growth, list) or not growth:
        failures.append("missing growth driver")

    risks = interpretation.get("risks")
    if not isinstance(risks, list) or not risks:
        failures.append("missing risk/disconfirming evidence")

    for name in ("bear", "base", "bull"):
        scenario = scenarios.get(name)
        if not isinstance(scenario, Mapping):
            failures.append(f"missing {name} scenario")
            continue
        unavailable = scenario.get("unavailable_reason")
        if unavailable:
            continue
        if not scenario.get("target_fiscal_year"):
            failures.append(f"{name} scenario missing target_fiscal_year")
        if scenario.get("eps") is None and scenario.get("net_income") is None:
            failures.append(f"{name} scenario missing eps/net_income")
        if not scenario.get("assumptions"):
            failures.append(f"{name} scenario missing assumptions")

    if not hypothesis.get("what_market_may_be_underestimating"):
        failures.append("missing initial hypothesis")
    if not hypothesis.get("must_happen"):
        failures.append("missing must_happen")
    if not hypothesis.get("invalidation_conditions"):
        failures.append("missing invalidation conditions")
    if not hypothesis.get("expected_time_horizon"):
        failures.append("missing expected_time_horizon")

    source_refs = raw.get("source_refs")
    if not isinstance(source_refs, list) or not source_refs:
        failures.append("missing source_refs")

    return failures


@dataclass(frozen=True)
class CompanyResearchRecord:
    security_code: str
    company_name: str
    as_of: str
    status: str
    selection_context: Mapping[str, Any]
    facts: Mapping[str, Any]
    interpretation: Mapping[str, Any]
    scenarios: Mapping[str, Any]
    hypothesis: Mapping[str, Any]
    source_refs: tuple[str, ...]
    data_completeness: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "CompanyResearchRecord":
        status = _text(raw.get("status"), "status") or ""
        if status not in RESEARCH_STATUSES:
            raise CompanyResearchError(f"unsupported status: {status}")
        confidence = str(_mapping(raw.get("hypothesis", {}), "hypothesis").get("current_confidence", "")).upper()
        if confidence not in CONFIDENCE:
            raise CompanyResearchError("hypothesis.current_confidence must be LOW/MEDIUM/HIGH")
        completeness = str(raw.get("data_completeness", "")).upper()
        if completeness not in DATA_COMPLETENESS:
            raise CompanyResearchError("data_completeness must be COMPLETE/PARTIAL/UNKNOWN")
        record = cls(
            security_code=_text(raw.get("security_code"), "security_code") or "",
            company_name=_text(raw.get("company_name"), "company_name") or "",
            as_of=_text(raw.get("as_of"), "as_of") or "",
            status=status,
            selection_context=_mapping(raw.get("selection_context"), "selection_context"),
            facts=_mapping(raw.get("facts"), "facts"),
            interpretation=_mapping(raw.get("interpretation"), "interpretation"),
            scenarios=_mapping(raw.get("scenarios"), "scenarios"),
            hypothesis=_mapping(raw.get("hypothesis"), "hypothesis"),
            source_refs=tuple(sorted({_text(x, "source_ref") or "" for x in _array(raw.get("source_refs"), "source_refs")})),
            data_completeness=completeness,
        )
        if record.status == "CURRENT":
            failures = quality_gate_failures(raw)
            if failures:
                raise CompanyResearchError("CURRENT quality gate failed: " + "; ".join(failures))
        return record


def build_forward_valuation_handoff(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Build #117 input without silently converting operating profit to net income/EPS."""
    record = CompanyResearchRecord.from_mapping(raw)
    if record.status != "CURRENT":
        raise CompanyResearchError("#117 handoff requires CURRENT research")

    output: dict[str, Any] = {
        "security_code": record.security_code,
        "company_name": record.company_name,
        "as_of": record.as_of,
        "scenarios": {},
        "source_refs": list(record.source_refs),
    }
    for name in ("bear", "base", "bull"):
        source = _mapping(record.scenarios.get(name), f"scenarios.{name}")
        if source.get("unavailable_reason"):
            output["scenarios"][name] = {"unavailable_reason": source["unavailable_reason"]}
            continue
        if source.get("eps") is None and source.get("net_income") is None:
            raise CompanyResearchError(f"{name} scenario has no EPS/net income basis")
        item = {
            "target_fiscal_year": source.get("target_fiscal_year"),
            "eps": source.get("eps"),
            "net_income": source.get("net_income"),
            "share_basis": source.get("share_basis"),
            "assumptions": list(source.get("assumptions") or []),
            "source_type": source.get("source_type", "SADO_SCENARIO"),
            "source_refs": list(source.get("source_refs") or record.source_refs),
            "as_of": source.get("as_of", record.as_of),
        }
        output["scenarios"][name] = item
    return output
