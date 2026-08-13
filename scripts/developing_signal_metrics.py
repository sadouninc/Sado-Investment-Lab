from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Iterable

from scripts.developing_signal_registry import TERMINAL_STATUSES, validate_signal


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _hours(start: str, end: str) -> float:
    return max(0.0, (_dt(end) - _dt(start)).total_seconds() / 3600.0)


def evaluate_signals(signals: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Return deterministic lifecycle metrics from canonical Signal records only.

    This function does not infer quality, investment merit, or missed signals.
    Rates are descriptive counts over validated records; absent populations are null.
    """
    validated = [validate_signal(item) for item in signals]
    total = len(validated)
    promoted = [item for item in validated if item["status"] == "PROMOTED"]
    dismissed = [item for item in validated if item["status"] == "DISMISSED"]
    expired = [item for item in validated if item["status"] == "EXPIRED"]
    terminal = [item for item in validated if item["status"] in TERMINAL_STATUSES]

    lead_hours = [
        _hours(item["first_observed_at"], item["promoted_at"])
        for item in promoted
    ]

    by_sensor: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in validated:
        grouped[item["created_by"]].append(item)
    for sensor, items in sorted(grouped.items()):
        sensor_promoted = [item for item in items if item["status"] == "PROMOTED"]
        sensor_leads = [
            _hours(item["first_observed_at"], item["promoted_at"])
            for item in sensor_promoted
        ]
        by_sensor[sensor] = {
            "total": len(items),
            "promoted": len(sensor_promoted),
            "promotion_rate": len(sensor_promoted) / len(items),
            "average_promotion_lead_hours": (
                sum(sensor_leads) / len(sensor_leads) if sensor_leads else None
            ),
        }

    return {
        "total": total,
        "active": total - len(terminal),
        "promoted": len(promoted),
        "dismissed": len(dismissed),
        "expired": len(expired),
        "terminal": len(terminal),
        "promotion_rate": len(promoted) / total if total else None,
        "dismiss_or_expire_rate": (len(dismissed) + len(expired)) / total if total else None,
        "average_promotion_lead_hours": (
            sum(lead_hours) / len(lead_hours) if lead_hours else None
        ),
        "by_sensor": by_sensor,
    }
