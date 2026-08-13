from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from scripts.morning_dataset.providers.base import ProviderResult

SESSION_SLOTS = ("MORNING", "MIDDAY", "AFTERNOON", "CLOSE")
SOURCE_STATUSES = ("OK", "PARTIAL", "STALE", "MISSING")


@dataclass(frozen=True)
class SnapshotPaths:
    history: Path
    latest: Path


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be offset-aware")
    return parsed


def _normalize_source_status(result: ProviderResult, business_date: date) -> str:
    status = result.status
    if status not in SOURCE_STATUSES:
        raise ValueError(f"unsupported source status: {status}")
    source_time = _parse_timestamp(result.as_of)
    if source_time is not None and source_time.date() < business_date and status in {"OK", "PARTIAL"}:
        return "STALE"
    return status


def _market_values(market: Mapping[str, Any] | None) -> dict[str, float]:
    values: dict[str, float] = {}
    if not market:
        return values
    for group_name in ("indices", "macro"):
        group = market.get(group_name)
        if not isinstance(group, Mapping):
            continue
        for key, item in group.items():
            if not isinstance(item, Mapping):
                continue
            value = item.get("value")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values[f"{group_name}.{key}"] = float(value)
    return values


def calculate_delta(base: Mapping[str, Any] | None, current: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return deterministic value deltas, or None when a usable base is absent."""
    if not base:
        return None
    base_values = _market_values(base.get("market") if isinstance(base, Mapping) else None)
    current_values = _market_values(current.get("market"))
    shared = sorted(set(base_values) & set(current_values))
    if not shared:
        return None
    fields: dict[str, Any] = {}
    for key in shared:
        before = base_values[key]
        after = current_values[key]
        absolute = after - before
        pct = (absolute / before * 100.0) if before != 0 else None
        fields[key] = {
            "before": before,
            "current": after,
            "absolute": absolute,
            "pct": pct,
        }
    return {
        "base_identity": base.get("identity"),
        "fields": fields,
    }


def build_snapshot(
    result: ProviderResult,
    *,
    business_date: date,
    session_slot: str,
    observed_at: datetime,
    previous: Mapping[str, Any] | None = None,
    morning: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if session_slot not in SESSION_SLOTS:
        raise ValueError(f"unsupported session_slot: {session_slot}")
    if observed_at.tzinfo is None:
        raise ValueError("observed_at must be offset-aware")

    source_status = _normalize_source_status(result, business_date)
    market = result.data if isinstance(result.data, Mapping) else {}
    identity = f"{business_date.isoformat()}:{session_slot}"
    snapshot: dict[str, Any] = {
        "schema_version": "1.0",
        "identity": identity,
        "business_date": business_date.isoformat(),
        "session_slot": session_slot,
        "observed_at": observed_at.isoformat(timespec="seconds"),
        "source_timestamp": result.as_of,
        "source_status": source_status,
        "source_reference": result.source_reference,
        "source_reason": result.reason,
        "market": dict(market),
        "previous_snapshot_ref": previous.get("identity") if previous else None,
        "morning_snapshot_ref": morning.get("identity") if morning else (identity if session_slot == "MORNING" else None),
        "delta_from_previous": None,
        "delta_from_morning": None,
        "meaningful_delta": False,
        "review_reasons": [],
    }
    snapshot["delta_from_previous"] = calculate_delta(previous, snapshot)
    if session_slot == "MORNING":
        snapshot["delta_from_morning"] = None
    else:
        snapshot["delta_from_morning"] = calculate_delta(morning, snapshot)
    return snapshot


def snapshot_paths(root: Path, snapshot: Mapping[str, Any]) -> SnapshotPaths:
    business_date = str(snapshot["business_date"])
    slot = str(snapshot["session_slot"])
    return SnapshotPaths(
        history=root / "history" / business_date / f"{slot}.json",
        latest=root / "latest.json",
    )


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def persist_snapshot(root: Path, snapshot: Mapping[str, Any]) -> SnapshotPaths:
    """Persist stable history identity and latest projection without silent overwrite."""
    paths = snapshot_paths(root, snapshot)
    paths.history.parent.mkdir(parents=True, exist_ok=True)
    rendered = _canonical_json(snapshot)
    if paths.history.exists():
        existing = paths.history.read_text(encoding="utf-8")
        if existing != rendered:
            raise ValueError(f"conflicting observation for stable identity {snapshot['identity']}")
    else:
        paths.history.write_text(rendered, encoding="utf-8")
    paths.latest.parent.mkdir(parents=True, exist_ok=True)
    paths.latest.write_text(rendered, encoding="utf-8")
    return paths


def load_snapshot(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_previous(root: Path, business_date: date, session_slot: str) -> dict[str, Any] | None:
    if session_slot not in SESSION_SLOTS:
        raise ValueError(f"unsupported session_slot: {session_slot}")
    index = SESSION_SLOTS.index(session_slot)
    if index == 0:
        return None
    for prior_slot in reversed(SESSION_SLOTS[:index]):
        candidate = root / "history" / business_date.isoformat() / f"{prior_slot}.json"
        loaded = load_snapshot(candidate)
        if loaded is not None:
            return loaded
    return None


def load_morning(root: Path, business_date: date) -> dict[str, Any] | None:
    return load_snapshot(root / "history" / business_date.isoformat() / "MORNING.json")
