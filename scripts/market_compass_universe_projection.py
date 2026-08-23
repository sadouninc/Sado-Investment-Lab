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

        def _get_first_present_value(sources: list[dict[str, Any]], keys: list[str]) -> tuple[bool, Any]:
            for d in sources:
                if not d or not isinstance(d, dict):
                    continue
                scores = d.get("scores")
                if isinstance(scores, dict):
                    for k in keys:
                        if k in scores:
                            return True, scores[k]
                for k in keys:
                    if k in d:
                        return True, d[k]
            return False, None

        # Bridge evaluator inputs with explicit field-presence precedence
        fi_found, raw_fi = _get_first_present_value([cand_dict, pos_dict, evidence or {}], ["fundamental_integrity"])
        fundamental_integrity = raw_fi if fi_found else "UNKNOWN"
        if isinstance(fundamental_integrity, dict):
            fundamental_integrity = fundamental_integrity.get("status", "UNKNOWN")

        ed_found, ed_val = _get_first_present_value([cand_dict, pos_dict], ["excess_decline", "excess_decline_score"])
        excess_decline = ed_val if ed_found else None

        vr_found, vr_val = _get_first_present_value([cand_dict, pos_dict], ["valuation_reset", "valuation_reset_score"])
        valuation_reset = vr_val if vr_found else None

        fs_found, fs_val = _get_first_present_value([cand_dict, pos_dict], ["fundamental_strength", "fundamental_strength_score"])
        fundamental_strength = fs_val if fs_found else None

        rs_found, rs_val = _get_first_present_value([cand_dict, pos_dict], ["risk_stabilization", "risk_stabilization_score"])
        risk_stabilization = rs_val if rs_found else None

        conf_found, conf_val = _get_first_present_value([cand_dict, pos_dict], ["confidence"])
        confidence = conf_val if conf_found else None

        unq_found, unq_val = _get_first_present_value(
            [cand_dict, pos_dict],
            ["unquantified_deterioration", "company_specific_deterioration_unquantified"],
        )
        unquantified_det = unq_val if unq_found else None

        vsc_found, vsc_val = _get_first_present_value([cand_dict, pos_dict], ["verified_stabilization_count"])
        verified_stab_count = vsc_val if vsc_found else None

        si_found, si_val = _get_first_present_value([cand_dict, pos_dict], ["stabilization_inputs"])
        stabilization_inputs = si_val if si_found else None

        fe_found, fe_val = _get_first_present_value([cand_dict, pos_dict], ["fundamental_evidence"])
        fundamental_evidence = fe_val if fe_found else None

        sr_found, sr_val = _get_first_present_value([cand_dict, pos_dict], ["source_refs", "source_references"])
        source_refs = sr_val if sr_found else None

        notes_found, notes_val = _get_first_present_value([cand_dict, pos_dict], ["notes"])
        notes = notes_val if notes_found else None

        name_found, name_val = _get_first_present_value([pos_dict, cand_dict], ["security_name", "name"])
        security_name = name_val if name_found else None

        row = {
            "security_code": security_code,
            "security_name": security_name,
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
            "fundamental_evidence": deepcopy(fundamental_evidence),
            "source_refs": deepcopy(source_refs),
            "notes": notes,
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
