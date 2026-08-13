from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping

from build_site import ROOT, SITE, front_matter, write
from scripts.intraday_review_candidate import project_review_candidate

SNAPSHOT_PATH = ROOT / "data" / "generated" / "intraday-market" / "latest.json"
OUTPUT_PATH = SITE / "market" / "intraday" / "index.md"
FIELD_LABELS = {
    "indices.nikkei225": "Nikkei 225",
    "indices.topix": "TOPIX",
    "indices.growth250": "Growth 250",
    "macro.usdjpy": "USD/JPY",
    "macro.vix": "VIX",
    "macro.us10y": "US 10Y",
    "macro.wti": "WTI",
}


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _delta_rows(delta: Mapping[str, Any] | None) -> list[tuple[str, Mapping[str, Any]]]:
    if not isinstance(delta, Mapping):
        return []
    fields = delta.get("fields")
    if not isinstance(fields, Mapping):
        return []
    rows: list[tuple[str, Mapping[str, Any]]] = []
    for key, value in fields.items():
        if isinstance(key, str) and isinstance(value, Mapping):
            rows.append((key, value))
    return rows


def _format_number(value: Any) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "—"
    magnitude = abs(float(value))
    if magnitude >= 1000:
        return f"{float(value):,.1f}"
    if magnitude >= 100:
        return f"{float(value):,.2f}"
    return f"{float(value):,.3f}".rstrip("0").rstrip(".")


def _format_pct(value: Any) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "—"
    return f"{float(value):+.2f}%"


def _render_delta_cards(delta: Mapping[str, Any] | None, limit: int = 4) -> str:
    rows = _delta_rows(delta)
    if not rows:
        return '<div class="codex-alert" data-state="unavailable"><strong>比較基準を取得できません</strong><p>差分を0として補完せず、基準snapshotが揃うまで未取得として表示します。</p></div>'
    ranked = sorted(
        rows,
        key=lambda row: abs(float(row[1].get("pct"))) if isinstance(row[1].get("pct"), (int, float)) else -1.0,
        reverse=True,
    )[:limit]
    cards: list[str] = []
    for key, values in ranked:
        label = FIELD_LABELS.get(key, key.replace("indices.", "").replace("macro.", ""))
        cards.append(
            '<article class="codex-summary-card">'
            f'<h3>{_escape(label)}</h3>'
            f'<p><strong>{_format_pct(values.get("pct"))}</strong> Morning→Current</p>'
            f'<p>{_format_number(values.get("before"))} → {_format_number(values.get("current"))}</p>'
            '</article>'
        )
    return '<div class="codex-summary-grid">' + "".join(cards) + "</div>"


def render_page(snapshot: Mapping[str, Any] | None) -> str:
    page = front_matter(
        "Intraday Market",
        "場中のMarket freshnessとMorningからの変化をread-onlyで確認する",
        "/market/intraday/",
    )
    page += '<link rel="stylesheet" href="{{ \'/assets/design-system.css\' | relative_url }}">\n\n'
    page += '<div class="codex-page-shell">\n'
    page += '<header class="codex-page-header"><p class="eyebrow">INTRADAY MARKET</p><h1>朝から何が変わったか</h1><p class="lead">現在値の羅列ではなく、freshness → Morning→Current delta → Review Requiredの順で確認します。</p></header>\n'

    if not isinstance(snapshot, Mapping):
        page += '<section><div class="codex-alert" data-state="unavailable"><strong>Market freshness: MISSING</strong><p>Intraday snapshotがまだありません。未取得を正常・最新とは扱いません。</p></div></section>\n</div>\n'
        return page

    candidate = project_review_candidate(snapshot)
    status = snapshot.get("source_status") or "MISSING"
    slot = snapshot.get("session_slot") or "UNKNOWN"
    observed_at = snapshot.get("observed_at") or "unknown"
    source_timestamp = snapshot.get("source_timestamp") or "unknown"
    blocked = status != "OK"
    state = "unavailable" if blocked else "normal"

    page += '<section aria-labelledby="freshness-title"><p class="eyebrow">FRESHNESS</p><h2 id="freshness-title">Market freshness</h2>'
    page += f'<div class="codex-alert" data-state="{state}"><strong>{_escape(slot)} · {_escape(status)}</strong><p>Observed: {_escape(observed_at)}<br>Source: {_escape(source_timestamp)}</p></div></section>\n'

    page += '<section aria-labelledby="morning-delta-title"><p class="eyebrow">MORNING → CURRENT</p><h2 id="morning-delta-title">朝からの主要変化</h2>'
    if blocked:
        page += '<div class="codex-alert" data-state="unavailable"><strong>差分表示をブロックしています</strong><p>STALE / PARTIAL / MISSINGをfreshな市場変化として見せません。</p></div>'
    else:
        page += _render_delta_cards(snapshot.get("delta_from_morning"))
    page += '</section>\n'

    page += '<section aria-labelledby="review-title"><p class="eyebrow">REVIEW REQUIRED</p><h2 id="review-title">判断前提の再確認</h2>'
    review_state = candidate["state"]
    review_required = "YES" if candidate["review_required"] else "NO"
    page += f'<div class="codex-alert" data-state="{"warning" if candidate["review_required"] else state}"><strong>Review Required: {review_required}</strong><p>State: {_escape(review_state)}</p>'
    reasons = candidate.get("review_reasons") or []
    if reasons:
        page += '<ul>' + ''.join(f'<li>{_escape(reason)}</li>' for reason in reasons) + '</ul>'
    elif blocked:
        page += '<p>データ品質がOKではないため、review signalへ昇格しません。</p>'
    else:
        page += '<p>明示されたMeaningful Delta reasonはありません。</p>'
    page += '</div><p>これはBUY / SELL / HOLDの推奨ではありません。Portfolio / Research / Hypothesisを変更しません。</p></section>\n'

    page += '<details class="codex-disclosure"><summary>Previous → Current と詳細</summary><div class="codex-disclosure__body">'
    page += _render_delta_cards(snapshot.get("delta_from_previous"), limit=8)
    page += '</div></details>\n</div>\n'
    return page


def load_snapshot(path: Path = SNAPSHOT_PATH) -> Mapping[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, Mapping) else None


def main() -> None:
    write(OUTPUT_PATH, render_page(load_snapshot()))


if __name__ == "__main__":
    main()
