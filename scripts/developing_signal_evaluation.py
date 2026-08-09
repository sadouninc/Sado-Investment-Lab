from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Any, Iterable, Mapping

from scripts.developing_signal_registry import validate_signal


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _pct(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator * 100.0 / denominator, 2)


def _lead_days(signal: Mapping[str, Any]) -> float | None:
    if signal.get("status") != "PROMOTED" or not signal.get("promoted_at"):
        return None
    start = _parse_dt(str(signal["first_observed_at"]))
    end = _parse_dt(str(signal["promoted_at"]))
    if end < start:
        raise ValueError("promoted_at cannot precede first_observed_at")
    return round((end - start).total_seconds() / 86400.0, 4)


def evaluate_signals(signals: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Return descriptive Registry metrics without overclaiming sparse samples."""
    validated = [validate_signal(dict(item)) for item in signals]
    ordered = sorted(validated, key=lambda item: (item["first_observed_at"], item["signal_id"]))

    total = len(ordered)
    status_counts: dict[str, int] = defaultdict(int)
    creator_total: dict[str, int] = defaultdict(int)
    creator_promoted: dict[str, int] = defaultdict(int)
    lead_times: list[float] = []

    for signal in ordered:
        status = signal["status"]
        creator = str(signal["created_by"]).upper()
        status_counts[status] += 1
        creator_total[creator] += 1
        if status == "PROMOTED":
            creator_promoted[creator] += 1
            lead = _lead_days(signal)
            if lead is not None:
                lead_times.append(lead)

    sensor_metrics: list[dict[str, Any]] = []
    for creator in sorted(creator_total):
        count = creator_total[creator]
        promoted = creator_promoted.get(creator, 0)
        sensor_metrics.append(
            {
                "sensor": creator,
                "signals": count,
                "promoted": promoted,
                "promotion_rate_pct": _pct(promoted, count),
                "sample_status": "INSUFFICIENT" if count < 5 else "OBSERVABLE",
            }
        )

    lead_summary = {
        "count": len(lead_times),
        "median_days": round(median(lead_times), 4) if lead_times else None,
        "min_days": min(lead_times) if lead_times else None,
        "max_days": max(lead_times) if lead_times else None,
        "sample_status": "INSUFFICIENT" if len(lead_times) < 5 else "OBSERVABLE",
    }

    promoted_count = status_counts.get("PROMOTED", 0)
    dismissed_count = status_counts.get("DISMISSED", 0)
    expired_count = status_counts.get("EXPIRED", 0)
    active_count = sum(
        status_counts.get(status, 0)
        for status in ("WATCHING", "STRENGTHENING", "WEAKENING", "MIXED")
    )

    return {
        "schema_version": 1,
        "signal_count": total,
        "status_counts": dict(sorted(status_counts.items())),
        "rates": {
            "promotion_rate_pct": _pct(promoted_count, total),
            "dismiss_rate_pct": _pct(dismissed_count, total),
            "expiry_rate_pct": _pct(expired_count, total),
            "active_rate_pct": _pct(active_count, total),
        },
        "promotion_lead_time": lead_summary,
        "sensor_metrics": sensor_metrics,
        "sample_status": "INSUFFICIENT" if total < 10 else "OBSERVABLE",
        "interpretation_guard": (
            "Rates are descriptive only; INSUFFICIENT samples must not be used to rank sensors or infer signal quality."
        ),
    }
