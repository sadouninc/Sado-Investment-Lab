from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable


class MoneyFlowHistoryError(ValueError):
    pass


def _parse_date(value: Any, field: str = "as_of") -> date:
    if not isinstance(value, str) or not value.strip():
        raise MoneyFlowHistoryError(f"{field} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise MoneyFlowHistoryError(f"{field} must be an ISO date") from exc


def snapshot_key(snapshot: dict[str, Any]) -> tuple[str, str, str]:
    kind = str(snapshot.get("kind") or "").upper()
    entity_id = str(snapshot.get("id") or "").strip()
    as_of = str(snapshot.get("as_of") or "").strip()
    if kind not in {"SECTOR", "THEME"}:
        raise MoneyFlowHistoryError("kind must be SECTOR or THEME")
    if not entity_id:
        raise MoneyFlowHistoryError("id is required")
    _parse_date(as_of)
    return kind, entity_id, as_of


def normalize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        raise MoneyFlowHistoryError("snapshot must be an object")
    normalized = json.loads(json.dumps(snapshot, ensure_ascii=False, sort_keys=True))
    snapshot_key(normalized)
    state = str(normalized.get("state") or "")
    if state not in {"COLD", "WARMING", "INFLOW", "HOT", "OVERHEATED"}:
        raise MoneyFlowHistoryError("snapshot has unsupported state")
    if not isinstance(normalized.get("selection_signal"), bool):
        raise MoneyFlowHistoryError("selection_signal must be boolean")
    return normalized


def load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MoneyFlowHistoryError(f"invalid JSONL at line {line_number}") from exc
        records.append(normalize_snapshot(payload))
    return sorted(records, key=snapshot_key)


def upsert_snapshot(path: Path, snapshot: dict[str, Any]) -> str:
    """Persist one daily snapshot idempotently.

    Returns INSERTED for a new identity and UNCHANGED for an identical retry.
    A conflicting payload for the same (kind, id, as_of) fails closed rather than
    silently rewriting detector history.
    """

    candidate = normalize_snapshot(snapshot)
    key = snapshot_key(candidate)
    records = load_history(path)
    by_key = {snapshot_key(record): record for record in records}
    if key in by_key:
        if by_key[key] == candidate:
            return "UNCHANGED"
        raise MoneyFlowHistoryError(f"conflicting snapshot already exists for {key}")
    records.append(candidate)
    records.sort(key=snapshot_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records)
    path.write_text(content + "\n", encoding="utf-8")
    return "INSERTED"


def _normalize_prices(prices: Iterable[dict[str, Any]]) -> list[tuple[date, float]]:
    normalized: list[tuple[date, float]] = []
    seen: set[date] = set()
    for row in prices:
        day = _parse_date(row.get("date"), "price.date")
        close = row.get("close")
        if not isinstance(close, (int, float)) or float(close) <= 0:
            raise MoneyFlowHistoryError("price.close must be a positive number")
        if day in seen:
            raise MoneyFlowHistoryError(f"duplicate price date: {day.isoformat()}")
        seen.add(day)
        normalized.append((day, float(close)))
    return sorted(normalized)


def evaluate_forward_performance(
    history: Iterable[dict[str, Any]],
    prices_by_entity: dict[str, Iterable[dict[str, Any]]],
    *,
    horizons: tuple[int, ...] = (5, 20, 60),
    selection_only: bool = True,
) -> list[dict[str, Any]]:
    """Evaluate detector snapshots using trading-session forward returns.

    The first market session on or after snapshot.as_of is the base session.
    Missing future sessions stay null; they are never converted to zero return.
    """

    if not horizons or any(not isinstance(h, int) or h <= 0 for h in horizons):
        raise MoneyFlowHistoryError("horizons must contain positive integers")
    price_cache = {entity_id: _normalize_prices(rows) for entity_id, rows in prices_by_entity.items()}
    results: list[dict[str, Any]] = []
    for raw in sorted((normalize_snapshot(row) for row in history), key=snapshot_key):
        if selection_only and not raw["selection_signal"]:
            continue
        entity_id = raw["id"]
        series = price_cache.get(entity_id, [])
        as_of = _parse_date(raw["as_of"])
        base_index = next((index for index, (day, _) in enumerate(series) if day >= as_of), None)
        returns: dict[str, float | None] = {}
        base_date: str | None = None
        if base_index is None:
            for horizon in horizons:
                returns[f"return_{horizon}d"] = None
        else:
            base_day, base_close = series[base_index]
            base_date = base_day.isoformat()
            for horizon in horizons:
                target_index = base_index + horizon
                if target_index >= len(series):
                    returns[f"return_{horizon}d"] = None
                else:
                    target_close = series[target_index][1]
                    returns[f"return_{horizon}d"] = round((target_close / base_close - 1.0) * 100.0, 4)
        results.append(
            {
                "kind": raw["kind"],
                "id": entity_id,
                "name": raw.get("name"),
                "as_of": raw["as_of"],
                "state": raw["state"],
                "flow_score": raw.get("flow_score"),
                "selection_signal": raw["selection_signal"],
                "base_market_date": base_date,
                "forward_returns_pct": returns,
            }
        )
    return results


def _runs(states: list[tuple[date, str]]) -> list[tuple[str, int]]:
    if not states:
        return []
    result: list[tuple[str, int]] = []
    current = states[0][1]
    length = 1
    for _, state in states[1:]:
        if state == current:
            length += 1
        else:
            result.append((current, length))
            current = state
            length = 1
    result.append((current, length))
    return result


def compute_stability_metrics(history: Iterable[dict[str, Any]]) -> dict[str, Any]:
    records = sorted((normalize_snapshot(row) for row in history), key=snapshot_key)
    by_entity: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_day: dict[str, set[str]] = defaultdict(set)
    for record in records:
        by_entity[(record["kind"], record["id"])].append(record)
        # Every snapshot day participates in turnover, even when selection count is zero.
        # This makes 1→0 and 0→1 explicit instead of silently dropping the zero day.
        by_day[record["as_of"]]
        if record["selection_signal"]:
            by_day[record["as_of"]].add(f'{record["kind"]}:{record["id"]}')

    transitions = 0
    comparisons = 0
    warming_runs: list[int] = []
    short_warming_reversals = 0
    for entity_records in by_entity.values():
        states = [(_parse_date(row["as_of"]), row["state"]) for row in entity_records]
        for (_, previous), (_, current) in zip(states, states[1:]):
            comparisons += 1
            transitions += int(previous != current)
        runs = _runs(states)
        for index, (state, length) in enumerate(runs):
            if state != "WARMING":
                continue
            warming_runs.append(length)
            if length <= 2 and index + 1 < len(runs) and runs[index + 1][0] == "COLD":
                short_warming_reversals += 1

    ordered_days = sorted(by_day)
    turnovers: list[float] = []
    for previous_day, current_day in zip(ordered_days, ordered_days[1:]):
        previous = by_day[previous_day]
        current = by_day[current_day]
        union = previous | current
        # Jaccard turnover: if both days have zero selections there is no membership change.
        turnovers.append(0.0 if not union else 1.0 - len(previous & current) / len(union))

    return {
        "snapshot_count": len(records),
        "entity_count": len(by_entity),
        "state_change_rate": round(transitions / comparisons, 4) if comparisons else None,
        "warming_run_count": len(warming_runs),
        "warming_average_duration_sessions": round(sum(warming_runs) / len(warming_runs), 2) if warming_runs else None,
        "warming_short_reversal_rate": round(short_warming_reversals / len(warming_runs), 4) if warming_runs else None,
        "selection_turnover_average": round(sum(turnovers) / len(turnovers), 4) if turnovers else None,
    }
