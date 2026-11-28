#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import date, datetime
import hashlib
import json
import math
import os
import re
from pathlib import Path
import sys
import time
from typing import Any
from urllib import request, error

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.morning_dataset.context_optimizer import optimize_dataset

API_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5")

SYSTEM_PROMPT = """You are the AI Morning Analyst for Sado Investment Lab.
Use only the supplied optimized Morning Dataset as factual input.
Never invent missing market data, prices, events, portfolio facts, or news.
Clearly distinguish facts from interpretation.
If data quality is PARTIAL, MISSING, or STALE, say so prominently.
Do not place orders and do not present output as guaranteed investment advice.
Write concise Japanese Markdown with these sections exactly:
# AI Morning Report
## データ品質
## 市場概況
## 前日の重要ポイント
## 今日の注目イベント
## 保有株へ影響しそうなテーマ
## リスク要因
## 今日の戦略
## 注目銘柄
## 次回確認時に見る条件
For sections unsupported by the dataset, write 「データ不足のため判断保留」.
For ## 注目銘柄, use candidate-specific source_status and each candidate's status,
total_priority, rank, and last_researched_at. A freshly generated candidate
snapshot or an OK provider status does not prove an individual company is fresh.
Never treat historical portfolio holdings, stale company research, or a null rank
or total_priority as today's verified stock pick, current holding, or top rank.
If there is no candidate with a finite numeric total_priority AND current
independently dated evidence, say 「今日の検証済み注目銘柄は未確定」 and
identify which dated evidence is missing; do not promote an arbitrary row.
Do not interpret a theme name or 4-digit calendar year as a tradable ticker.
Keep historical notes labelled as history, never silently rewrite them.
"""


def extract_output_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(content["text"])
    text = "\n".join(parts).strip()
    if not text:
        raise RuntimeError("OpenAI response did not contain output_text")
    return text


def call_openai(dataset: dict[str, Any], *, model: str, api_key: str, timeout: int = 120) -> tuple[str, dict[str, Any], float]:
    user_input = (
        "Analyze the following optimized Morning Dataset JSON. Preserve null/MISSING/PARTIAL as uncertainty.\n\n"
        + json.dumps(dataset, ensure_ascii=False, separators=(",", ":"))
    )
    body = {
        "model": model,
        "instructions": SYSTEM_PROMPT,
        "input": user_input,
    }
    req = request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started = time.monotonic()
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API HTTP {exc.code}: {detail[:1000]}") from exc
    elapsed = time.monotonic() - started
    return extract_output_text(raw), raw, elapsed


def estimate_cost(usage: dict[str, Any]) -> tuple[float | None, str]:
    input_rate = os.environ.get("OPENAI_INPUT_COST_PER_MILLION")
    output_rate = os.environ.get("OPENAI_OUTPUT_COST_PER_MILLION")
    if not input_rate or not output_rate:
        return None, "pricing_not_configured"
    try:
        cost = (
            float(usage.get("input_tokens", 0)) * float(input_rate)
            + float(usage.get("output_tokens", 0)) * float(output_rate)
        ) / 1_000_000
    except (TypeError, ValueError):
        return None, "pricing_invalid"
    return round(cost, 6), "estimated_from_repository_variables"


def _finite_number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:  # integers too large to convert to float
        return False


def _positive_integer_rank(value: Any) -> bool:
    """Rank must be a positive whole number (same rule as #951's static audit)."""
    return _finite_number(value) and value > 0 and value == int(value)


# JPX securities codes: 4 characters, digits with optional letters in the 2nd
# and 4th positions for new-format codes (e.g. 6622, 278A).
SECURITY_CODE_RE = re.compile(r"^[0-9][0-9A-Z][0-9][0-9A-Z]$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _iso_date(value: Any) -> date | None:
    """Strict calendar date: exactly ``YYYY-MM-DD`` (no prefixes, times or suffixes)."""
    if not isinstance(value, str) or not _ISO_DATE_RE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _row_code(row: dict[str, Any]) -> str | None:
    code = row.get("security_code")
    if not isinstance(code, str) or not SECURITY_CODE_RE.fullmatch(code.strip()):
        return None
    return code.strip()


def _row_name(row: dict[str, Any]) -> str | None:
    name = row.get("company_name")
    if not isinstance(name, str) or not name.strip():
        return None
    return " ".join(name.split())


def _verified_row_code(row: dict[str, Any], as_of: date | None) -> str | None:
    """Return the security code only if this row is independently verified.

    Same row contract as #951's ``_verified_candidate``: a well-formed code, a
    non-empty company name, upstream research status exactly ``CURRENT`` (the
    Candidate Selector freshness contract), a finite total_priority, a positive
    integer rank and a strict ``YYYY-MM-DD`` last_researched_at that is not after
    the dataset date.
    """
    code = _row_code(row)
    if code is None or _row_name(row) is None:
        return None
    if row.get("status") != "CURRENT":
        return None
    if not (_finite_number(row.get("total_priority")) and _positive_integer_rank(row.get("rank"))):
        return None
    researched = _iso_date(row.get("last_researched_at"))
    if as_of is None or researched is None or researched > as_of:
        return None
    return code


def candidate_focus_verification(dataset: Any) -> dict[str, Any]:
    """Deterministically record which securities the dataset verifies as focus.

    Renderers show a verified focus only from ``verified_candidates`` for the same
    ``as_of``; AI prose is never identity evidence. Any malformed payload, non-OK
    candidate source or unverified row fails closed, while other well-formed rows
    are kept. A security code that appears with different company names is
    ambiguous and is never verified; an identical code/name pair is shown once.
    """
    dataset = dataset if isinstance(dataset, dict) else {}
    as_of = _iso_date(dataset.get("as_of"))
    statuses = dataset.get("source_status")
    statuses = statuses if isinstance(statuses, list) else []
    source = next(
        (row for row in statuses if isinstance(row, dict) and row.get("name") == "candidates"),
        {},
    )
    source_status = source.get("status") if isinstance(source.get("status"), str) else "UNKNOWN"
    rows = dataset.get("candidates")
    rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    scored = [row for row in rows if _finite_number(row.get("total_priority")) and _positive_integer_rank(row.get("rank"))]

    names_by_code: dict[str, set[str]] = {}
    for row in rows:
        code, name = _row_code(row), _row_name(row)
        if code is not None and name is not None:
            names_by_code.setdefault(code, set()).add(name)
    conflicting = sorted(code for code, names in names_by_code.items() if len(names) > 1)

    pairs: dict[str, str] = {}
    for row in rows:
        code = _verified_row_code(row, as_of)
        if code is not None and code not in conflicting:
            pairs[code] = _row_name(row)  # identical pairs collapse to one entry
    if source_status != "OK":
        pairs = {}
    codes = sorted(pairs)
    verified = bool(codes)
    if verified:
        reason = None
    elif as_of is None:
        reason = "データの基準日（as_of）を確認できません"
    elif not rows:
        reason = "候補データがありません"
    elif source_status != "OK":
        reason = f"候補データの状態が {source_status} です"
    elif not scored:
        reason = "優先度を算出できた候補がありません"
    else:
        reason = "優先度のある候補の根拠がすべて古いか、日付・銘柄コード・会社名を確認できません"
    return {
        "as_of": as_of.isoformat() if as_of else None,
        "verified_focus_available": verified,
        "verified_security_codes": codes,
        # Canonical code/name pairs: the only identity a renderer may show as a
        # verified focus. AI watch prose is never used as identity evidence.
        "verified_candidates": [{"security_code": code, "company_name": pairs[code]} for code in codes],
        "conflicting_security_codes": conflicting,
        "candidate_source_status": source_status,
        "candidate_source_as_of": source.get("as_of"),
        "candidate_count": len(rows),
        "scored_count": len(scored),
        "verified_count": len(codes),
        "reason": reason,
    }


def render_report(ai_markdown: str, dataset: dict[str, Any], model: str) -> str:
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    quality = dataset.get("data_quality", {})
    meta = (
        "---\n"
        f"generated_at: {generated_at}\n"
        f"dataset_as_of: {dataset.get('as_of')}\n"
        f"dataset_status: {quality.get('status')}\n"
        f"model: {model}\n"
        "source: OpenAI Responses API + optimized Morning Dataset\n"
        "---\n\n"
    )
    return meta + ai_markdown.strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AI Morning Report from Morning Dataset")
    parser.add_argument("--input", default="data/generated/public/morning-dataset.json")
    parser.add_argument("--report-dir", default="05_Daily_Reports/Morning")
    parser.add_argument("--diagnostics-dir", default="data/generated/diagnostics/openai")
    parser.add_argument("--optimized-output", default="data/generated/diagnostics/openai/optimized-morning-dataset.json")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not configured")

    input_path = Path(args.input)
    dataset = json.loads(input_path.read_text(encoding="utf-8"))
    dataset_bytes = input_path.read_bytes()
    optimized, optimization = optimize_dataset(dataset)
    if optimization["status"] != "OK":
        raise RuntimeError("Context optimizer could not reduce the Morning Dataset below the hard cap")

    optimized_path = Path(args.optimized_output)
    optimized_path.parent.mkdir(parents=True, exist_ok=True)
    optimized_path.write_text(json.dumps(optimized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report_text, response, elapsed = call_openai(optimized, model=args.model, api_key=api_key)

    day = str(dataset.get("as_of") or datetime.now().astimezone().date())
    report_path = Path(args.report_dir) / f"{day}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(report_text, dataset, args.model), encoding="utf-8")

    usage = response.get("usage") or {}
    estimated_cost, cost_basis = estimate_cost(usage)
    diagnostics = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "dataset_as_of": dataset.get("as_of"),
        "dataset_schema_version": dataset.get("schema_version"),
        "dataset_status": (dataset.get("data_quality") or {}).get("status"),
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "model": response.get("model", args.model),
        "response_id": response.get("id"),
        "execution_seconds": round(elapsed, 3),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "estimated_cost_usd": estimated_cost,
        "cost_basis": cost_basis,
        "context_optimization": optimization,
        "candidate_focus": candidate_focus_verification(dataset),
        "optimized_dataset_path": str(optimized_path),
        "report_path": str(report_path),
        "status": "OK",
    }
    diagnostics_path = Path(args.diagnostics_dir) / f"{day}.json"
    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_path.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"AI Morning Report: {report_path}")
    print(f"Diagnostics: {diagnostics_path}")
    print(
        "Context: "
        f"{optimization['raw_dataset_chars']} -> {optimization['optimized_prompt_chars']} chars "
        f"({optimization['reduction_ratio']:.1%} reduction; ~{optimization['estimated_input_tokens']} tokens)"
    )
    print(f"Model: {diagnostics['model']}; tokens: {diagnostics['total_tokens']}")


if __name__ == "__main__":
    main()
