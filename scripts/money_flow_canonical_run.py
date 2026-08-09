from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Callable

from scripts.money_flow_detector import load_config as load_detector_config
from scripts.money_flow_history import load_history, upsert_snapshot
from scripts.money_flow_sector_adapter import fetch_yahoo_history, load_sector_config
from scripts.money_flow_theme_adapter import build_theme_snapshots, load_theme_config

Fetcher = Callable[[str, str, str], dict[str, Any]]

DEFAULT_THEME_ID = "theme:ai-data-center-power-infrastructure"
DEFAULT_POLICY_T0 = date(2024, 10, 4)


class CanonicalRunError(ValueError):
    pass


def _latest_previous(history: list[dict[str, Any]], *, as_of: date) -> dict[str, dict[str, Any]]:
    previous: dict[str, dict[str, Any]] = {}
    for row in history:
        if row.get("kind") != "THEME":
            continue
        row_date = date.fromisoformat(str(row["as_of"]))
        if row_date >= as_of:
            continue
        entity_id = str(row["id"])
        current = previous.get(entity_id)
        if current is None or str(current["as_of"]) < str(row["as_of"]):
            previous[entity_id] = row
    return previous


def _theme_config_entry(theme_config: dict[str, Any], theme_id: str) -> dict[str, Any]:
    matches = [row for row in theme_config.get("themes") or [] if str(row.get("id")) == theme_id]
    if len(matches) != 1:
        raise CanonicalRunError(f"theme config must contain exactly one {theme_id}")
    return matches[0]


def canonical_snapshot(
    *,
    theme_id: str,
    as_of: date,
    theme_config: dict[str, Any],
    sector_config: dict[str, Any],
    detector_config: dict[str, Any],
    history: list[dict[str, Any]],
    fetcher: Fetcher = fetch_yahoo_history,
) -> dict[str, Any]:
    entry = _theme_config_entry(theme_config, theme_id)
    payload = build_theme_snapshots(
        theme_config=theme_config,
        sector_config=sector_config,
        detector_config=detector_config,
        as_of=as_of,
        fetcher=fetcher,
        previous=_latest_previous(history, as_of=as_of),
    )
    matches = [row for row in payload.get("themes") or [] if str(row.get("id")) == theme_id]
    if not matches:
        coverage = payload.get("coverage") or {}
        return {
            "kind": "THEME",
            "id": theme_id,
            "name": str(entry.get("name") or theme_id),
            "as_of": as_of.isoformat(),
            "data_completeness": "UNAVAILABLE",
            "missing_reason": "all theme members unavailable",
            "coverage": coverage,
            "membership_as_of": entry.get("membership_as_of"),
            "membership_version": entry.get("membership_version"),
            "members": entry.get("members") or [],
            "persistable": False,
        }

    snapshot = dict(matches[0])
    snapshot["membership_version"] = entry.get("membership_version") or str(entry.get("membership_as_of"))
    snapshot["backfill_policy"] = entry.get("backfill_policy")
    completeness = str(snapshot.get("data_completeness") or "").upper()
    if completeness == "INSUFFICIENT":
        snapshot["data_completeness"] = "PARTIAL"
    snapshot["missing_reason"] = snapshot.get("missing_reason") or None
    snapshot["persistable"] = True
    return snapshot


def persist_canonical_snapshot(path: Path, snapshot: dict[str, Any]) -> str:
    if not snapshot.get("persistable"):
        return "NOT_PERSISTED_UNAVAILABLE"
    candidate = dict(snapshot)
    candidate.pop("persistable", None)
    return upsert_snapshot(path, candidate)


def first_state_date(history: list[dict[str, Any]], *, theme_id: str, state: str) -> str | None:
    target = state.upper()
    if target not in {"WARMING", "INFLOW"}:
        raise CanonicalRunError("state must be WARMING or INFLOW")
    dates = sorted(
        str(row["as_of"])
        for row in history
        if row.get("kind") == "THEME" and str(row.get("id")) == theme_id and row.get("state") == target
    )
    return dates[0] if dates else None


def evaluate_policy_lead_time(
    history: list[dict[str, Any]],
    *,
    theme_id: str = DEFAULT_THEME_ID,
    policy_t0: date = DEFAULT_POLICY_T0,
    retrospective_membership: bool = False,
) -> dict[str, Any]:
    warming = first_state_date(history, theme_id=theme_id, state="WARMING")
    inflow = first_state_date(history, theme_id=theme_id, state="INFLOW")

    def delta(value: str | None) -> int | None:
        return None if value is None else (date.fromisoformat(value) - policy_t0).days

    limitations: list[str] = []
    if retrospective_membership:
        limitations.append("RETROSPECTIVE_MEMBERSHIP")
    if warming is None:
        limitations.append("FIRST_WARMING_NOT_OBSERVED")
    if inflow is None:
        limitations.append("FIRST_INFLOW_NOT_OBSERVED")

    return {
        "theme_id": theme_id,
        "policy_t0": policy_t0.isoformat(),
        "first_warming_date": warming,
        "first_inflow_date": inflow,
        "policy_to_warming_days": delta(warming),
        "policy_to_inflow_days": delta(inflow),
        "limitations": limitations,
    }


def run_once(
    *,
    as_of: date,
    history_path: Path,
    theme_config_path: Path,
    sector_config_path: Path,
    detector_config_path: Path,
    theme_id: str = DEFAULT_THEME_ID,
    fetcher: Fetcher = fetch_yahoo_history,
) -> dict[str, Any]:
    history = load_history(history_path)
    theme_config = load_theme_config(theme_config_path)
    sector_config = load_sector_config(sector_config_path)
    detector_config = load_detector_config(detector_config_path)
    snapshot = canonical_snapshot(
        theme_id=theme_id,
        as_of=as_of,
        theme_config=theme_config,
        sector_config=sector_config,
        detector_config=detector_config,
        history=history,
        fetcher=fetcher,
    )
    persistence = persist_canonical_snapshot(history_path, snapshot)
    updated_history = load_history(history_path)
    entry = _theme_config_entry(theme_config, theme_id)
    lead_time = evaluate_policy_lead_time(
        updated_history,
        theme_id=theme_id,
        retrospective_membership=(
            str(entry.get("backfill_policy") or "") == "RETROSPECTIVE_MEMBERSHIP_IF_HISTORICAL_MEMBERSHIP_UNAVAILABLE"
            and as_of < date.fromisoformat(str(entry["membership_as_of"]))
        ),
    )
    return {"snapshot": snapshot, "persistence": persistence, "lead_time": lead_time}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run canonical Money Flow Theme snapshot once")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--theme-id", default=DEFAULT_THEME_ID)
    parser.add_argument("--history", default="data/generated/public/money-flow/history.jsonl")
    parser.add_argument("--themes", default="data/config/money-flow-themes-v1.json")
    parser.add_argument("--sector", default="data/config/money-flow-sector-v1.json")
    parser.add_argument("--detector", default="data/config/money-flow-detector-v1.json")
    args = parser.parse_args()

    result = run_once(
        as_of=date.fromisoformat(args.as_of),
        history_path=Path(args.history),
        theme_config_path=Path(args.themes),
        sector_config_path=Path(args.sector),
        detector_config_path=Path(args.detector),
        theme_id=args.theme_id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
