from __future__ import annotations

from copy import deepcopy
from typing import Any

from scripts.developing_signal_registry import transition_signal, validate_signal


class DevelopingSignalPromotionError(ValueError):
    pass


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DevelopingSignalPromotionError(f"{field} must be a non-empty string")
    return value.strip()


def _company_identity(signal: dict[str, Any], security_code: str | None, company_name: str | None) -> tuple[str, str | None]:
    code = security_code.strip() if isinstance(security_code, str) and security_code.strip() else None
    name = company_name.strip() if isinstance(company_name, str) and company_name.strip() else None
    related_codes = {
        str(item.get("id")).strip()
        for item in signal.get("related_entities", [])
        if isinstance(item, dict) and str(item.get("type") or "").upper() == "COMPANY" and str(item.get("id") or "").strip()
    }
    if code is None:
        if len(related_codes) != 1:
            raise DevelopingSignalPromotionError("security_code is required when company identity is not unique")
        code = next(iter(related_codes))
    elif related_codes and code not in related_codes:
        raise DevelopingSignalPromotionError("security_code conflicts with signal related company identity")
    return code, name


def _promote(signal: dict[str, Any], *, at: str, destination_ref: str) -> dict[str, Any]:
    current = validate_signal(signal)
    promoted = transition_signal(current, "PROMOTED", at=_text(at, "at"), promotion_ref=_text(destination_ref, "destination_ref"))
    return promoted


def promote_to_candidate(
    signal: dict[str, Any],
    *,
    at: str,
    candidate_ref: str,
    security_code: str | None = None,
    company_name: str | None = None,
) -> dict[str, Any]:
    """Create an explicit #108 handoff without forcing rank or investment action."""
    current = validate_signal(signal)
    code, name = _company_identity(current, security_code, company_name)
    handoff = {
        "target": "CANDIDATE_SELECTOR",
        "candidate_source": "DEVELOPING_SIGNAL",
        "signal_ref": current["signal_id"],
        "security_code": code,
        "company_name": name,
        "selection_reason": current["why_it_may_matter"],
        "source_refs": deepcopy(current.get("source_refs", [])),
        "auto_select": False,
        "score_override": None,
        "trade_action": None,
    }
    return {"signal": _promote(current, at=at, destination_ref=candidate_ref), "handoff": handoff}


def promote_to_company_research(
    signal: dict[str, Any],
    *,
    at: str,
    research_ref: str,
    mode: str,
    security_code: str | None = None,
    company_name: str | None = None,
) -> dict[str, Any]:
    """Create a #113 research start/refresh candidate while preserving the explicit START_RESEARCH gate."""
    current = validate_signal(signal)
    code, name = _company_identity(current, security_code, company_name)
    normalized_mode = _text(mode, "mode").upper()
    if normalized_mode not in {"START", "REFRESH"}:
        raise DevelopingSignalPromotionError("mode must be START or REFRESH")
    handoff = {
        "target": "COMPANY_RESEARCH",
        "signal_ref": current["signal_id"],
        "security_code": code,
        "company_name": name,
        "research_action_candidate": normalized_mode,
        "selection_reason": current["why_it_may_matter"],
        "candidate_sources": ["DEVELOPING_SIGNAL"],
        "source_refs": deepcopy(current.get("source_refs", [])),
        "requires_start_research_gate": True,
        "start_research": False,
        "trade_action": None,
    }
    return {"signal": _promote(current, at=at, destination_ref=research_ref), "handoff": handoff}


def promote_to_hypothesis_evidence(
    signal: dict[str, Any],
    *,
    at: str,
    hypothesis_ref: str,
    evidence_ref: str,
    relation: str,
) -> dict[str, Any]:
    """Create a #130 evidence candidate without changing thesis confidence automatically."""
    current = validate_signal(signal)
    normalized_relation = _text(relation, "relation").upper()
    if normalized_relation not in {"SUPPORTING", "COUNTER", "MUST_HAPPEN", "INVALIDATION"}:
        raise DevelopingSignalPromotionError("unsupported hypothesis evidence relation")
    target_hypothesis = _text(hypothesis_ref, "hypothesis_ref")
    handoff = {
        "target": "HYPOTHESIS_MONITOR",
        "signal_ref": current["signal_id"],
        "hypothesis_ref": target_hypothesis,
        "evidence_ref": _text(evidence_ref, "evidence_ref"),
        "relation": normalized_relation,
        "evidence_status": "CANDIDATE",
        "source_refs": deepcopy(current.get("source_refs", [])),
        "auto_confidence_change": False,
        "trade_action": None,
    }
    return {"signal": _promote(current, at=at, destination_ref=evidence_ref), "handoff": handoff}


def promote_to_theme_research(
    signal: dict[str, Any],
    *,
    at: str,
    theme_ref: str,
) -> dict[str, Any]:
    """Create an explicit Theme Research handoff without copying full source payloads."""
    current = validate_signal(signal)
    handoff = {
        "target": "THEME_RESEARCH",
        "signal_ref": current["signal_id"],
        "theme_ref": _text(theme_ref, "theme_ref"),
        "summary": current["summary"],
        "why_it_may_matter": current["why_it_may_matter"],
        "source_refs": deepcopy(current.get("source_refs", [])),
        "auto_research_complete": False,
        "trade_action": None,
    }
    return {"signal": _promote(current, at=at, destination_ref=theme_ref), "handoff": handoff}
