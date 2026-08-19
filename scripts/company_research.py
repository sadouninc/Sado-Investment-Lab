from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class CompanyResearchError(ValueError):
    """Raised when canonical Company Research violates the v1 contract."""


RESEARCH_STATUSES = {"IN_PROGRESS", "CURRENT", "NEEDS_REVIEW"}
CONFIDENCE = {"LOW", "MEDIUM", "HIGH"}
DATA_COMPLETENESS = {"COMPLETE", "PARTIAL", "UNKNOWN"}


GOVERNMENT_MATURITY_LEVELS = {"L0", "L1", "L2", "L3", "L4", "L5", "UNKNOWN"}
GOVERNMENT_CONFIDENCE = {"CONFIRMED", "PARTIAL", "UNKNOWN"}
GOVERNMENT_ATTRIBUTION = {"CONFIRMED", "NOT_CONFIRMED", "NOT_APPLICABLE"}


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


def _validate_government_evidence_maturity(raw: Mapping[str, Any]) -> None:
    """Validate government_evidence_maturity field if present.
    
    Critical validation rules:
    - L4 requires revenue_attribution = CONFIRMED (mass production ≠ L4)
    - L5 requires profit_cf_attribution = CONFIRMED
    - CONFIRMED/PARTIAL confidence requires as_of and sources
    - UNKNOWN, NOT_CONFIRMED, NOT_APPLICABLE are valid and not collapsed
    """
    gov_maturity = raw.get("government_evidence_maturity")
    if not gov_maturity:
        return  # Field is optional
    
    if not isinstance(gov_maturity, Mapping):
        raise CompanyResearchError("government_evidence_maturity must be an object")
    
    # Validate level enum
    level = str(gov_maturity.get("level", "")).upper()
    if not level or level not in GOVERNMENT_MATURITY_LEVELS:
        raise CompanyResearchError(
            f"government_evidence_maturity.level must be one of {GOVERNMENT_MATURITY_LEVELS}"
        )
    
    # Validate confidence enum
    confidence = str(gov_maturity.get("confidence", "")).upper()
    if not confidence or confidence not in GOVERNMENT_CONFIDENCE:
        raise CompanyResearchError(
            f"government_evidence_maturity.confidence must be one of {GOVERNMENT_CONFIDENCE}"
        )
    
    # Validate attribution enums
    revenue_attr = str(gov_maturity.get("revenue_attribution", "")).upper()
    if not revenue_attr or revenue_attr not in GOVERNMENT_ATTRIBUTION:
        raise CompanyResearchError(
            f"government_evidence_maturity.revenue_attribution must be one of {GOVERNMENT_ATTRIBUTION}"
        )
    
    profit_cf_attr = str(gov_maturity.get("profit_cf_attribution", "")).upper()
    if not profit_cf_attr or profit_cf_attr not in GOVERNMENT_ATTRIBUTION:
        raise CompanyResearchError(
            f"government_evidence_maturity.profit_cf_attribution must be one of {GOVERNMENT_ATTRIBUTION}"
        )
    
    # L4 requires CONFIRMED revenue attribution (mass production started ≠ L4)
    if level == "L4" and revenue_attr != "CONFIRMED":
        raise CompanyResearchError(
            "L4 maturity requires revenue_attribution=CONFIRMED (mass production started ≠ L4)"
        )
    
    # L5 requires CONFIRMED profit/CF attribution
    if level == "L5" and profit_cf_attr != "CONFIRMED":
        raise CompanyResearchError("L5 maturity requires profit_cf_attribution=CONFIRMED")
    
    # CONFIRMED or PARTIAL confidence requires as_of and sources
    if confidence in ("CONFIRMED", "PARTIAL"):
        as_of = gov_maturity.get("as_of")
        sources = gov_maturity.get("sources")
        if not as_of or not isinstance(as_of, str) or not as_of.strip():
            raise CompanyResearchError(
                "government_evidence_maturity with CONFIRMED/PARTIAL confidence requires as_of"
            )
        if not isinstance(sources, list) or not sources:
            raise CompanyResearchError(
                "government_evidence_maturity with CONFIRMED/PARTIAL confidence requires non-empty sources"
            )


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
        _validate_government_evidence_maturity(raw)
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
