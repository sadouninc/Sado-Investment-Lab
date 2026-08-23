"""Read-only Market Compass universe projection for #586 B2."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any

from scripts.market_compass_security_intraday_evidence import resolve_security_intraday_evidence


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _unknown_evidence(security_code: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "security_code": security_code,
        "status": "UNKNOWN",
        "reason": reason,
        "investment_authority": "READ_ONLY_EVIDENCE",
        "trade_recommendation": None,
        "intraday_evidence": None,
    }


def project_market_compass_universe(
    portfolio: dict[str, Any],
    reentry_watch: dict[str, Any],
    subsector_evidence_by_security: dict[str, dict[str, Any]],
    *,
    evidence_as_of: str,
    expected_taxonomy_version: str,
    mapping: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project current/re-entry membership and B1 evidence without mutation.

    A confirmed exit newer than the portfolio snapshot supersedes stale current
    membership. Current holding membership additionally requires VERIFIED
    portfolio authority. Unknown authority fails closed instead of being guessed.
    """
    portfolio_copy = deepcopy(portfolio)
    reentry_copy = deepcopy(reentry_watch)
    evidence_copy = deepcopy(subsector_evidence_by_security)

    snapshot_as_of = _parse_date(portfolio_copy.get("as_of"))
    authority_status = portfolio_copy.get("verification_status", "UNKNOWN")
    portfolio_membership_verified = authority_status == "VERIFIED"
    positions = {
        str(row.get("security_code")): row
        for row in portfolio_copy.get("positions", [])
        if isinstance(row, dict) and row.get("security_code") is not None
    }
    candidates = {
        str(row.get("security_code")): row
        for row in reentry_copy.get("candidates", [])
        if isinstance(row, dict) and row.get("security_code") is not None
    }

    current: list[dict[str, Any]] = []
    reentry: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []

    for security_code in sorted(set(positions) | set(candidates)):
        position = positions.get(security_code)
        candidate = candidates.get(security_code)
        exit_date = _parse_date(candidate.get("exit_date")) if candidate else None

        if position is not None and candidate is not None:
            if snapshot_as_of is None or exit_date is None:
                membership = "MEMBERSHIP_UNKNOWN"
            elif exit_date > snapshot_as_of:
                membership = "REENTRY_WATCH"
            elif portfolio_membership_verified:
                membership = "CURRENT_HOLDING"
            else:
                membership = "MEMBERSHIP_UNKNOWN"
        elif position is not None:
            membership = (
                "CURRENT_HOLDING"
                if snapshot_as_of is not None and portfolio_membership_verified
                else "MEMBERSHIP_UNKNOWN"
            )
        elif candidate is not None:
            membership = "REENTRY_WATCH" if exit_date is not None else "MEMBERSHIP_UNKNOWN"
        else:
            membership = "MEMBERSHIP_UNKNOWN"

        evidence_payload = evidence_copy.get(security_code)
        if evidence_payload is None:
            evidence = _unknown_evidence(security_code, "MISSING_SUBSECTOR_EVIDENCE")
        else:
            try:
                evidence = resolve_security_intraday_evidence(
                    security_code,
                    evidence_as_of,
                    expected_taxonomy_version,
                    evidence_payload,
                    mapping,
                )
            except (ValueError, TypeError):
                evidence = _unknown_evidence(security_code, "RESOLVER_FAILURE")

        pos_dict = position or {}
        cand_dict = candidate or {}

        # Bridge evaluator inputs without imputing missing values
        fundamental_integrity = (
            cand_dict.get("fundamental_integrity")
            or pos_dict.get("fundamental_integrity")
            or (evidence or {}).get("fundamental_integrity")
            or "UNKNOWN"
        )
        if isinstance(fundamental_integrity, dict):
            fundamental_integrity = fundamental_integrity.get("status", "UNKNOWN")

        def _get_score_val(primary: dict[str, Any], secondary: dict[str, Any], name: str, alt_name: str) -> float | int | None:
            for d in (primary, secondary):
                if not d:
                    continue
                scores = d.get("scores")
                if isinstance(scores, dict) and name in scores and scores[name] is not None:
                    return scores[name]
                if name in d and d[name] is not None:
                    return d[name]
                if alt_name in d and d[alt_name] is not None:
                    return d[alt_name]
            return None

        excess_decline = _get_score_val(cand_dict, pos_dict, "excess_decline", "excess_decline_score")
        valuation_reset = _get_score_val(cand_dict, pos_dict, "valuation_reset", "valuation_reset_score")
        fundamental_strength = _get_score_val(cand_dict, pos_dict, "fundamental_strength", "fundamental_strength_score")
        risk_stabilization = _get_score_val(cand_dict, pos_dict, "risk_stabilization", "risk_stabilization_score")

        confidence = cand_dict.get("confidence") or pos_dict.get("confidence")
        unquantified_det = (
            cand_dict.get("unquantified_deterioration")
            if cand_dict.get("unquantified_deterioration") is not None
            else cand_dict.get("company_specific_deterioration_unquantified")
            if cand_dict.get("company_specific_deterioration_unquantified") is not None
            else pos_dict.get("unquantified_deterioration")
            if pos_dict.get("unquantified_deterioration") is not None
            else pos_dict.get("company_specific_deterioration_unquantified")
        )
        verified_stab_count = (
            cand_dict.get("verified_stabilization_count")
            if cand_dict.get("verified_stabilization_count") is not None
            else pos_dict.get("verified_stabilization_count")
        )
        stabilization_inputs = (
            cand_dict.get("stabilization_inputs")
            if cand_dict.get("stabilization_inputs") is not None
            else pos_dict.get("stabilization_inputs")
        )

        row = {
            "security_code": security_code,
            "security_name": pos_dict.get("security_name") or cand_dict.get("name"),
            "membership": membership,
            "portfolio_authority_status": (
                "STALE_RELATIVE_TO_EXIT"
                if membership == "REENTRY_WATCH" and position is not None and candidate is not None
                else authority_status if position is not None else None
            ),
            "portfolio_snapshot_as_of": portfolio_copy.get("as_of") if position is not None else None,
            "confirmed_exit_date": cand_dict.get("exit_date") if candidate is not None else None,
            "fundamental_integrity": fundamental_integrity,
            "scores": {
                "excess_decline": excess_decline,
                "valuation_reset": valuation_reset,
                "fundamental_strength": fundamental_strength,
                "risk_stabilization": risk_stabilization,
            },
            "confidence": confidence,
            "unquantified_deterioration": unquantified_det,
            "verified_stabilization_count": verified_stab_count,
            "stabilization_inputs": deepcopy(stabilization_inputs),
            "fundamental_evidence": deepcopy(cand_dict.get("fundamental_evidence") or pos_dict.get("fundamental_evidence")),
            "source_refs": deepcopy(cand_dict.get("source_refs") or cand_dict.get("source_references") or pos_dict.get("source_references")),
            "notes": cand_dict.get("notes") or pos_dict.get("notes"),
            "next_price_observation": cand_dict.get("next_price_observation"),
            "next_fundamental_checkpoint": cand_dict.get("next_fundamental_checkpoint"),
            "position": deepcopy(position),
            "reentry_candidate": deepcopy(candidate),
            "intraday_evidence": deepcopy(evidence),
        }
        if membership == "CURRENT_HOLDING":
            current.append(row)
        elif membership == "REENTRY_WATCH":
            reentry.append(row)
        else:
            unknown.append(row)

    return {
        "schema_version": 1,
        "as_of": evidence_as_of,
        "investment_authority": "READ_ONLY_EVIDENCE",
        "trade_recommendation": None,
        "portfolio_base_snapshot": portfolio_copy.get("base_snapshot"),
        "portfolio_authority": portfolio_copy.get("authority"),
        "portfolio_verification_source": portfolio_copy.get("verification_source"),
        "portfolio_verification_as_of": portfolio_copy.get("verification_as_of"),
        "portfolio_verification_scope": portfolio_copy.get("verification_scope"),
        "portfolio_source_references": deepcopy(portfolio_copy.get("source_references")),
        "current_holdings": current,
        "reentry_watch": reentry,
        "membership_unknown": unknown,
    }
