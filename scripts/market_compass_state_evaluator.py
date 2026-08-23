"""Canonical Market Compass state evaluator v0.1 for #586 B3 / #568."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _extract_number(val: Any) -> float | int | None:
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return val
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _get_fundamental_integrity(security: dict[str, Any]) -> str:
    raw = security.get("fundamental_integrity")
    if isinstance(raw, dict):
        raw = raw.get("status")
    if isinstance(raw, str):
        raw_upper = raw.upper()
        if raw_upper in ("PASS", "REVIEW", "FAIL", "UNKNOWN"):
            return raw_upper
    return "UNKNOWN"


def _has_unquantified_deterioration(security: dict[str, Any]) -> bool:
    if security.get("unquantified_deterioration") is True:
        return True
    if security.get("company_specific_deterioration_unquantified") is True:
        return True
    return False


def _extract_scores(security: dict[str, Any]) -> tuple[dict[str, float | int | None], float | int | None]:
    scores_dict = security.get("scores") if isinstance(security.get("scores"), dict) else security

    excess_decline = _extract_number(scores_dict.get("excess_decline"))
    valuation_reset = _extract_number(scores_dict.get("valuation_reset"))
    fundamental_strength = _extract_number(scores_dict.get("fundamental_strength"))
    risk_stabilization = _extract_number(scores_dict.get("risk_stabilization"))

    extracted_scores = {
        "excess_decline": excess_decline,
        "valuation_reset": valuation_reset,
        "fundamental_strength": fundamental_strength,
        "risk_stabilization": risk_stabilization,
    }

    if (
        excess_decline is None
        or valuation_reset is None
        or fundamental_strength is None
        or risk_stabilization is None
    ):
        score_total = None
    else:
        score_total = excess_decline + valuation_reset + fundamental_strength + risk_stabilization

    return extracted_scores, score_total


def _get_verified_stabilization_count(security: dict[str, Any]) -> int:
    explicit_count = security.get("verified_stabilization_count")
    if isinstance(explicit_count, int) and not isinstance(explicit_count, bool):
        return explicit_count

    inputs = security.get("stabilization_inputs")
    if isinstance(inputs, list):
        count = 0
        for item in inputs:
            if item == "VERIFIED":
                count += 1
            elif isinstance(item, dict) and item.get("status") == "VERIFIED":
                count += 1
            elif isinstance(item, dict) and item.get("verification") == "VERIFIED":
                count += 1
        return count

    return 0


def _get_confidence(security: dict[str, Any]) -> str | None:
    conf = security.get("confidence")
    if isinstance(conf, str):
        conf_upper = conf.upper()
        if conf_upper in ("HIGH", "MEDIUM", "LOW"):
            return conf_upper
    return None


def evaluate_security_state(security_input: dict[str, Any]) -> dict[str, Any]:
    """Evaluate canonical v0.1 Market Compass state for a security without payload mutation.

    Separates `evaluation_status` ("EVALUATED" vs "UNKNOWN") from `market_compass_state`.
    Score UNKNOWN => `score_total=None` (never coerced to zero).
    MEMBERSHIP_UNKNOWN never emits BUY_WATCH or REENTRY_READY.
    """
    security = deepcopy(security_input)
    security_code = str(security.get("security_code", ""))
    membership = security.get("membership")

    integrity = _get_fundamental_integrity(security)
    unquantified_det = _has_unquantified_deterioration(security)
    scores, score_total = _extract_scores(security)
    verified_stab_count = _get_verified_stabilization_count(security)
    confidence = _get_confidence(security)

    excess_decline = scores["excess_decline"]
    fundamental_strength = scores["fundamental_strength"]
    risk_stabilization = scores["risk_stabilization"]

    # 1. AVOID predicate check
    if integrity in ("FAIL", "UNKNOWN") or unquantified_det:
        return {
            "schema_version": 1,
            "security_code": security_code,
            "evaluation_status": "EVALUATED",
            "market_compass_state": "AVOID",
            "reason": "FUNDAMENTAL_INTEGRITY_FAIL_OR_UNQUANTIFIED_DETERIORATION",
            "score_total": score_total,
            "scores": scores,
            "fundamental_integrity": integrity,
            "confidence": confidence,
            "membership": membership,
            "verified_stabilization_count": verified_stab_count,
            "investment_authority": "READ_ONLY_EVIDENCE",
            "trade_recommendation": None,
        }

    # If scores are missing/UNKNOWN, score-dependent predicates cannot be provably satisfied
    if score_total is None or excess_decline is None or fundamental_strength is None or risk_stabilization is None:
        return {
            "schema_version": 1,
            "security_code": security_code,
            "evaluation_status": "UNKNOWN",
            "market_compass_state": None,
            "reason": "SCORE_UNKNOWN",
            "score_total": None,
            "scores": scores,
            "fundamental_integrity": integrity,
            "confidence": confidence,
            "membership": membership,
            "verified_stabilization_count": verified_stab_count,
            "investment_authority": "READ_ONLY_EVIDENCE",
            "trade_recommendation": None,
        }

    # 2. REENTRY READY predicate check
    is_reentry_ready_candidate = (
        integrity == "PASS"
        and score_total >= 70
        and excess_decline >= 10
        and fundamental_strength >= 10
        and risk_stabilization >= 15
        and verified_stab_count >= 3
        and confidence is not None
        and confidence != "LOW"
    )

    if is_reentry_ready_candidate:
        if membership == "MEMBERSHIP_UNKNOWN":
            return {
                "schema_version": 1,
                "security_code": security_code,
                "evaluation_status": "UNKNOWN",
                "market_compass_state": None,
                "reason": "MEMBERSHIP_UNKNOWN_FAIL_CLOSED",
                "score_total": score_total,
                "scores": scores,
                "fundamental_integrity": integrity,
                "confidence": confidence,
                "membership": membership,
                "verified_stabilization_count": verified_stab_count,
                "investment_authority": "READ_ONLY_EVIDENCE",
                "trade_recommendation": None,
            }
        return {
            "schema_version": 1,
            "security_code": security_code,
            "evaluation_status": "EVALUATED",
            "market_compass_state": "REENTRY_READY",
            "reason": "REENTRY_READY_PREDICATE_MET",
            "score_total": score_total,
            "scores": scores,
            "fundamental_integrity": integrity,
            "confidence": confidence,
            "membership": membership,
            "verified_stabilization_count": verified_stab_count,
            "investment_authority": "READ_ONLY_EVIDENCE",
            "trade_recommendation": None,
        }

    # 3. BUY WATCH predicate check
    is_buy_watch_candidate = (
        integrity == "PASS"
        and score_total >= 50
        and excess_decline >= 10
        and fundamental_strength >= 10
        and risk_stabilization >= 5
    )

    if is_buy_watch_candidate:
        if membership == "MEMBERSHIP_UNKNOWN":
            return {
                "schema_version": 1,
                "security_code": security_code,
                "evaluation_status": "UNKNOWN",
                "market_compass_state": None,
                "reason": "MEMBERSHIP_UNKNOWN_FAIL_CLOSED",
                "score_total": score_total,
                "scores": scores,
                "fundamental_integrity": integrity,
                "confidence": confidence,
                "membership": membership,
                "verified_stabilization_count": verified_stab_count,
                "investment_authority": "READ_ONLY_EVIDENCE",
                "trade_recommendation": None,
            }
        return {
            "schema_version": 1,
            "security_code": security_code,
            "evaluation_status": "EVALUATED",
            "market_compass_state": "BUY_WATCH",
            "reason": "BUY_WATCH_PREDICATE_MET",
            "score_total": score_total,
            "scores": scores,
            "fundamental_integrity": integrity,
            "confidence": confidence,
            "membership": membership,
            "verified_stabilization_count": verified_stab_count,
            "investment_authority": "READ_ONLY_EVIDENCE",
            "trade_recommendation": None,
        }

    # 4. WATCH predicate check
    is_watch_candidate = (
        integrity in ("PASS", "REVIEW")
        and (score_total < 50 or risk_stabilization < 10)
    )

    if is_watch_candidate:
        return {
            "schema_version": 1,
            "security_code": security_code,
            "evaluation_status": "EVALUATED",
            "market_compass_state": "WATCH",
            "reason": "WATCH_PREDICATE_MET",
            "score_total": score_total,
            "scores": scores,
            "fundamental_integrity": integrity,
            "confidence": confidence,
            "membership": membership,
            "verified_stabilization_count": verified_stab_count,
            "investment_authority": "READ_ONLY_EVIDENCE",
            "trade_recommendation": None,
        }

    # Fall-through: no predicate satisfied
    return {
        "schema_version": 1,
        "security_code": security_code,
        "evaluation_status": "UNKNOWN",
        "market_compass_state": None,
        "reason": "UNSATISFIED_PREDICATE",
        "score_total": score_total,
        "scores": scores,
        "fundamental_integrity": integrity,
        "confidence": confidence,
        "membership": membership,
        "verified_stabilization_count": verified_stab_count,
        "investment_authority": "READ_ONLY_EVIDENCE",
        "trade_recommendation": None,
    }


def evaluate_market_compass_universe_states(universe_projection: dict[str, Any]) -> dict[str, Any]:
    """Evaluate states for all securities in a projected universe payload without payload mutation."""
    projection = deepcopy(universe_projection)

    def _eval_list(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        evaluated_list = []
        for item in items:
            sec_eval = evaluate_security_state(item)
            merged = deepcopy(item)
            merged["evaluation_status"] = sec_eval["evaluation_status"]
            merged["market_compass_state"] = sec_eval["market_compass_state"]
            merged["evaluation_reason"] = sec_eval["reason"]
            merged["score_total"] = sec_eval["score_total"]
            merged["scores"] = sec_eval["scores"]
            evaluated_list.append(merged)
        return evaluated_list

    projection["current_holdings"] = _eval_list(projection.get("current_holdings", []))
    projection["reentry_watch"] = _eval_list(projection.get("reentry_watch", []))
    projection["membership_unknown"] = _eval_list(projection.get("membership_unknown", []))

    return projection
