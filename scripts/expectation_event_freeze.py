from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping

from scripts.expectation_revision import validate_snapshot


class ExpectationEventError(ValueError):
    """Raised when event-time expectation comparison violates the frozen-basis contract."""


FREEZE_STATUSES = {"FROZEN", "UNAVAILABLE", "NEEDS_REVIEW"}
COMPARISON_KINDS = {
    "actual_vs_consensus",
    "company_guidance_vs_consensus",
    "sado_base_vs_consensus",
}


def _dt(value: Any, field: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ExpectationEventError(f"{field} is required")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ExpectationEventError(f"{field} must include timezone")
    return parsed


def _share_basis_key(value: Any) -> tuple[tuple[str, str], ...] | None:
    if value in (None, {}, ""):
        return None
    if not isinstance(value, Mapping):
        return (("value", str(value)),)
    comparable = {
        str(key): str(item)
        for key, item in value.items()
        if key in {"basis", "share_basis", "dilution", "split_adjustment", "shares"} and item is not None
    }
    return tuple(sorted(comparable.items())) or None


def _basis_reason(snapshot: Mapping[str, Any], *, event: Mapping[str, Any], metric: str, unit: str, share_basis: Any) -> str | None:
    if str(snapshot.get("security_code")) != str(event.get("security_code")):
        return "SECURITY_CODE_MISMATCH"
    if str(snapshot.get("target_fiscal_period")) != str(event.get("fiscal_period")):
        return "FISCAL_PERIOD_MISMATCH"
    if str(snapshot.get("metric")) != metric:
        return "METRIC_MISMATCH"
    if str(snapshot.get("unit")) != unit:
        return "UNIT_MISMATCH"
    expected_share = _share_basis_key(share_basis)
    actual_share = _share_basis_key((snapshot.get("provenance") or {}).get("share_basis"))
    if expected_share is not None and actual_share is not None and expected_share != actual_share:
        return "SHARE_BASIS_MISMATCH"
    return None


def freeze_pre_event_expectation(
    event: Mapping[str, Any],
    snapshots: Iterable[Mapping[str, Any]],
    *,
    metric: str,
    unit: str,
    share_basis: Any = None,
) -> dict[str, Any]:
    """Freeze the latest compatible CONSENSUS observed no later than the exact announcement time."""
    event_id = str(event.get("event_id") or "").strip()
    if not event_id or not event.get("security_code") or not event.get("fiscal_period"):
        raise ExpectationEventError("event_id/security_code/fiscal_period are required")

    quality = str(event.get("announcement_time_quality") or "UNKNOWN").upper()
    if quality != "EXACT":
        return {
            "event_id": event_id,
            "metric": metric,
            "pre_event_expectation_ref": None,
            "pre_event_cutoff_at": None,
            "freeze_status": "NEEDS_REVIEW",
            "reason_codes": ["ANNOUNCEMENT_TIME_UNKNOWN"],
            "frozen_at": None,
        }

    cutoff = _dt(event.get("announcement_at"), "announcement_at")
    valid: list[dict[str, Any]] = []
    mismatch_codes: set[str] = set()
    post_event_excluded = False

    for raw in snapshots:
        if str(raw.get("expectation_type")) != "CONSENSUS":
            continue
        snapshot = validate_snapshot(dict(raw))
        reason = _basis_reason(snapshot, event=event, metric=metric, unit=unit, share_basis=share_basis)
        if reason:
            mismatch_codes.add(reason)
            continue
        observed_at = _dt(snapshot.get("observed_at"), "observed_at")
        if observed_at > cutoff:
            post_event_excluded = True
            continue
        if (snapshot.get("coverage") or {}).get("status") == "UNAVAILABLE":
            continue
        valid.append(snapshot)

    if not valid:
        reasons = sorted(mismatch_codes)
        if post_event_excluded:
            reasons.append("POST_EVENT_EXPECTATION_EXCLUDED")
        reasons.append("NO_PRE_EVENT_EXPECTATION")
        return {
            "event_id": event_id,
            "metric": metric,
            "pre_event_expectation_ref": None,
            "pre_event_cutoff_at": cutoff.isoformat(),
            "freeze_status": "UNAVAILABLE",
            "reason_codes": sorted(set(reasons)),
            "frozen_at": cutoff.isoformat(),
        }

    valid.sort(key=lambda row: (_dt(row["observed_at"], "observed_at"), str(row["expectation_id"])))
    latest_time = _dt(valid[-1]["observed_at"], "observed_at")
    latest = [row for row in valid if _dt(row["observed_at"], "observed_at") == latest_time]
    signatures = {(row.get("expectation_id"), row.get("value")) for row in latest}
    if len(signatures) > 1:
        return {
            "event_id": event_id,
            "metric": metric,
            "pre_event_expectation_ref": None,
            "pre_event_cutoff_at": cutoff.isoformat(),
            "freeze_status": "NEEDS_REVIEW",
            "reason_codes": ["CONFLICTING_SNAPSHOT"],
            "frozen_at": cutoff.isoformat(),
        }

    selected = latest[0]
    reasons: list[str] = []
    if post_event_excluded:
        reasons.append("POST_EVENT_EXPECTATION_EXCLUDED")
    if (selected.get("coverage") or {}).get("status") == "STALE":
        reasons.append("STALE_EXPECTATION")

    return {
        "event_id": event_id,
        "metric": metric,
        "pre_event_expectation_ref": selected["expectation_id"],
        "pre_event_cutoff_at": cutoff.isoformat(),
        "freeze_status": "FROZEN",
        "reason_codes": sorted(reasons),
        "frozen_at": cutoff.isoformat(),
        "expectation_snapshot": selected,
    }


def calculate_surprise(
    event: Mapping[str, Any],
    frozen: Mapping[str, Any],
    comparison: Mapping[str, Any],
    *,
    comparison_kind: str = "actual_vs_consensus",
) -> dict[str, Any]:
    """Compare an actual/guidance/Sado value against the immutable frozen consensus basis."""
    if comparison_kind not in COMPARISON_KINDS:
        raise ExpectationEventError("invalid comparison_kind")
    event_id = str(event.get("event_id") or "")
    metric = str(frozen.get("metric") or comparison.get("metric") or "")
    warnings: list[str] = []

    def unavailable(status: str, code: str) -> dict[str, Any]:
        return {
            "event_id": event_id,
            "metric": metric,
            "comparison_kind": comparison_kind,
            "actual_ref": comparison.get("source_ref"),
            "expectation_ref": frozen.get("pre_event_expectation_ref"),
            "actual_value": comparison.get("value"),
            "expectation_value": None,
            "surprise_abs": None,
            "surprise_pct": None,
            "status": status,
            "warning_codes": sorted(set(warnings + [code])),
            "calculated_at": frozen.get("frozen_at"),
        }

    freeze_status = frozen.get("freeze_status")
    if freeze_status != "FROZEN":
        return unavailable("NEEDS_REVIEW" if freeze_status == "NEEDS_REVIEW" else "UNAVAILABLE", "NO_PRE_EVENT_EXPECTATION")

    expectation = frozen.get("expectation_snapshot")
    if not isinstance(expectation, Mapping):
        return unavailable("UNAVAILABLE", "NO_PRE_EVENT_EXPECTATION")

    if str(comparison.get("security_code")) != str(event.get("security_code")):
        return unavailable("NEEDS_REVIEW", "SECURITY_CODE_MISMATCH")
    if str(comparison.get("target_fiscal_period")) != str(event.get("fiscal_period")):
        return unavailable("NEEDS_REVIEW", "FISCAL_PERIOD_MISMATCH")
    if str(comparison.get("metric")) != str(expectation.get("metric")):
        return unavailable("NEEDS_REVIEW", "METRIC_MISMATCH")
    if str(comparison.get("unit")) != str(expectation.get("unit")):
        return unavailable("NEEDS_REVIEW", "UNIT_MISMATCH")

    expected_share = _share_basis_key((expectation.get("provenance") or {}).get("share_basis"))
    actual_share = _share_basis_key(comparison.get("share_basis"))
    if expected_share is not None and actual_share is not None and expected_share != actual_share:
        return unavailable("NEEDS_REVIEW", "SHARE_BASIS_MISMATCH")

    actual_value = comparison.get("value")
    expected_value = expectation.get("value")
    if actual_value is None or expected_value is None:
        return unavailable("UNAVAILABLE", "NO_PRE_EVENT_EXPECTATION")
    actual_num = float(actual_value)
    expected_num = float(expected_value)
    if expected_num == 0:
        return unavailable("NEEDS_REVIEW", "ZERO_EXPECTATION_DENOMINATOR")

    warnings.extend(str(code) for code in frozen.get("reason_codes") or [])
    absolute = actual_num - expected_num
    pct = absolute / abs(expected_num)
    return {
        "event_id": event_id,
        "metric": metric,
        "comparison_kind": comparison_kind,
        "actual_ref": comparison.get("source_ref"),
        "expectation_ref": expectation.get("expectation_id"),
        "actual_value": actual_num,
        "expectation_value": expected_num,
        "surprise_abs": round(absolute, 10),
        "surprise_pct": round(pct, 10),
        "status": "OK",
        "warning_codes": sorted(set(warnings)),
        "calculated_at": frozen.get("frozen_at"),
    }
