from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.developing_signal_store import ACTIVE_STATUSES, StoreReadResult, read_store


ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site-src"
OUTPUT = SITE / "research" / "developing-signals" / "index.md"

DIRECTION_LABELS = {
    "STRENGTHENING": "↑ 強まっている",
    "WEAKENING": "↓ 弱まっている",
    "MIXED": "↕ 強弱が混在",
    "UNKNOWN": "? 方向不明",
}


def _front_matter() -> str:
    return """---
layout: site
title: Developing Signals
description: 継続観測すべき未確定Signalの方向・鮮度・次の確認点を追う
permalink: /research/developing-signals/
---

"""


def _age_text(value: str, *, now: datetime) -> str:
    try:
        observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            return "最終観測 UNKNOWN — timezone未設定"
        delta = now.astimezone(timezone.utc) - observed.astimezone(timezone.utc)
        if delta.total_seconds() < 0:
            return "最終観測 UNKNOWN — future timestamp"
        return f"最終観測 {delta.days}日前"
    except (TypeError, ValueError):
        return "最終観測 UNKNOWN"


def _entities(signal: dict[str, Any]) -> str:
    values = []
    for entity in signal.get("related_entities", []):
        kind = str(entity.get("type", "UNKNOWN")).strip() or "UNKNOWN"
        identifier = str(entity.get("id", "UNKNOWN")).strip() or "UNKNOWN"
        values.append(f"{kind}: {identifier}")
    return " / ".join(values) if values else "UNKNOWN"


def _checkpoint(signal: dict[str, Any]) -> str:
    checkpoint = signal.get("next_checkpoint")
    if checkpoint:
        return str(checkpoint)
    reason = signal.get("checkpoint_reason")
    return str(reason) if reason else "UNKNOWN — 次の確認点が未設定"


def _details(signal: dict[str, Any]) -> str:
    observations = signal.get("observations", [])
    observation_items = "\n".join(
        f"<li><strong>{html.escape(str(item.get('observed_at', 'UNKNOWN')))}</strong> — {html.escape(str(item.get('observation', 'UNKNOWN')))}</li>"
        for item in observations
    ) or "<li>Observation history unavailable</li>"
    sources = "\n".join(
        f"<li><code>{html.escape(str(ref))}</code></li>" for ref in signal.get("source_refs", [])
    ) or "<li>Source UNKNOWN</li>"
    return f"""<details class="codex-disclosure">
<summary>観測履歴・Source</summary>
<div class="codex-disclosure__body">
<h4>Observations</h4><ul>{observation_items}</ul>
<h4>Sources</h4><ul>{sources}</ul>
</div>
</details>"""


def _card(signal: dict[str, Any], *, now: datetime) -> str:
    direction = str(signal.get("direction", "UNKNOWN"))
    direction_label = DIRECTION_LABELS.get(direction, f"? {direction}")
    status = str(signal.get("status", "UNKNOWN"))
    return f"""<article class="codex-summary-card developing-signal-card">
<p class="codex-card-question">{html.escape(direction_label)} · {html.escape(status)}</p>
<h3>{html.escape(str(signal.get('title', 'UNKNOWN SIGNAL')))}</h3>
<p>{html.escape(str(signal.get('summary', 'UNKNOWN')))}</p>
<dl>
<dt>なぜ見るか</dt><dd>{html.escape(str(signal.get('why_it_may_matter', 'UNKNOWN')))}</dd>
<dt>関連</dt><dd>{html.escape(_entities(signal))}</dd>
<dt>鮮度</dt><dd>{html.escape(_age_text(str(signal.get('last_observed_at', '')), now=now))} / {html.escape(str(signal.get('last_observed_at', 'UNKNOWN')))}</dd>
<dt>次の確認点</dt><dd>{html.escape(_checkpoint(signal))}</dd>
</dl>
{_details(signal)}
</article>"""


def render(result: StoreReadResult, *, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    active = [signal for signal in result.signals if signal.get("status") in ACTIVE_STATUSES]
    cards = "\n".join(_card(signal, now=now) for signal in active)
    if not cards:
        cards = '<div class="codex-alert" data-state="unknown"><strong>Active WATCHはありません。</strong><p>Signalを推測生成しません。</p></div>'

    diagnostics = ""
    if result.status != "OK":
        diagnostic_text = " / ".join(result.diagnostics) if result.diagnostics else "canonical store unavailable"
        diagnostics = (
            '<div class="codex-alert" data-state="unavailable">'
            f'<strong>Data status: {html.escape(result.status)}</strong>'
            f'<p>{html.escape(diagnostic_text)}。欠損を正常値・negative signalへ変換しません。</p></div>'
        )

    return _front_matter() + f"""<link rel="stylesheet" href="{{{{ '/assets/design-system.css' | relative_url }}}}">

<div class="codex-page-shell">
<header class="codex-page-header">
<p class="codex-card-question">Observe / Developing Signal Registry</p>
<h1>Developing Signals</h1>
<p>まだResearch結論ではないが、継続観測すべき兆候の方向・鮮度・次の確認点を確認します。</p>
<div class="codex-page-header__meta"><span>Active WATCH: {len(active)}</span><span>Canonical store: {html.escape(result.status)}</span></div>
</header>

{diagnostics}

<section aria-labelledby="active-watch">
<h2 id="active-watch">継続観測中</h2>
<p>STRENGTHENING / WEAKENING は変化の方向であり、BUY / SELL推奨ではありません。UNKNOWNはnegativeへ丸めません。</p>
<div class="codex-summary-grid developing-signals-grid">
{cards}
</div>
</section>

<details class="codex-disclosure">
<summary>責務境界</summary>
<div class="codex-disclosure__body"><p>#356 Seedはcapture/triage、#170は継続観測、Research CandidateはTransmission検証、Cockpitは最終Decision Contextです。この画面はCanonical Signal storeをread-onlyで表示し、SignalやPortfolioを変更しません。</p></div>
</details>
</div>
"""


def build(path: Path = OUTPUT) -> Path:
    result = read_store(ROOT / "data" / "signals" / "developing-signals.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(result), encoding="utf-8")
    return path


if __name__ == "__main__":
    build()
