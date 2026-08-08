from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from scripts.candidate_selector import build_selector, load_config, parse_as_of
from scripts.candidate_selector_sources import build_source_candidates, candidate_record, render_shortlist

SOURCE_FILES = {
    "NEWS_THEME": Path("data/candidates/news-theme.json"),
    "EARNINGS_CHANGE": Path("data/candidates/earnings-change.json"),
    "QUANT_VALUATION": Path("data/candidates/quant-valuation.json"),
}

ALLOWED_SIGNALS = {
    "NEWS_THEME": {"investment_relevance", "change_signal", "theme_relevance"},
    "EARNINGS_CHANGE": {"investment_relevance", "change_signal", "valuation_interest"},
    "QUANT_VALUATION": {"investment_relevance", "valuation_interest"},
}


def _score(value: Any, *, field: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or not 0 <= value <= 100:
        raise ValueError(f"{field} must be null or within 0..100")
    return float(value)


def load_structured_candidates(path: Path | None, *, source: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if source not in ALLOWED_SIGNALS:
        raise ValueError(f"unsupported source: {source}")
    if path is None or not path.is_file():
        return [], {
            "status": "MISSING",
            "source_reference": str(path) if path else None,
            "reason": "structured candidate source not found",
            "count": 0,
        }

    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("candidates") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError(f"{source} source must be a list or object with candidates list")

    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f"{source} candidate must be an object")
        name = str(item.get("company_name") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if not name:
            raise ValueError(f"{source} company_name is required")
        if not reason:
            raise ValueError(f"{source} reason is required")
        code = str(item.get("security_code") or "").strip() or None
        row = candidate_record(
            company_name=name,
            security_code=code,
            source=source,
            reason=reason,
        )
        scores = item.get("signals") or {}
        if not isinstance(scores, dict):
            raise ValueError(f"{source} signals must be an object")
        unexpected = set(scores) - ALLOWED_SIGNALS[source]
        if unexpected:
            raise ValueError(f"{source} unsupported signals: {sorted(unexpected)}")
        for key in ALLOWED_SIGNALS[source]:
            value = _score(scores.get(key), field=f"{source}.{key}")
            row["signals"][key] = value
            if value is not None:
                detail = str((item.get("signal_reasons") or {}).get(key) or reason).strip()
                row["signal_reasons"][key] = [detail]
        updated_at = str(item.get("updated_at") or "").strip()
        row["updated_at"] = updated_at or None
        rows.append(row)

    return rows, {
        "status": "OK",
        "source_reference": str(path),
        "reason": None,
        "count": len(rows),
    }


def build_all_candidate_sources(
    *,
    current_status: Path,
    research_root: Path,
    owner_picks: Path | None,
    news_theme: Path | None,
    earnings_change: Path | None,
    quant_valuation: Path | None,
    as_of: date,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, status = build_source_candidates(
        current_status=current_status,
        research_root=research_root,
        owner_picks=owner_picks,
        as_of=as_of,
    )
    signal_paths = {
        "NEWS_THEME": news_theme,
        "EARNINGS_CHANGE": earnings_change,
        "QUANT_VALUATION": quant_valuation,
    }
    for source, path in signal_paths.items():
        source_rows, source_status = load_structured_candidates(path, source=source)
        rows.extend(source_rows)
        status[source] = source_status
    return rows, status


def main() -> int:
    parser = argparse.ArgumentParser(description="Build #108 candidate selector from all v1 source adapters")
    parser.add_argument("--current-status", type=Path, default=Path("Current_Status.md"))
    parser.add_argument("--research-root", type=Path, default=Path("03_Companies"))
    parser.add_argument("--owner-picks", type=Path, default=Path("data/candidates/owner-picks.json"))
    parser.add_argument("--news-theme", type=Path, default=SOURCE_FILES["NEWS_THEME"])
    parser.add_argument("--earnings-change", type=Path, default=SOURCE_FILES["EARNINGS_CHANGE"])
    parser.add_argument("--quant-valuation", type=Path, default=SOURCE_FILES["QUANT_VALUATION"])
    parser.add_argument("--config", type=Path, default=Path("data/config/candidate-selector-v1.json"))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", type=Path, default=Path("data/generated/public/candidate-selector.json"))
    parser.add_argument("--shortlist", type=Path, default=Path("data/generated/public/candidate-selector-shortlist.md"))
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args()

    as_of = parse_as_of(args.as_of)
    rows, source_status = build_all_candidate_sources(
        current_status=args.current_status,
        research_root=args.research_root,
        owner_picks=args.owner_picks,
        news_theme=args.news_theme,
        earnings_change=args.earnings_change,
        quant_valuation=args.quant_valuation,
        as_of=as_of,
    )
    result = build_selector(rows, config=load_config(args.config), as_of=as_of)
    result["source_status"] = source_status
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.shortlist.parent.mkdir(parents=True, exist_ok=True)
    args.shortlist.write_text(render_shortlist(result, top_n=max(1, args.top_n)), encoding="utf-8")
    print(f"Candidate sources: {len(rows)} records -> {len(result['candidates'])} canonical candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
