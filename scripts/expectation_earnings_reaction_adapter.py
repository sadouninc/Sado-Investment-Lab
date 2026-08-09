from __future__ import annotations

import copy
from datetime import datetime
from typing import Any, Iterable, Mapping

from scripts.expectation_event_freeze import calculate_surprise, freeze_pre_event_expectation
from scripts.expectation_revision import summarize_revision_direction, validate_snapshot


class ExpectationReactionAdapterError(ValueError):
    """Raised when Expectation context cannot be safely attached to an earnings event."""


def _dt(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ExpectationReactionAdapterError("timestamp must include timezone")
    return parsed


def _share_basis_key(value: Any) -> tuple[tuple[str, str], ...] | None:
    if value in (None, {}, ""):
        return None
    if not isinstance(value, Mapping):
        return (("value", str(value)),)
    comparable = {
        str(key): str(item)
        for key, item in value.items()
        if key in {"basis", "share_basis", "dilution", "split_adjustment", "shares", "diluted_shares"}
        and item is not None
    }
    return tuple(sorted(comparable.items())) or None


def _pre_event_consensus_series(
    event: Mapping[str, Any],
    snapshots: Iterable[Mapping[str, Any]],
    *,
    metric: str,
    unit: str,
    share_basis: Any = None,
) -> list[dict[str, Any]]:
    if str(event.get("announcement_time_quality") or "UNKNOWN").upper() != "EXACT":
        return []
    cutoff = _dt(event.get("announcement_at"))
    expected_share = _share_basis_key(share_basis)
    rows: list[dict[str, Any]] = []
    for raw in snapshots:
        if str(raw.get("expectation_type")) != "CONSENSUS":
            continue
        snapshot = validate_snapshot(dict(raw))
        if str(snapshot.get("security_code")) != str(event.get("security_code")):
            continue
        if str(snapshot.get("target_fiscal_period")) != str(event.get("fiscal_period")):
            continue
        if str(snapshot.get("metric")) != str(metric) or str(snapshot.get("unit")) != str(unit):
            continue
        actual_share = _share_basis_key((snapshot.get("provenance") or {}).get("share_basis"))
        if expected_share is not None and actual_share is not None and expected_share != actual_share:
            continue
        if _dt(snapshot.get("observed_at")) > cutoff:
            continue
        if (snapshot.get("coverage") or {}).get("status") == "UNAVAILABLE":
            continue
        rows.append(snapshot)
    return sorted(rows, key=lambda row: (_dt(row["observed_at"]), str(row["expectation_id"])))


def build_earnings_reaction_expectation_context(
    event: Mapping[str, Any],
    expectation_history: Iterable[Mapping[str, Any]],
    actual: Mapping[str, Any],
    *,
    metric: str,
    unit: str,
    share_basis: Any = None,
) -> dict[str, Any]:
    """Build #43 expectation input without mixing it with fundamental or price-reaction quality."""
    snapshots = [copy.deepcopy(dict(row)) for row in expectation_history]
    frozen = freeze_pre_event_expectation(
        event,
        snapshots,
        metric=metric,
        unit=unit,
        share_basis=share_basis,
    )
    surprise = calculate_surprise(
        event,
        frozen,
        actual,
        comparison_kind="actual_vs_consensus",
    )
    series = _pre_event_consensus_series(
        event,
        snapshots,
        metric=metric,
        unit=unit,
        share_basis=share_basis,
    )

    direction = summarize_revision_direction(series)
    latest_pre_event = series[-1] if series else None
    warning_codes = sorted(
        set(
            list(frozen.get("reason_codes") or [])
            + list(surprise.get("warning_codes") or [])
        )
    )

    return {
        "event_id": event.get("event_id"),
        "security_code": event.get("security_code"),
        "fiscal_period": event.get("fiscal_period"),
        "expectation_axis": {
            "metric": metric,
            "unit": unit,
            "pre_event_expectation_ref": frozen.get("pre_event_expectation_ref"),
            "pre_event_cutoff_at": frozen.get("pre_event_cutoff_at"),
            "freeze_status": frozen.get("freeze_status"),
            "pre_event_revision_direction": direction,
            "pre_event_observation_count": len(series),
            "latest_pre_event_value": None if latest_pre_event is None else latest_pre_event.get("value"),
            "latest_pre_event_observed_at": None if latest_pre_event is None else latest_pre_event.get("observed_at"),
        },
        "expectation_surprise": copy.deepcopy(surprise),
        "warning_codes": warning_codes,
        "status": surprise.get("status"),
        "provenance": {
            "event_source_ref": event.get("source_ref"),
            "actual_source_ref": actual.get("source_ref"),
            "expectation_ref": frozen.get("pre_event_expectation_ref"),
        },
        "boundary": {
            "fundamental_quality": "NOT_CALCULATED_HERE",
            "market_price_reaction": "NOT_CALCULATED_HERE",
            "expectation_context_only": True,
        },
    }


def attach_expectation_to_earnings_reaction(
    earnings_event_record: Mapping[str, Any],
    expectation_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach the #199 Expectation axis to a #43 event record without mutating the event."""
    if str(earnings_event_record.get("security_code")) != str(expectation_context.get("security_code")):
        raise ExpectationReactionAdapterError("event/expectation security_code mismatch")
    event_id = earnings_event_record.get("event_id")
    if event_id is not None and str(event_id) != str(expectation_context.get("event_id")):
        raise ExpectationReactionAdapterError("event_id mismatch")
    result = copy.deepcopy(dict(earnings_event_record))
    result["expectation_context"] = copy.deepcopy(dict(expectation_context))
    return result
