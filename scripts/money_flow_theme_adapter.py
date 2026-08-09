from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Callable

from scripts.candidate_selector_sources import candidate_record
from scripts.money_flow_detector import evaluate_snapshot
from scripts.money_flow_sector_adapter import (
    _series,
    derive_sector_scores,
    fetch_yahoo_history,
)

Fetcher = Callable[[str, str, str], dict[str, Any]]


class ThemeAdapterError(ValueError):
    pass


def load_theme_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    benchmark = config.get("benchmark") or {}
    if not benchmark.get("symbol"):
        raise ThemeAdapterError("benchmark.symbol is required")
    themes = config.get("themes")
    if not isinstance(themes, list) or not themes:
        raise ThemeAdapterError("themes must be a non-empty list")
    seen_codes: dict[str, str] = {}
    for theme in themes:
        if not theme.get("id") or not theme.get("name") or not theme.get("membership_as_of"):
            raise ThemeAdapterError("theme id/name/membership_as_of are required")
        members = theme.get("members")
        if not isinstance(members, list) or not members:
            raise ThemeAdapterError(f"{theme.get('id')} members must be non-empty")
        local_codes: set[str] = set()
        for member in members:
            code = str(member.get("security_code") or "").strip()
            name = str(member.get("company_name") or "").strip()
            symbol = str(member.get("symbol") or "").strip()
            if not code or not name or not symbol:
                raise ThemeAdapterError("theme member security_code/company_name/symbol are required")
            if code in local_codes:
                raise ThemeAdapterError(f"duplicate member {code} in {theme['id']}")
            local_codes.add(code)
            seen_codes.setdefault(code, name)
    return config


def _mean(values: list[float | None]) -> float | None:
    valid = [float(v) for v in values if v is not None]
    return round(sum(valid) / len(valid), 2) if valid else None


def _theme_scores(member_results: list[dict[str, Any]]) -> tuple[dict[str, float | None], list[str], dict[str, Any]]:
    scores = {
        "relative_strength": _mean([m["scores"].get("relative_strength") for m in member_results]),
        "activity": _mean([m["scores"].get("activity") for m in member_results]),
        "breadth": None,
        "heat": _mean([m["scores"].get("heat") for m in member_results]),
        "acceleration": _mean([m["scores"].get("acceleration") for m in member_results]),
    }

    medium_rel = [
        m["metrics"].get("relative_returns_pct", {}).get("medium")
        for m in member_results
        if m["metrics"].get("relative_returns_pct", {}).get("medium") is not None
    ]
    if medium_rel:
        scores["breadth"] = round(sum(1 for value in medium_rel if float(value) > 0.0) / len(medium_rel) * 100.0, 2)

    evidence = [
        f"member_coverage={len(member_results)}",
        (
            f"breadth_outperforming_topix_20d={scores['breadth']:.1f}%"
            if scores["breadth"] is not None
            else "breadth_outperforming_topix_20d=missing"
        ),
    ]
    metrics = {
        "member_count_with_market_data": len(member_results),
        "member_relative_return_20d_pct": {
            m["security_code"]: m["metrics"].get("relative_returns_pct", {}).get("medium")
            for m in member_results
        },
    }
    return scores, evidence, metrics


def build_theme_snapshots(
    *,
    theme_config: dict[str, Any],
    sector_config: dict[str, Any],
    detector_config: dict[str, Any],
    as_of: date,
    fetcher: Fetcher = fetch_yahoo_history,
    previous: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    previous = previous or {}
    range_ = str(theme_config.get("history_range") or "6mo")
    interval = str(theme_config.get("interval") or "1d")
    benchmark_symbol = str((theme_config.get("benchmark") or {}).get("symbol") or "")
    if not benchmark_symbol:
        raise ThemeAdapterError("benchmark.symbol is required")
    benchmark_series = _series(fetcher(benchmark_symbol, range_, interval), benchmark_symbol)

    snapshots: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for theme in theme_config["themes"]:
        member_results: list[dict[str, Any]] = []
        missing_members: list[dict[str, str]] = []
        for member in theme["members"]:
            code = str(member["security_code"])
            symbol = str(member["symbol"])
            try:
                member_series = _series(fetcher(symbol, range_, interval), symbol)
                scores, source_evidence, metrics = derive_sector_scores(
                    member_series,
                    benchmark_series,
                    config=sector_config,
                )
                member_results.append(
                    {
                        "security_code": code,
                        "company_name": str(member["company_name"]),
                        "symbol": symbol,
                        "scores": scores,
                        "source_evidence": source_evidence,
                        "metrics": metrics,
                    }
                )
            except Exception as exc:
                missing_members.append({"security_code": code, "symbol": symbol, "reason": exc.__class__.__name__})

        if not member_results:
            failures.append({"id": str(theme["id"]), "reason": "all theme members unavailable"})
            continue

        scores, source_evidence, metrics = _theme_scores(member_results)
        prior = previous.get(str(theme["id"])) or {}
        raw = {
            "id": str(theme["id"]),
            "name": str(theme["name"]),
            "kind": "THEME",
            "scores": scores,
            "previous_state": str(prior.get("state") or "COLD"),
            "prior_target_state": prior.get("target_state"),
            "target_streak": int(prior.get("target_streak") or 0),
            "state_since": prior.get("state_since"),
            "member_count": len(theme["members"]),
            "membership_as_of": str(theme["membership_as_of"]),
        }
        snapshot = evaluate_snapshot(raw, config=detector_config, as_of=as_of)
        snapshot["source_evidence"] = source_evidence
        snapshot["metrics"] = metrics
        snapshot["members"] = [
            {
                "security_code": str(member["security_code"]),
                "company_name": str(member["company_name"]),
                "symbol": str(member["symbol"]),
            }
            for member in theme["members"]
        ]
        snapshot["coverage"] = {
            "available": len(member_results),
            "requested": len(theme["members"]),
            "missing": missing_members,
        }
        snapshots.append(snapshot)

    return {
        "schema_version": 1,
        "as_of": as_of.isoformat(),
        "benchmark": theme_config["benchmark"],
        "themes": snapshots,
        "coverage": {
            "available": len(snapshots),
            "requested": len(theme_config["themes"]),
            "missing": failures,
        },
    }


def theme_snapshots_to_candidate_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for theme in payload.get("themes") or []:
        state = str(theme.get("state") or "")
        if state not in {"WARMING", "INFLOW"} or not bool(theme.get("selection_signal")):
            continue
        flow_score = theme.get("flow_score")
        acceleration = (theme.get("scores") or {}).get("acceleration")
        breadth = (theme.get("scores") or {}).get("breadth")
        reason = (
            f"Money Flow {state}: {theme.get('name')}"
            + (f" / flow_score {float(flow_score):.1f}" if flow_score is not None else "")
        )
        for member in theme.get("members") or []:
            code = str(member.get("security_code") or "").strip()
            name = str(member.get("company_name") or "").strip()
            if not code or not name:
                continue
            row = candidate_record(
                company_name=name,
                security_code=code,
                source="MONEY_FLOW",
                reason=reason,
            )
            row["signals"]["investment_relevance"] = flow_score
            row["signals"]["theme_relevance"] = flow_score
            row["signals"]["change_signal"] = _mean([acceleration, breadth])
            row["signal_reasons"]["investment_relevance"] = [reason]
            row["signal_reasons"]["theme_relevance"] = [reason]
            row["signal_reasons"]["change_signal"] = [
                f"theme acceleration={acceleration}; breadth={breadth}"
            ]
            row["updated_at"] = payload.get("as_of")
            rows.append(row)
    return rows
