from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from scripts.candidate_selector import build_selector, load_config
from scripts.candidate_selector_signal_sources import build_all_candidate_sources


def derive_research_gap(candidates: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive research_gap from repository research freshness without guessing identities.

    CURRENT research lowers the gap, STALE research raises it, and a resolved
    security_code with no research record is treated as an uncovered research gap.
    Unresolved candidates remain null rather than being guessed by name.
    """
    rows = [deepcopy(row) for row in candidates]
    research_status_by_code: dict[str, str] = {}

    for row in rows:
        code = str(row.get("security_code") or "").strip()
        sources = set(row.get("candidate_sources") or [])
        if not code or "RESEARCH_INDEX" not in sources:
            continue
        status = str(row.get("research_status") or "NOT_STARTED")
        research_status_by_code[code] = status

    for row in rows:
        signals = row.setdefault("signals", {})
        reasons = row.setdefault("signal_reasons", {})
        reasons.setdefault("research_gap", [])
        code = str(row.get("security_code") or "").strip()
        sources = set(row.get("candidate_sources") or [])

        status = research_status_by_code.get(code) if code else None
        if status == "CURRENT":
            signals["research_gap"] = 10.0
            reasons["research_gap"] = ["fresh Company Research exists within the configured freshness window"]
        elif status == "STALE":
            signals["research_gap"] = 90.0
            reasons["research_gap"] = ["Company Research exists but is stale and should be refreshed"]
        elif code:
            signals["research_gap"] = 100.0
            reasons["research_gap"] = ["no Company Research record found for this security_code"]
        elif "RESEARCH_INDEX" in sources:
            # A research file exists, but identity is unresolved. Preserve the evidence
            # without inventing a code or applying it to another candidate by name.
            status = str(row.get("research_status") or "NOT_STARTED")
            if status == "CURRENT":
                signals["research_gap"] = 10.0
                reasons["research_gap"] = ["fresh Company Research exists; security_code unresolved"]
            elif status == "STALE":
                signals["research_gap"] = 90.0
                reasons["research_gap"] = ["stale Company Research exists; security_code unresolved"]
        else:
            signals.setdefault("research_gap", None)

    return rows


def build_candidate_workflow(
    *,
    current_status: Path,
    research_root: Path,
    owner_picks: Path | None,
    news_theme: Path | None,
    earnings_change: Path | None,
    quant_valuation: Path | None,
    config: Path,
    as_of: date,
) -> dict[str, Any]:
    rows, source_status = build_all_candidate_sources(
        current_status=current_status,
        research_root=research_root,
        owner_picks=owner_picks,
        news_theme=news_theme,
        earnings_change=earnings_change,
        quant_valuation=quant_valuation,
        as_of=as_of,
    )
    enriched = derive_research_gap(rows)
    result = build_selector(enriched, config=load_config(config), as_of=as_of)
    result["source_status"] = source_status
    return result


def build_research_handoff(candidate: dict[str, Any]) -> dict[str, Any]:
    """Create the explicit, human-approved boundary into Company Research workflow."""
    code = str(candidate.get("security_code") or "").strip() or None
    name = str(candidate.get("company_name") or "").strip()
    if not name:
        raise ValueError("company_name is required for research handoff")

    return {
        "schema_version": 1,
        "handoff_type": "COMPANY_RESEARCH_CANDIDATE",
        "security_code": code,
        "company_name": name,
        "selection_reason": str(candidate.get("selection_reason") or "").strip(),
        "candidate_sources": list(candidate.get("candidate_sources") or []),
        "research_status": str(candidate.get("research_status") or "NOT_STARTED"),
        "total_priority": candidate.get("total_priority"),
        "requires_human_approval": True,
        "auto_create_issue": False,
    }
