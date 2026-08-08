from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from scripts.candidate_selector import build_selector, load_config, parse_as_of
from scripts.morning_dataset.providers import PortfolioProvider, WatchlistProvider

DATE_PATTERNS = (
    re.compile(r"(?:最終更新|更新日|as_of|updated(?:_at)?)\s*[:：]\s*(20\d{2}-\d{2}-\d{2})", re.IGNORECASE),
    re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b"),
)
CODE_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def _empty_signals() -> dict[str, None]:
    return {
        "investment_relevance": None,
        "change_signal": None,
        "research_gap": None,
        "theme_relevance": None,
        "valuation_interest": None,
    }


def _empty_signal_reasons() -> dict[str, list[str]]:
    return {key: [] for key in _empty_signals()}


def candidate_record(
    *,
    company_name: str,
    security_code: str | None,
    source: str,
    reason: str,
    research_status: str = "NOT_STARTED",
    last_researched_at: str | None = None,
    owner_pick: bool = False,
    owner_pick_note: str | None = None,
) -> dict[str, Any]:
    return {
        "security_code": security_code,
        "company_name": company_name,
        "candidate_sources": [source],
        "source_reasons": {source: [reason]},
        "owner_pick": owner_pick,
        "owner_pick_note": owner_pick_note,
        "signals": _empty_signals(),
        "signal_reasons": _empty_signal_reasons(),
        "research_status": research_status,
        "last_researched_at": last_researched_at,
        "updated_at": None,
    }


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", value)
    text = re.sub(r"[（(]\s*\d{4}\s*[)）]", "", text)
    text = re.sub(r"\s+", "", text)
    return text.strip()


def _title_from_markdown(path: Path, text: str) -> str:
    match = H1_RE.search(text)
    if match:
        title = match.group(1).strip()
        title = re.sub(r"^[🏢📊📈🔬]+\s*", "", title)
        return re.sub(r"[（(]\s*\d{4}\s*[)）].*$", "", title).strip()
    stem = path.stem
    stem = re.sub(r"^\d{4}[-_]", "", stem)
    return stem.replace("_", " ").replace("-", " ").strip()


def _research_date(text: str) -> str | None:
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def research_index_candidates(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not root.is_dir():
        return rows
    for path in sorted(root.glob("*/*.md")):
        if path.name.lower() == "readme.md":
            continue
        text = path.read_text(encoding="utf-8")
        code_match = CODE_RE.search(path.stem) or CODE_RE.search(text[:500])
        code = code_match.group(1) if code_match else None
        name = _title_from_markdown(path, text)
        researched_at = _research_date(text)
        status = "CURRENT" if researched_at else "STALE"
        reason = f"Company Research exists: {path.as_posix()}"
        if not researched_at:
            reason += " (freshness date unavailable)"
        rows.append(
            candidate_record(
                company_name=name,
                security_code=code,
                source="RESEARCH_INDEX",
                reason=reason,
                research_status=status,
                last_researched_at=researched_at,
            )
        )
    return rows


def research_name_map(rows: Iterable[dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    ambiguous: set[str] = set()
    for row in rows:
        code = row.get("security_code")
        if not code:
            continue
        key = normalize_name(str(row.get("company_name") or ""))
        if not key:
            continue
        if key in mapping and mapping[key] != code:
            ambiguous.add(key)
        else:
            mapping[key] = str(code)
    for key in ambiguous:
        mapping.pop(key, None)
    return mapping


def _resolve_code(name: str, mapping: dict[str, str]) -> str | None:
    return mapping.get(normalize_name(name))


def _provider_status(result: Any, count: int) -> dict[str, Any]:
    payload = result.metadata()
    payload["count"] = count
    return payload


def portfolio_candidates(path: Path, *, as_of: date, code_map: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    result = PortfolioProvider(path=path, today=as_of).collect()
    rows: list[dict[str, Any]] = []
    data = result.data or {}
    for position in data.get("positions") or []:
        name = str(position.get("name") or "").strip()
        if not name:
            continue
        code = position.get("security_code") or _resolve_code(name, code_map)
        details = str(position.get("details") or "").strip()
        reason = "Current portfolio holding" + (f" ({details})" if details else "")
        rows.append(
            candidate_record(
                company_name=name,
                security_code=str(code) if code else None,
                source="PORTFOLIO",
                reason=reason,
            )
        )
    return rows, _provider_status(result, len(rows))


def watchlist_candidates(path: Path, *, as_of: date, code_map: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    result = WatchlistProvider(path=path, today=as_of).collect()
    rows: list[dict[str, Any]] = []
    data = result.data or {}
    for item in data.get("items") or []:
        explicit_name = str(item.get("name") or "").strip()
        text = str(item.get("text") or item.get("reason") or "").strip()
        name = explicit_name or text
        if not name:
            continue
        code = item.get("security_code") or _resolve_code(name, code_map)
        rows.append(
            candidate_record(
                company_name=name,
                security_code=str(code) if code else None,
                source="WATCHLIST",
                reason=str(item.get("reason") or text),
            )
        )
    return rows, _provider_status(result, len(rows))


def load_owner_picks(path: Path | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if path is None or not path.is_file():
        return [], {"status": "MISSING", "source_reference": str(path) if path else None, "reason": "owner-pick source not configured", "count": 0}
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("owner_picks") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError("owner-pick source must be a list or an object with owner_picks list")
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("each owner pick must be an object")
        name = str(item.get("company_name") or "").strip()
        if not name:
            raise ValueError("owner pick company_name is required")
        rows.append(
            candidate_record(
                company_name=name,
                security_code=str(item["security_code"]).strip() if item.get("security_code") else None,
                source="OWNER_PICK",
                reason=str(item.get("reason") or "Explicit Owner Pick"),
                owner_pick=True,
                owner_pick_note=str(item.get("note") or item.get("reason") or "").strip() or None,
            )
        )
    return rows, {"status": "OK", "source_reference": str(path), "reason": None, "count": len(rows)}


def build_source_candidates(
    *,
    current_status: Path,
    research_root: Path,
    owner_picks: Path | None,
    as_of: date,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    research_rows = research_index_candidates(research_root)
    code_map = research_name_map(research_rows)
    portfolio_rows, portfolio_status = portfolio_candidates(current_status, as_of=as_of, code_map=code_map)
    watchlist_rows, watchlist_status = watchlist_candidates(current_status, as_of=as_of, code_map=code_map)
    owner_rows, owner_status = load_owner_picks(owner_picks)
    rows = [*owner_rows, *portfolio_rows, *watchlist_rows, *research_rows]
    status = {
        "OWNER_PICK": owner_status,
        "PORTFOLIO": portfolio_status,
        "WATCHLIST": watchlist_status,
        "RESEARCH_INDEX": {
            "status": "OK" if research_root.is_dir() else "MISSING",
            "source_reference": str(research_root),
            "reason": None if research_root.is_dir() else "company research directory not found",
            "count": len(research_rows),
        },
    }
    return rows, status


def render_shortlist(result: dict[str, Any], *, top_n: int) -> str:
    lines = ["# Research Candidate Shortlist", "", f"> as_of: {result['as_of']}", ""]
    lines += ["## Owner Picks", ""]
    owner_picks = result.get("owner_picks") or []
    if owner_picks:
        for row in owner_picks:
            code = f" ({row['security_code']})" if row.get("security_code") else ""
            lines.append(f"- {row['company_name']}{code} — {row['selection_reason']}")
    else:
        lines.append("- なし")
    lines += ["", f"## Ranked Candidates Top {top_n}", ""]
    for index, row in enumerate((result.get("ranked_candidates") or [])[:top_n], start=1):
        code = f" ({row['security_code']})" if row.get("security_code") else ""
        priority = "N/A" if row.get("total_priority") is None else f"{row['total_priority']:.2f}"
        lines.append(f"{index}. {row['company_name']}{code} — priority {priority} — {row['selection_reason']}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build #108 candidate inputs from repository SSoT sources")
    parser.add_argument("--current-status", type=Path, default=Path("Current_Status.md"))
    parser.add_argument("--research-root", type=Path, default=Path("03_Companies"))
    parser.add_argument("--owner-picks", type=Path, default=Path("data/candidates/owner-picks.json"))
    parser.add_argument("--config", type=Path, default=Path("data/config/candidate-selector-v1.json"))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", type=Path, default=Path("data/generated/public/candidate-selector.json"))
    parser.add_argument("--shortlist", type=Path, default=Path("data/generated/public/candidate-selector-shortlist.md"))
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args()

    as_of = parse_as_of(args.as_of)
    rows, source_status = build_source_candidates(
        current_status=args.current_status,
        research_root=args.research_root,
        owner_picks=args.owner_picks,
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
