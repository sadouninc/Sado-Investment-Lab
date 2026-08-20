"""Read-only security-level intraday evidence resolver for #586 B1."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any

from scripts.market_compass_intraday_evidence import (
    adapt_intraday_subsector_to_market_compass,
)
from scripts.security_subsector_mapping import lookup_security_subsector

_FAIL_CLOSED_MAPPING = {
    "UNMAPPED",
    "NO_EFFECTIVE_RECORD",
    "TAXONOMY_MISMATCH",
}


def resolve_security_intraday_evidence(
    security_code: str,
    as_of: str | date,
    expected_taxonomy_version: str,
    subsector_evidence: dict[str, Any],
    mapping: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project canonical subsector evidence to one security without inference.

    Mapping authority remains #756 and intraday evidence authority remains #752.
    Any mapping uncertainty or evidence mismatch stays fail-closed UNKNOWN.
    """
    mapping_result = lookup_security_subsector(
        security_code,
        as_of,
        expected_taxonomy_version,
        mapping,
    )

    base = {
        "schema_version": 1,
        "security_code": security_code,
        "as_of": as_of.isoformat() if isinstance(as_of, date) else as_of,
        "expected_taxonomy_version": expected_taxonomy_version,
        "mapping": deepcopy(mapping_result),
        "investment_authority": "READ_ONLY_EVIDENCE",
        "trade_recommendation": None,
    }

    if mapping_result["status"] in _FAIL_CLOSED_MAPPING:
        return {
            **base,
            "status": "UNKNOWN",
            "reason": mapping_result["status"],
            "intraday_evidence": None,
        }
    if mapping_result["status"] != "MAPPED":
        return {
            **base,
            "status": "UNKNOWN",
            "reason": "UNKNOWN_MAPPING_STATUS",
            "intraday_evidence": None,
        }

    adapted = adapt_intraday_subsector_to_market_compass(subsector_evidence)
    adapted_subsector = adapted["subsector"]
    if (
        adapted_subsector["id"] != mapping_result["subsector_id"]
        or adapted_subsector["taxonomy_version"] != expected_taxonomy_version
    ):
        return {
            **base,
            "status": "UNKNOWN",
            "reason": "SUBSECTOR_EVIDENCE_MISMATCH",
            "intraday_evidence": None,
        }

    quality_status = adapted["data_quality"]["status"]
    status = "PASS" if quality_status == "PASS" else "UNKNOWN"
    return {
        **base,
        "status": status,
        "reason": None if status == "PASS" else quality_status,
        "intraday_evidence": deepcopy(adapted),
    }
