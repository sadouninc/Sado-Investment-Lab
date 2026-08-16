from __future__ import annotations

import json
from pathlib import Path
import shutil

from build_intraday_market import main as build_intraday_market

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "data" / "generated" / "public" / "morning-dataset.json"
SITE = ROOT / "site-src" / "research" / "morning-dataset"


def esc(value: object) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.1%}" if 0 <= value <= 1 else f"{value:,.2f}"
    return esc(value)


def status_badge(status: object) -> str:
    normalized = str(status or "MISSING").upper()
    return f'<span class="status-badge status-{normalized.lower()}">{esc(normalized)}</span>'


def compact_value(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return fmt(value)
    if isinstance(value, (str, int)):
        return esc(value)
    if isinstance(value, list):
        return f"{len(value)} items"
    if isinstance(value, dict):
        return f"{len(value)} fields"
    return esc(value)


def section_summary(key: str, value: object) -> list[tuple[str, str]]:
    if value is None:
        return [("Data", "MISSING")]
    if isinstance(value, list):
        return [("Items", str(len(value)))]
    if not isinstance(value, dict):
        return [("Value", compact_value(value))]

    preferred_keys = {
        "market": ("phase", "risk_state", "indices", "breadth", "sentiment"),
        "portfolio": ("positions", "exposure", "pnl", "updated_at", "as_of"),
        "capital": ("cash_available", "buying_power", "margin_usage", "target_reserve", "capital_state"),
        "investor_dna": (
            "sample_count",
            "trade_count",
            "win_rate",
            "profit_factor",
            "native_dna",
            "environment_fit",
            "style_drift",
            "risk_patterns",
            "updated_at",
            "as_of",
        ),
        "events": ("earnings", "economic", "company", "today", "upcoming"),
    }
    rows: list[tuple[str, str]] = []
    for field in preferred_keys.get(key, ()):
        if field in value:
            rows.append((field, compact_value(value.get(field))))
        if len(rows) >= 6:
            break

    if not rows:
        for field, field_value in list(value.items())[:5]:
            rows.append((str(field), compact_value(field_value)))

    rows.append(("Available fields", str(len(value))))
    return rows


def raw_details(key: str, value: object) -> str:
    rendered = json.dumps(value, ensure_ascii=False, indent=2)
    return (
        f'<details class="raw-json-details"><summary>Raw JSONを見る — {esc(key)}</summary>'
        f'<pre><code>{esc(rendered)}</code></pre></details>\n\n'
    )


def build_page(payload: dict) -> str:
    quality = payload.get("data_quality") or {}
    sources = payload.get("source_status") or []
    warnings = payload.get("warnings") or []

    ok_sources = quality.get("ok_sources", quality.get("available_sources", 0))
    total_sources = quality.get("total_sources", len(sources))
    completeness_label = quality.get("completeness_label") or f"{ok_sources} / {total_sources}"
    completeness_percent = fmt(quality.get("completeness"))
    source_counts = quality.get("source_counts") or {}

    page = """---
layout: site
title: Morning Dataset Diagnostics
description: AI判断前にGitHub Actions / Pythonが準備したFact・Featureの状態を確認する
permalink: /research/morning-dataset/
---

<p class="breadcrumb"><a href="{{ '/' | relative_url }}">Home</a> / Research / Morning Dataset</p>

# Morning Dataset Diagnostics

このページは **AIが判断を始める前の入力データ** を確認するためのDiagnosticsです。
ここでは銘柄の推奨・優先順位付け・売買判断は行いません。

> Data / Feature preparation → Morning Dataset → AI reasoning → Human decision

"""
    page += (
        '<div class="metric-grid">'
        f'<div class="metric-card"><span>Schema</span><strong>{esc(payload.get("schema_version", "—"))}</strong></div>'
        f'<div class="metric-card"><span>As of</span><strong>{esc(payload.get("as_of", "—"))}</strong></div>'
        f'<div class="metric-card"><span>Quality</span><strong>{esc(quality.get("status", "—"))}</strong></div>'
        '<div class="metric-card"><span>Completeness</span>'
        f'<strong>{esc(completeness_label)} sources</strong>'
        f'<small> · {completeness_percent}</small></div>'
        '</div>\n\n'
    )

    page += (
        "<p><strong>Source counts:</strong> "
        f"OK {source_counts.get('OK', 0)} / "
        f"PARTIAL {source_counts.get('PARTIAL', 0)} / "
        f"STALE {source_counts.get('STALE', 0)} / "
        f"MISSING {source_counts.get('MISSING', 0)}</p>\n\n"
    )

    page += "## Source Status\n\n"
    page += "| Source | Status | As of | Source reference | Reason |\n|---|---|---|---|---|\n"
    for row in sources:
        source_reference = row.get("source_reference") or row.get("source") or "—"
        page += (
            f'| {esc(row.get("name", "—"))} | {status_badge(row.get("status"))} | '
            f'{esc(row.get("as_of") or "—")} | {esc(source_reference)} | '
            f'{esc(row.get("reason") or "—")} |\n'
        )

    page += (
        "\n`OK` は当日判断に利用可能、`PARTIAL` は一部不足、`STALE` は値はあるが鮮度不足、"
        "`MISSING` は利用可能な入力がない状態です。Completeness は **OK のソース数 / 全7ソース** で計算します。\n\n"
    )

    page += "## Warnings\n\n"
    if warnings:
        for warning in warnings:
            page += f"- {esc(warning)}\n"
    else:
        page += "- なし\n"

    page += "\n## Source Summaries\n\n"
    page += "日次確認では要約を先に表示します。検証・デバッグ時だけ各セクションの Raw JSON を展開してください。\n\n"
    sections = ("market", "portfolio", "capital", "candidates", "investor_dna", "events", "watchlist")
    status_by_name = {row.get("name"): row.get("status") for row in sources}
    source_by_name = {row.get("name"): row for row in sources}
    for key in sections:
        value = payload.get(key)
        source_row = source_by_name.get(key) or {}
        section_status = status_by_name.get(key, "MISSING")
        source_reference = source_row.get("source_reference") or source_row.get("source") or "—"
        page += f"### {key} — {section_status}\n\n"
        page += (
            f"- Status: {section_status}\n"
            f"- As of: {esc(source_row.get('as_of') or '—')}\n"
            f"- Source: {esc(source_reference)}\n"
            f"- Reason: {esc(source_row.get('reason') or '—')}\n"
        )
        for label, summary_value in section_summary(key, value):
            page += f"- {esc(label)}: {summary_value}\n"
        page += "\n"
        if value is not None:
            page += raw_details(key, value)

    page += (
        "## Public JSON\n\n"
        "AI入力契約そのものは [`morning-dataset.json`](./morning-dataset.json) で確認できます。\n\n"
        "不足データは0や推測値で補完せず、`null` / `MISSING` / `PARTIAL` / `STALE` として残します。\n"
    )
    return page


def main() -> None:
    if not REPORT.is_file():
        print(f"WARNING: Morning Dataset not found at {REPORT}")
        print("Skipping Morning Dataset page generation - file will be created by ai-morning-analyst workflow")
        return
    
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    
    # Guard against Issue #334 regression: reject investor-DNA-only datasets
    source_status = payload.get("source_status") or []
    source_map = {s.get("name"): s.get("status") for s in source_status}
    
    provider_names = ["market", "portfolio", "capital", "candidates", "events", "watchlist", "sector_rotation"]
    ok_providers = [n for n in provider_names if source_map.get(n) in ("OK", "PARTIAL")]
    dna_ok = source_map.get("investor_dna") in ("OK", "PARTIAL")
    
    if dna_ok and not ok_providers:
        msg = (
            "Refusing to publish investor-DNA-only Morning Dataset.\n"
            "This would regress all provider sources to MISSING on Pages.\n"
            "Expected: canonical dataset from ai-morning-analyst.yml with multiple providers.\n"
            f"Found: investor_dna={source_map.get('investor_dna')}, providers with OK/PARTIAL={len(ok_providers)}\n"
            "Fix: Do not regenerate morning-dataset.json in publish-site.yml - use existing canonical file.\n"
            "See Issue #334."
        )
        raise ValueError(msg)
    
    quality = payload.get("data_quality", {})
    print(f"Morning Dataset OK: {quality.get('ok_sources', 0)}/{quality.get('total_sources', 8)} sources, "
          f"status={quality.get('status')}")
    if not ok_providers and not dna_ok:
        print("WARNING: All sources are MISSING or STALE")
    
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "index.md").write_text(build_page(payload), encoding="utf-8")
    shutil.copyfile(REPORT, SITE / "morning-dataset.json")
    build_intraday_market()


if __name__ == "__main__":
    main()
