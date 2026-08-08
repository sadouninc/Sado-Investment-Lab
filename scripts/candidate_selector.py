from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable


SIGNAL_KEYS = (
    "investment_relevance",
    "change_signal",
    "research_gap",
    "theme_relevance",
    "valuation_interest",
)
VALID_RESEARCH_STATUS = {"NOT_STARTED", "IN_PROGRESS", "CURRENT", "STALE"}


class CandidateSelectorError(ValueError):
    pass


def load_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    weights = payload.get("weights")
    if not isinstance(weights, dict) or set(weights) != set(SIGNAL_KEYS):
        raise CandidateSelectorError("config weights must define every signal key exactly once")
    if any(not isinstance(weights[key], (int, float)) or weights[key] < 0 for key in SIGNAL_KEYS):
        raise CandidateSelectorError("signal weights must be non-negative numbers")
    if sum(float(weights[key]) for key in SIGNAL_KEYS) <= 0:
        raise CandidateSelectorError("signal weights must have a positive total")
    freshness_days = payload.get("freshness_days")
    major_change_threshold = payload.get("major_change_threshold")
    if not isinstance(freshness_days, int) or freshness_days < 1:
        raise CandidateSelectorError("freshness_days must be a positive integer")
    if not isinstance(major_change_threshold, (int, float)) or not 0 <= major_change_threshold <= 100:
        raise CandidateSelectorError("major_change_threshold must be within 0..100")
    return payload


def _validate_score(value: Any, key: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or not 0 <= value <= 100:
        raise CandidateSelectorError(f"{key} must be null or within 0..100")
    return float(value)


def normalize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    row = deepcopy(candidate)
    code = row.get("security_code")
    row["security_code"] = str(code).strip() if code not in (None, "") else None
    name = str(row.get("company_name") or "").strip()
    if not name:
        raise CandidateSelectorError("company_name is required")
    row["company_name"] = name

    sources = row.get("candidate_sources") or []
    if not isinstance(sources, list):
        raise CandidateSelectorError("candidate_sources must be a list")
    row["candidate_sources"] = sorted({str(value).strip() for value in sources if str(value).strip()})

    source_reasons = row.get("source_reasons") or {}
    if not isinstance(source_reasons, dict):
        raise CandidateSelectorError("source_reasons must be an object")
    row["source_reasons"] = {
        str(key): sorted({str(item).strip() for item in (value if isinstance(value, list) else [value]) if str(item).strip()})
        for key, value in source_reasons.items()
    }

    signals = row.get("signals") or {}
    signal_reasons = row.get("signal_reasons") or {}
    if not isinstance(signals, dict) or not isinstance(signal_reasons, dict):
        raise CandidateSelectorError("signals and signal_reasons must be objects")
    row["signals"] = {key: _validate_score(signals.get(key), key) for key in SIGNAL_KEYS}
    row["signal_reasons"] = {
        key: sorted({str(item).strip() for item in (signal_reasons.get(key) or []) if str(item).strip()})
        for key in SIGNAL_KEYS
    }

    row["owner_pick"] = bool(row.get("owner_pick"))
    note = row.get("owner_pick_note")
    row["owner_pick_note"] = str(note).strip() if note not in (None, "") else None
    status = str(row.get("research_status") or "NOT_STARTED")
    if status not in VALID_RESEARCH_STATUS:
        raise CandidateSelectorError(f"unsupported research_status: {status}")
    row["research_status"] = status
    last = row.get("last_researched_at")
    row["last_researched_at"] = str(last).strip() if last not in (None, "") else None
    updated = row.get("updated_at")
    row["updated_at"] = str(updated).strip() if updated not in (None, "") else None
    row["selection_reason"] = str(row.get("selection_reason") or "")
    row["total_priority"] = row.get("total_priority")
    return row


def _merge_unique(*values: Iterable[str]) -> list[str]:
    return sorted({item for group in values for item in group if item})


def _merge_pair(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(left)
    result["candidate_sources"] = _merge_unique(left["candidate_sources"], right["candidate_sources"])
    result["owner_pick"] = left["owner_pick"] or right["owner_pick"]
    notes = _merge_unique(
        [left["owner_pick_note"]] if left["owner_pick_note"] else [],
        [right["owner_pick_note"]] if right["owner_pick_note"] else [],
    )
    result["owner_pick_note"] = " / ".join(notes) if notes else None

    for source in sorted(set(left["source_reasons"]) | set(right["source_reasons"])):
        result["source_reasons"][source] = _merge_unique(
            left["source_reasons"].get(source, []), right["source_reasons"].get(source, [])
        )

    for key in SIGNAL_KEYS:
        values = [value for value in (left["signals"][key], right["signals"][key]) if value is not None]
        result["signals"][key] = max(values) if values else None
        result["signal_reasons"][key] = _merge_unique(
            left["signal_reasons"][key], right["signal_reasons"][key]
        )

    rank = {"NOT_STARTED": 0, "CURRENT": 1, "STALE": 2, "IN_PROGRESS": 3}
    result["research_status"] = max(
        (left["research_status"], right["research_status"]), key=lambda value: rank[value]
    )
    dates = [value for value in (left["last_researched_at"], right["last_researched_at"]) if value]
    result["last_researched_at"] = max(dates) if dates else None
    updated = [value for value in (left["updated_at"], right["updated_at"]) if value]
    result["updated_at"] = max(updated) if updated else None
    return result


def merge_candidates(candidates: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    merged_by_code: dict[str, dict[str, Any]] = {}
    unresolved: list[dict[str, Any]] = []
    for raw in candidates:
        row = normalize_candidate(raw)
        code = row["security_code"]
        if code is None:
            unresolved.append(row)
            continue
        if code in merged_by_code:
            merged_by_code[code] = _merge_pair(merged_by_code[code], row)
        else:
            merged_by_code[code] = row
    return [merged_by_code[key] for key in sorted(merged_by_code)] + unresolved


def refresh_research_status(
    candidate: dict[str, Any], *, as_of: date, freshness_days: int, major_change_threshold: float
) -> str:
    status = candidate["research_status"]
    if status == "IN_PROGRESS" or status == "NOT_STARTED":
        return status
    last = candidate.get("last_researched_at")
    if last:
        try:
            researched = date.fromisoformat(str(last)[:10])
        except ValueError as exc:
            raise CandidateSelectorError("last_researched_at must start with YYYY-MM-DD") from exc
        if (as_of - researched).days > freshness_days:
            return "STALE"
    change = candidate["signals"].get("change_signal")
    if change is not None and change >= major_change_threshold:
        return "STALE"
    return status


def calculate_priority(candidate: dict[str, Any], weights: dict[str, float]) -> float | None:
    available = [key for key in SIGNAL_KEYS if candidate["signals"].get(key) is not None and weights[key] > 0]
    if not available:
        return None
    total_weight = sum(float(weights[key]) for key in available)
    return round(
        sum(float(candidate["signals"][key]) * float(weights[key]) for key in available) / total_weight,
        2,
    )


def selection_reason(candidate: dict[str, Any], weights: dict[str, float], *, top_n: int = 3) -> str:
    ranked = []
    for key in SIGNAL_KEYS:
        score = candidate["signals"].get(key)
        if score is None:
            continue
        ranked.append((float(score) * float(weights[key]), key, score))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    parts: list[str] = []
    for _, key, score in ranked[:top_n]:
        reasons = candidate["signal_reasons"].get(key) or []
        detail = f" — {reasons[0]}" if reasons else ""
        parts.append(f"{key} {score:g}{detail}")
    if not parts:
        source_bits = []
        for source in candidate["candidate_sources"]:
            reasons = candidate["source_reasons"].get(source) or []
            source_bits.append(f"{source}: {reasons[0]}" if reasons else source)
        return "; ".join(source_bits[:top_n]) or "評価可能なシグナルなし"
    return "; ".join(parts)


def build_selector(
    candidates: Iterable[dict[str, Any]], *, config: dict[str, Any], as_of: date
) -> dict[str, Any]:
    merged = merge_candidates(candidates)
    weights = {key: float(config["weights"][key]) for key in SIGNAL_KEYS}
    for row in merged:
        row["research_status"] = refresh_research_status(
            row,
            as_of=as_of,
            freshness_days=int(config["freshness_days"]),
            major_change_threshold=float(config["major_change_threshold"]),
        )
        row["total_priority"] = calculate_priority(row, weights)
        row["selection_reason"] = selection_reason(row, weights)
        row["updated_at"] = row["updated_at"] or as_of.isoformat()

    def sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
        priority = row["total_priority"]
        return (priority is None, -(priority or 0), row["security_code"] or "", row["company_name"])

    ranked = sorted(merged, key=sort_key)
    owner_picks = [row for row in ranked if row["owner_pick"]]
    return {
        "schema_version": 1,
        "as_of": as_of.isoformat(),
        "owner_picks": owner_picks,
        "ranked_candidates": ranked,
        "candidates": merged,
    }


def parse_as_of(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CandidateSelectorError("as_of must be YYYY-MM-DD") from exc


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build explainable research candidate ranking")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--config", type=Path, default=Path("data/config/candidate-selector-v1.json"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        source = json.loads(args.input.read_text(encoding="utf-8"))
        rows = source.get("candidates") if isinstance(source, dict) else source
        if not isinstance(rows, list):
            raise CandidateSelectorError("input must be a list or an object with candidates list")
        result = build_selector(rows, config=config, as_of=parse_as_of(args.as_of))
    except (OSError, json.JSONDecodeError, CandidateSelectorError) as exc:
        parser.exit(2, f"candidate selector error: {exc}\n")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Candidate Selector: {len(result['candidates'])} candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
