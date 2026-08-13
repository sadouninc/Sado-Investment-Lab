from __future__ import annotations

from typing import Any, Mapping

USABLE_SOURCE_STATUS = "OK"


def project_review_candidate(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Project a canonical intraday snapshot into a read-only review candidate.

    This projection never invents a market-move threshold. It only consumes an
    explicit upstream ``meaningful_delta`` decision and its ``review_reasons``.
    A review reason is valid only when it is a non-empty string after trimming;
    normalized output stores the trimmed string. Non-OK source data fails closed
    and cannot become REVIEW_REQUIRED.
    """
    source_status = snapshot.get("source_status")
    meaningful_delta = snapshot.get("meaningful_delta") is True
    reasons = snapshot.get("review_reasons")
    explicit_reasons = (
        [item.strip() for item in reasons if isinstance(item, str) and item.strip()]
        if isinstance(reasons, list)
        else []
    )

    if source_status != USABLE_SOURCE_STATUS:
        state = "DATA_QUALITY_BLOCKED"
        review_required = False
    elif meaningful_delta and explicit_reasons:
        state = "REVIEW_REQUIRED"
        review_required = True
    else:
        state = "NO_REVIEW_REQUIRED"
        review_required = False

    return {
        "schema_version": "1.0",
        "candidate_type": "INTRADAY_MARKET_REVIEW",
        "snapshot_ref": snapshot.get("identity"),
        "business_date": snapshot.get("business_date"),
        "session_slot": snapshot.get("session_slot"),
        "observed_at": snapshot.get("observed_at"),
        "source_status": source_status,
        "state": state,
        "review_required": review_required,
        "review_reasons": explicit_reasons,
        "meaningful_delta": meaningful_delta,
        "delta_from_previous": snapshot.get("delta_from_previous"),
        "delta_from_morning": snapshot.get("delta_from_morning"),
        "mutation_performed": False,
    }
