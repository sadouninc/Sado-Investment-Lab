from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.developing_signal_registry import TERMINAL_STATUSES, validate_signal


CANONICAL_SIGNAL_STORE = Path("data/signals/developing-signals.jsonl")
ACTIVE_STATUSES = {"WATCHING", "STRENGTHENING", "WEAKENING", "MIXED"}


@dataclass(frozen=True)
class StoreReadResult:
    status: str
    signals: tuple[dict[str, Any], ...]
    diagnostics: tuple[str, ...]


def _canonical_payload(signal: dict[str, Any]) -> str:
    return json.dumps(signal, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sort_key(signal: dict[str, Any]) -> tuple[int, str, str]:
    active_rank = 0 if signal["status"] in ACTIVE_STATUSES else 1
    # ISO-8601 timestamps sort lexically when normalized by the existing validator contract.
    # Reverse timestamp order is applied separately to avoid lossy timestamp transforms.
    return active_rank, signal["last_observed_at"], signal["signal_id"]


def _ordered(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    active = [item for item in signals if item["status"] in ACTIVE_STATUSES]
    terminal = [item for item in signals if item["status"] not in ACTIVE_STATUSES]
    active.sort(key=lambda item: (item["last_observed_at"], item["signal_id"]), reverse=True)
    terminal.sort(key=lambda item: (item["last_observed_at"], item["signal_id"]), reverse=True)
    return active + terminal


def read_store(path: Path = CANONICAL_SIGNAL_STORE) -> StoreReadResult:
    if not path.exists():
        return StoreReadResult("MISSING", (), (f"canonical signal store missing: {path}",))

    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return StoreReadResult("OK", (), ())

    signals: list[dict[str, Any]] = []
    diagnostics: list[str] = []
    seen_ids: set[str] = set()
    for line_number, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            decoded = json.loads(line)
            validated = validate_signal(decoded)
            signal_id = validated["signal_id"]
            if signal_id in seen_ids:
                raise ValueError(f"duplicate signal_id: {signal_id}")
            seen_ids.add(signal_id)
            signals.append(validated)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            diagnostics.append(f"line {line_number}: {exc}")

    status = "PARTIAL" if diagnostics else "OK"
    return StoreReadResult(status, tuple(_ordered(signals)), tuple(diagnostics))


def _assert_update_safe(existing: dict[str, Any], incoming: dict[str, Any]) -> None:
    immutable_fields = ("signal_id", "signal_key", "first_observed_at", "created_by")
    for field in immutable_fields:
        if existing.get(field) != incoming.get(field):
            raise ValueError(f"immutable signal identity conflict: {field}")

    if existing.get("related_entities", []) != incoming.get("related_entities", []):
        raise ValueError("immutable signal identity conflict: related_entities")

    old_observations = existing.get("observations", [])
    new_observations = incoming.get("observations", [])
    if len(new_observations) < len(old_observations) or new_observations[: len(old_observations)] != old_observations:
        raise ValueError("observations are append-only; existing history cannot be changed or removed")

    old_sources = [ref for ref in existing.get("source_refs", []) if ref is not None]
    new_sources = [ref for ref in incoming.get("source_refs", []) if ref is not None]
    if any(ref not in new_sources for ref in old_sources):
        raise ValueError("initial source lineage cannot be removed")

    if existing["status"] in TERMINAL_STATUSES and _canonical_payload(existing) != _canonical_payload(incoming):
        raise ValueError("terminal signal is immutable in the canonical store")


def write_signal(signal: dict[str, Any], path: Path = CANONICAL_SIGNAL_STORE) -> bool:
    """Persist one validated Signal. Returns True only when the store changed."""
    incoming = validate_signal(signal)
    current = read_store(path)
    if current.status == "PARTIAL":
        raise ValueError("canonical signal store is PARTIAL; repair diagnostics before writing")

    by_id = {item["signal_id"]: item for item in current.signals}
    existing = by_id.get(incoming["signal_id"])
    if existing is not None:
        if _canonical_payload(existing) == _canonical_payload(incoming):
            return False
        _assert_update_safe(existing, incoming)

    by_id[incoming["signal_id"]] = incoming
    ordered = _ordered(list(by_id.values()))
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(_canonical_payload(item) + "\n" for item in ordered)
    path.write_text(payload, encoding="utf-8")
    return True
