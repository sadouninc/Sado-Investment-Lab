from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
SITE_HOME = ROOT / "site-src" / "index.md"
MORNING_DATASET = ROOT / "data" / "generated" / "public" / "morning-dataset.json"
MORNING_DIAGNOSTICS_ROUTE = "/research/morning-dataset/"
MAP_MARKER = '  <section class="home-os-section" aria-labelledby="map-title">'
FOCUS_MARKER = '  <section class="home-os-section home-today-focus" aria-labelledby="today-focus-title">'

STATUS_LABELS = {
    "OK": ("normal", "確認可能"),
    "PARTIAL": ("caution", "一部情報不足"),
    "STALE": ("stale", "情報が古い"),
    "MISSING": ("unavailable", "取得できません"),
}


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _source_status(dataset: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    for row in dataset.get("source_status") or []:
        if isinstance(row, Mapping) and row.get("name") == name:
            return row
    return {"name": name, "status": "MISSING", "reason": "source status not available"}


def project_today_focus(dataset: Mapping[str, Any] | None) -> dict[str, Any]:
    """Read-only Home projection. Preserve Current Focus order; never invent ranking."""
    if not isinstance(dataset, Mapping):
        return {"status": "MISSING", "as_of": None, "items": [], "reason": "Morning Datasetを取得できません"}

    source = _source_status(dataset, "watchlist")
    status = str(source.get("status") or "MISSING").upper()
    payload = dataset.get("watchlist") if isinstance(dataset.get("watchlist"), Mapping) else {}
    raw_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    items: list[dict[str, Any]] = []
    for row in raw_items[:3]:
        if not isinstance(row, Mapping):
            continue
        text = row.get("text") or row.get("reason")
        if text:
            items.append({"text": str(text), "reason": str(row.get("reason") or text)})

    reason = source.get("reason")
    if not items and not reason:
        reason = "Current Focusに表示可能な項目がありません"
    return {
        "status": status,
        "as_of": source.get("as_of"),
        "items": items,
        "reason": reason,
    }


def render_today_focus(dataset: Mapping[str, Any] | None) -> str:
    projection = project_today_focus(dataset)
    status = projection["status"]
    token, label = STATUS_LABELS.get(status, ("unknown", "状態不明"))
    as_of = projection.get("as_of") or "時点不明"
    items = projection.get("items") or []

    if not items:
        return f'''{FOCUS_MARKER}
    <p class="eyebrow">TODAY FOCUS</p>
    <h2 id="today-focus-title">では今日何を見る？</h2>
    <div class="codex-alert" data-state="unavailable">
      <strong>今日見る項目を取得できません / {status}</strong>
      <p>{_e(projection.get('reason') or 'Canonical Current Focusが未接続です。')}</p>
    </div>
    <div class="codex-evidence">
      <a href="{{{{ '{MORNING_DIAGNOSTICS_ROUTE}' | relative_url }}}}">Morning Datasetの状態を確認する</a>
    </div>
  </section>

'''

    cards = []
    for index, item in enumerate(items, start=1):
        cards.append(
            '<article class="codex-summary-card">'
            f'<span class="codex-status-chip" data-state="{token}">{_e(label)} / {_e(status)}</span>'
            f'<p class="eyebrow">FOCUS {index}</p>'
            f'<h3>{_e(item["text"])}</h3>'
            f'<p>なぜ見る: {_e(item["reason"])}</p>'
            f'<p class="codex-evidence__meta">Current Focus as of: {_e(as_of)}</p>'
            f'<a href="{{{{ \'{MORNING_DIAGNOSTICS_ROUTE}\' | relative_url }}}}" aria-label="{_e(item["text"])}の根拠をMorning Datasetで確認する">根拠・鮮度を確認する</a>'
            '</article>'
        )
    cards_html = "\n".join(cards)
    stale_note = (
        '<div class="codex-alert" data-state="stale"><strong>Current Focusは古い情報です</strong>'
        '<p>STALEを現在の優先順位へ昇格せず、記録された順序のまま参考表示します。</p></div>'
        if status == "STALE" else ""
    )
    return f'''{FOCUS_MARKER}
    <p class="eyebrow">TODAY FOCUS</p>
    <h2 id="today-focus-title">では今日何を見る？</h2>
    <p>Canonical Current Focusの先頭最大3件を、記録順のまま表示します。Home独自のscore・ranking・BUY/SELLは生成しません。</p>
    {stale_note}
    <div class="summary-grid home-today-focus-grid">
{cards_html}
    </div>
  </section>

'''


def enrich_home_focus(dataset: Mapping[str, Any] | None = None, *, home_path: Path = SITE_HOME) -> None:
    if not home_path.is_file():
        return
    if dataset is None:
        try:
            loaded = json.loads(MORNING_DATASET.read_text(encoding="utf-8"))
            dataset = loaded if isinstance(loaded, Mapping) else None
        except (OSError, json.JSONDecodeError):
            dataset = None

    text = home_path.read_text(encoding="utf-8")
    if FOCUS_MARKER in text:
        return
    if MAP_MARKER not in text:
        raise RuntimeError("#312 Slice C: Home map marker is missing")
    text = text.replace(MAP_MARKER, render_today_focus(dataset) + MAP_MARKER, 1)
    home_path.write_text(text, encoding="utf-8")
