from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping

from scripts.fair_per_evidence import FACTOR_OPTIONALITY, FairPEREvidenceRecord


class DaihenOperationalReadModelError(ValueError):
    """Raised when the #257 integration read-model contract is violated."""


SECTION_NAMES = (
    "review_context",
    "earnings_driver",
    "valuation",
    "expectations",
    "hypothesis",
    "portfolio_preflight",
    "decision_history",
)

SECTION_STATUSES = {"OK", "PARTIAL", "NEEDS_REVIEW", "UNAVAILABLE", "NOT_RUN"}
FRESHNESS_STATUSES = {"CURRENT", "STALE", "UNKNOWN"}
PROHIBITED_KEYS = {
    "recommendation",
    "trade_recommendation",
    "buy_sell_recommendation",
    "auto_decision",
}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DaihenOperationalReadModelError(f"{field} must be a non-empty string")
    return value.strip()


def _iso_datetime(value: Any, field: str) -> str:
    text = _text(value, field)
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise DaihenOperationalReadModelError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DaihenOperationalReadModelError(f"{field} must include timezone")
    return text


def _reject_prohibited(value: Any, *, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if key_text in PROHIBITED_KEYS:
                raise DaihenOperationalReadModelError(
                    f"{path}.{key_text} is prohibited: read model must not generate BUY/SELL decisions"
                )
            _reject_prohibited(child, path=f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_prohibited(child, path=f"{path}[{index}]")


def _source_refs(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise DaihenOperationalReadModelError(f"{field} must be an array")
    refs: list[str] = []
    for item in value:
        ref = _text(item, field)
        if ref not in refs:
            refs.append(ref)
    return sorted(refs)


def _section(name: str, raw: Any) -> dict[str, Any]:
    if raw is None:
        return {"status": "UNAVAILABLE", "freshness": "UNKNOWN", "source_refs": []}
    if not isinstance(raw, Mapping):
        raise DaihenOperationalReadModelError(f"{name} must be an object")

    out = deepcopy(dict(raw))
    status = _text(out.get("status"), f"{name}.status").upper()
    if status not in SECTION_STATUSES:
        raise DaihenOperationalReadModelError(f"unsupported {name}.status: {status}")
    if name != "portfolio_preflight" and status == "NOT_RUN":
        raise DaihenOperationalReadModelError("NOT_RUN is only valid for portfolio_preflight")

    freshness = str(out.get("freshness") or "UNKNOWN").upper()
    if freshness not in FRESHNESS_STATUSES:
        raise DaihenOperationalReadModelError(f"unsupported {name}.freshness: {freshness}")

    refs = _source_refs(out.get("source_refs"), f"{name}.source_refs")
    if out.get("basis_conflict") is True:
        status = "NEEDS_REVIEW"
    elif freshness == "STALE" and status == "OK":
        status = "PARTIAL"
    elif status == "OK" and not refs:
        status = "PARTIAL"

    out["status"] = status
    out["freshness"] = freshness
    out["source_refs"] = refs
    return out


def _unavailable_fair_per_projection() -> dict[str, Any]:
    return {
        "status": "UNAVAILABLE",
        "fair_per_range": {
            "fair_per_low": None,
            "fair_per_high": None,
            "confidence": None,
        },
        "canonical_price": {
            "identity_status": "UNKNOWN",
            "freshness_status": "UNKNOWN",
            "provider_status": "UNKNOWN",
            "not_market_truth": True,
            "price": None,
            "price_as_of": None,
            "usable_for_current_valuation": False,
        },
        "current_valuation_status": "UNKNOWN",
        "implied_expectation": {
            "current_per": None,
            "implied_scenario": None,
            "expectation_gap_to_low": None,
            "expectation_gap_to_high": None,
        },
        "factors": {},
        "strengthening": [],
        "invalidation": [],
        "next_checkpoint": [],
    }


def _project_fair_per_evidence(
    record: FairPEREvidenceRecord | None,
    *,
    security_code: str,
) -> dict[str, Any]:
    """Losslessly project #626 evidence without deriving a new valuation decision."""
    if record is None:
        return _unavailable_fair_per_projection()
    if not isinstance(record, FairPEREvidenceRecord):
        raise DaihenOperationalReadModelError("fair_per_evidence must be FairPEREvidenceRecord or None")
    if record.symbol != security_code:
        raise DaihenOperationalReadModelError(
            f"fair_per_evidence symbol mismatch: expected {security_code}, got {record.symbol}"
        )

    implied = record.implied_expectation
    factors: dict[str, dict[str, Any]] = {}
    for factor_name in sorted(record.factors):
        evidence = record.factors[factor_name]
        factors[factor_name] = {
            "as_of": evidence.as_of,
            "confidence": evidence.confidence,
            "source_ref": evidence.source_ref,
            "stage": evidence.stage if factor_name == FACTOR_OPTIONALITY else None,
        }

    gate = record.canonical_price
    return {
        "status": "AVAILABLE",
        "fair_per_range": {
            "fair_per_low": record.fair_per_range.fair_per_low,
            "fair_per_high": record.fair_per_range.fair_per_high,
            "confidence": record.fair_per_range.confidence,
        },
        "canonical_price": {
            "identity_status": gate.identity_status,
            "freshness_status": gate.freshness_status,
            "provider_status": gate.provider_status,
            "not_market_truth": gate.not_market_truth,
            "price": gate.price,
            "price_as_of": gate.price_as_of,
            "usable_for_current_valuation": gate.usable_for_current_valuation,
        },
        "current_valuation_status": record.current_valuation_status,
        "implied_expectation": {
            "current_per": implied.current_per,
            "implied_scenario": implied.implied_scenario,
            "expectation_gap_to_low": implied.expectation_gap_to_low,
            "expectation_gap_to_high": implied.expectation_gap_to_high,
        },
        "factors": factors,
        "strengthening": list(record.strengthening),
        "invalidation": list(record.invalidation),
        "next_checkpoint": list(record.next_checkpoint),
    }


def _overall_status(sections: Mapping[str, Mapping[str, Any]]) -> str:
    statuses = [str(sections[name]["status"]) for name in SECTION_NAMES]
    if "NEEDS_REVIEW" in statuses:
        return "NEEDS_REVIEW"

    meaningful = [status for status in statuses if status not in {"UNAVAILABLE", "NOT_RUN"}]
    if not meaningful:
        return "UNAVAILABLE"

    if all(status == "OK" for status in statuses) and all(
        sections[name].get("freshness") == "CURRENT" for name in SECTION_NAMES
    ):
        return "OK"
    return "PARTIAL"


def build_daihen_operational_read_model(
    upstream: Mapping[str, Any],
    *,
    generated_at: str,
    fair_per_evidence: FairPEREvidenceRecord | None = None,
) -> dict[str, Any]:
    """Bundle existing canonical outputs for #257 without recomputation or write-back.

    The function is intentionally presentation-neutral. It accepts already-authoritative
    upstream projections and only copies/aggregates explicit status, freshness and refs.
    It never derives EPS, valuation, expectation gaps, portfolio limits or trade actions.
    A supplied #626 ``FairPEREvidenceRecord`` is projected losslessly as a valuation
    sub-record; when absent, only that sub-record remains unavailable.
    """
    if not isinstance(upstream, Mapping):
        raise DaihenOperationalReadModelError("upstream must be an object")
    _reject_prohibited(upstream)

    security_code = _text(upstream.get("security_code"), "security_code")
    if security_code != "6622":
        raise DaihenOperationalReadModelError("#257 PR-A fixture is restricted to Daihen security_code=6622")
    company_name = _text(upstream.get("company_name"), "company_name")
    generated = _iso_datetime(generated_at, "generated_at")

    sections = {name: _section(name, upstream.get(name)) for name in SECTION_NAMES}
    fair_per_projection = _project_fair_per_evidence(
        fair_per_evidence,
        security_code=security_code,
    )
    sections["valuation"]["fair_per_evidence"] = fair_per_projection

    missing_components = [
        name for name in SECTION_NAMES if sections[name]["status"] in {"UNAVAILABLE", "NOT_RUN"}
    ]
    stale_components = [name for name in SECTION_NAMES if sections[name].get("freshness") == "STALE"]
    unknown_components = [name for name in SECTION_NAMES if sections[name].get("freshness") == "UNKNOWN"]

    all_refs: set[str] = set()
    for name in SECTION_NAMES:
        all_refs.update(sections[name].get("source_refs") or [])
    for factor in fair_per_projection["factors"].values():
        source_ref = factor.get("source_ref")
        if source_ref:
            all_refs.add(str(source_ref))

    if stale_components:
        freshness_overall = "STALE"
    elif unknown_components:
        freshness_overall = "PARTIAL"
    else:
        freshness_overall = "CURRENT"

    result: dict[str, Any] = {
        "security_code": security_code,
        "company_name": company_name,
        "generated_at": generated,
        "overall_status": _overall_status(sections),
        **sections,
        "freshness": {
            "overall": freshness_overall,
            "stale_components": sorted(stale_components),
            "unknown_components": sorted(unknown_components),
        },
        "missing_components": sorted(missing_components),
        "source_refs": sorted(all_refs),
    }
    return result
