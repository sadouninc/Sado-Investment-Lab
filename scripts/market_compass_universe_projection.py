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
    membership.  If temporal authority cannot be compared, membership remains
    fail-closed UNKNOWN rather than being guessed.
    """
    portfolio_copy = deepcopy(portfolio)
    reentry_copy = deepcopy(reentry_watch)
    evidence_copy = deepcopy(subsector_evidence_by_security)

    snapshot_as_of = _parse_date(portfolio_copy.get("as_of"))
    authority_status = portfolio_copy.get("verification_status", "UNKNOWN")
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
            else:
                membership = "CURRENT_HOLDING"
        elif position is not None:
            membership = "CURRENT_HOLDING" if snapshot_as_of is not None else "MEMBERSHIP_UNKNOWN"
        elif candidate is not None:
            membership = "REENTRY_WATCH" if exit_date is not None else "MEMBERSHIP_UNKNOWN"
        else:  # defensive; union above makes this unreachable
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
            except (ValueError, TypeError, KeyError):
                evidence = _unknown_evidence(security_code, "RESOLVER_FAILURE")

        row = {
            "security_code": security_code,
            "security_name": (position or {}).get("security_name") or (candidate or {}).get("name"),
            "membership": membership,
            "portfolio_authority_status": (
                "STALE_RELATIVE_TO_EXIT"
                if membership == "REENTRY_WATCH" and position is not None and candidate is not None
                else authority_status if position is not None else None
            ),
            "portfolio_snapshot_as_of": portfolio_copy.get("as_of") if position is not None else None,
            "confirmed_exit_date": candidate.get("exit_date") if candidate is not None else None,
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
        "current_holdings": current,
        "reentry_watch": reentry,
        "membership_unknown": unknown,
    }
