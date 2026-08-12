from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
import html
import json
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from scripts.morning_dataset.providers import SectorRotationProvider

ROOT = Path(__file__).resolve().parents[2]
SITE_HOME = ROOT / "site-src" / "index.md"
MORNING_DATASET = ROOT / "data" / "generated" / "public" / "morning-dataset.json"
SECTOR_ROTATION_ROUTE = "/market-analysis/2026/sector-rotation/"

STATUS_SECTION_START = '  <section class="home-os-section" aria-labelledby="status-title">'
STATUS_SECTION_END = '  <section class="home-os-section" aria-labelledby="map-title">'

STATUS_LABELS = {
    "OK": ("normal", "確認可能"),
    "PARTIAL": ("caution", "一部情報不足"),
    "STALE": ("stale", "情報が古い"),
    "MISSING": ("unavailable", "取得できません"),
}

SECTOR_STATE_LABELS = {
    "COLD": "静穏",
    "WARMING": "温まり始め",
    "INFLOW": "資金流入",
    "HOT": "高温",
    "OVERHEATED": "過熱",
}


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _status(value: Any) -> tuple[str, str, str]:
    status = str(value or "MISSING").upper()
    token, label = STATUS_LABELS.get(status, ("unknown", "状態不明"))
    return status, token, label


def expected_jst_business_date(now: datetime | None = None) -> date:
    current = now or datetime.now(ZoneInfo("Asia/Tokyo"))
    day = current.astimezone(ZoneInfo("Asia/Tokyo")).date()
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def morning_freshness(dataset_as_of: Any, *, expected_as_of: date) -> str:
    try:
        observed = date.fromisoformat(str(dataset_as_of or ""))
    except ValueError:
        return "DATASET_DATE_INVALID"
    if observed < expected_as_of:
        return "NOT_GENERATED_TODAY"
    if observed > expected_as_of:
        return "DATASET_DATE_INVALID"
    return "CURRENT"


def _source_status(dataset: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    for row in dataset.get("source_status") or []:
        if isinstance(row, Mapping) and row.get("name") == name:
            return row
    return {"name": name, "status": "MISSING", "reason": "source status not available"}


def _status_card(title: str, source: Mapping[str, Any], detail: str) -> str:
    status, token, label = _status(source.get("status"))
    as_of = source.get("as_of") or "時点不明"
    reason = source.get("reason")
    reason_html = f'<p class="codex-evidence__meta">{_e(reason)}</p>' if reason else ""
    return (
        '<article class="codex-summary-card">'
        f'<span class="codex-status-chip" data-state="{token}">{_e(label)} / {_e(status)}</span>'
        f'<h3>{_e(title)}</h3><p>{_e(detail)}</p>'
        f'<p class="codex-evidence__meta">as of: {_e(as_of)}</p>{reason_html}'
        '</article>'
    )


def with_sector_rotation(dataset: Mapping[str, Any]) -> dict[str, Any]:
    """Attach the existing #359 read provider for Home only, without mutating Morning."""
    merged = deepcopy(dict(dataset))
    existing = _source_status(merged, "sector_rotation")
    if existing.get("status") in {"OK", "PARTIAL", "STALE"} and isinstance(
        merged.get("sector_rotation"), Mapping
    ):
        return merged

    result = SectorRotationProvider().collect()
    rows = [
        deepcopy(dict(row))
        for row in merged.get("source_status") or []
        if isinstance(row, Mapping) and row.get("name") != "sector_rotation"
    ]
    rows.append(result.metadata() | {"name": result.name})
    merged["source_status"] = rows
    if result.data is not None:
        merged["sector_rotation"] = deepcopy(result.data)
    return merged


def _transition_text(row: Mapping[str, Any]) -> tuple[str, str]:
    previous = str(row.get("previous_state") or "UNKNOWN")
    current = str(row.get("state") or "UNKNOWN")
    if previous == "COLD" and current == "WARMING":
        change = "↗ 初動"
    elif previous == "WARMING" and current == "INFLOW":
        change = "⇧ 流入へ移行"
    elif previous == current:
        change = "→ 継続"
    else:
        change = "↔ 状態変化"
    return f"{previous} → {current}", change


def render_sector_heatmap(dataset: Mapping[str, Any]) -> str:
    source = _source_status(dataset, "sector_rotation")
    status, token, label = _status(source.get("status"))
    payload = dataset.get("sector_rotation") if isinstance(dataset.get("sector_rotation"), Mapping) else {}
    sectors = payload.get("sectors") if isinstance(payload.get("sectors"), list) else []
    as_of = payload.get("as_of") or source.get("as_of") or "時点不明"

    if not sectors:
        return f'''  <section class="home-os-section home-heatmap" aria-labelledby="heatmap-title">
    <p class="eyebrow">MARKET HEATMAP</p>
    <h2 id="heatmap-title">市場・テーマの動き</h2>
    <p>今日の判断に影響しそうな変化を、既存Canonical stateだけで俯瞰します。</p>
    <div class="codex-alert" data-state="unavailable">
      <strong>Sector Rotationは取得できません</strong>
      <p>{_e(source.get('reason') or 'canonical Sector snapshotが未接続です。')}</p>
    </div>
  </section>

'''

    cells: list[str] = []
    for row in sectors:
        if not isinstance(row, Mapping):
            continue
        state = str(row.get("state") or "UNKNOWN")
        transition, change = _transition_text(row)
        state_label = SECTOR_STATE_LABELS.get(state, "状態不明")
        name = row.get("name") or row.get("id") or "名称不明"
        cells.append(
            '<article class="home-heatmap-cell" '
            f'data-sector-state="{_e(state.lower())}">'
            f'<span class="home-heatmap-cell__state">{_e(state_label)} / {_e(state)}</span>'
            f'<h3>{_e(name)}</h3>'
            f'<p class="home-heatmap-cell__transition">{_e(transition)}</p>'
            f'<p class="home-heatmap-cell__change">{_e(change)}</p>'
            '</article>'
        )

    grid = "\n".join(cells)
    return f'''  <section class="home-os-section home-heatmap" aria-labelledby="heatmap-title">
    <p class="eyebrow">MARKET HEATMAP</p>
    <h2 id="heatmap-title">市場・テーマの動き</h2>
    <p>TOPIX-17 Sector Rotationの前回→現在を表示します。Homeで独自score・ranking・BUY/SELLは生成しません。</p>
    <div class="codex-alert" data-state="{token}">
      <strong>Sector Rotation: {_e(label)} / {_e(status)}</strong>
      <p>as of: {_e(as_of)} / source: canonical sector-history.jsonl</p>
    </div>
    <div class="home-heatmap-grid" aria-label="TOPIX-17 Sector Rotation HeatMap">
{grid}
    </div>
    <div class="codex-evidence home-heatmap-evidence">
      <a href="{{{{ '{SECTOR_ROTATION_ROUTE}' | relative_url }}}}">Sector Rotationの詳細を見る</a>
      <p class="codex-evidence__meta">state / previous_state / as_of は既存Canonical値をそのまま表示しています。</p>
    </div>
  </section>

'''


def render_status_section(
    dataset: Mapping[str, Any] | None, *, expected_as_of: date | None = None
) -> str:
    if not isinstance(dataset, Mapping):
        return f'''{STATUS_SECTION_START}
    <p class="eyebrow">STATUS</p>
    <h2 id="status-title">重要な変化・状態</h2>
    <div class="codex-alert" data-state="unavailable">
      <strong>Morning Datasetを取得できません</strong>
      <p>取得不能を「問題なし」「最新」とは扱いません。Morning Dataset生成後に再確認してください。</p>
    </div>
  </section>

  <section class="home-os-section home-heatmap" aria-labelledby="heatmap-title">
    <p class="eyebrow">MARKET HEATMAP</p>
    <h2 id="heatmap-title">市場・テーマの動き</h2>
    <div class="codex-alert" data-state="unavailable">
      <strong>HeatMapを表示できません</strong>
      <p>Canonical sourceを取得できないため、状態を推測表示しません。</p>
    </div>
  </section>

'''

    expected = expected_as_of or expected_jst_business_date()
    freshness = morning_freshness(dataset.get("as_of"), expected_as_of=expected)
    quality = dataset.get("data_quality") if isinstance(dataset.get("data_quality"), Mapping) else {}
    quality_status, quality_token, quality_label = _status(quality.get("status"))
    market = _source_status(dataset, "market")
    sector = _source_status(dataset, "sector_rotation")
    sector_payload = dataset.get("sector_rotation") if isinstance(dataset.get("sector_rotation"), Mapping) else {}
    sectors = sector_payload.get("sectors") if isinstance(sector_payload.get("sectors"), list) else []
    warming = sum(1 for row in sectors if isinstance(row, Mapping) and row.get("state") == "WARMING")
    inflow = sum(1 for row in sectors if isinstance(row, Mapping) and row.get("state") == "INFLOW")
    warnings = [str(item) for item in (dataset.get("warnings") or []) if item]
    warning_html = (
        '<div class="codex-alert" data-state="caution"><strong>既存Dataset warning</strong><ul>'
        + ''.join(f'<li>{_e(item)}</li>' for item in warnings[:5])
        + '</ul></div>'
        if warnings else
        '<div class="codex-alert" data-state="normal"><strong>Morning Datasetに明示warningはありません</strong><p>これはBUY/SELL判断ではありません。</p></div>'
    )

    cards = "\n".join([
        _status_card("市場データ", market, "Morning Datasetの既存market source状態を表示します。"),
        _status_card(
            "Sector Rotation",
            sector,
            f"最新canonical set内の WARMING {warming}件 / INFLOW {inflow}件。順位や推奨はHomeで生成しません。",
        ),
    ])
    if freshness == "NOT_GENERATED_TODAY":
        dataset_alert = f'''<div class="codex-alert" data-state="stale">
      <strong>今日のMorning Datasetはまだ生成されていません / NOT_GENERATED_TODAY</strong>
      <p>表示中: {_e(dataset.get('as_of') or '時点不明')} / 期待営業日: {_e(expected.isoformat())}</p>
      <p>source completenessのPARTIALとは別の、当日pipeline未生成状態です。</p>
    </div>'''
    elif freshness == "DATASET_DATE_INVALID":
        dataset_alert = f'''<div class="codex-alert" data-state="unavailable">
      <strong>Morning Datasetの日付を検証できません / DATASET_DATE_INVALID</strong>
      <p>表示値: {_e(dataset.get('as_of') or '時点不明')} / 期待営業日: {_e(expected.isoformat())}</p>
    </div>'''
    else:
        dataset_alert = f'''<div class="codex-alert" data-state="{quality_token}">
      <strong>Morning Dataset: {_e(quality_label)} / {_e(quality_status)}</strong>
      <p>Dataset as of: {_e(dataset.get('as_of') or '時点不明')} / completeness: {_e(quality.get('completeness_label') or '不明')}</p>
    </div>'''

    return f'''{STATUS_SECTION_START}
    <p class="eyebrow">STATUS</p>
    <h2 id="status-title">重要な変化・状態</h2>
    {dataset_alert}
    <div class="codex-summary-grid home-primary-grid">
{cards}
    </div>
{warning_html}
  </section>

{render_sector_heatmap(dataset)}'''


def load_dataset(path: Path = MORNING_DATASET) -> Mapping[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, Mapping):
        return None
    return with_sector_rotation(payload)


def enrich_text(
    text: str,
    dataset: Mapping[str, Any] | None,
    *,
    expected_as_of: date | None = None,
) -> str:
    start = text.find(STATUS_SECTION_START)
    end = text.find(STATUS_SECTION_END)
    if start < 0 or end < 0 or end <= start:
        raise ValueError("Home status section boundary not found")
    return text[:start] + render_status_section(
        dataset, expected_as_of=expected_as_of
    ) + text[end:]


def enrich_home_from_morning(home_path: Path = SITE_HOME, dataset_path: Path = MORNING_DATASET) -> None:
    text = home_path.read_text(encoding="utf-8")
    home_path.write_text(enrich_text(text, load_dataset(dataset_path)), encoding="utf-8")


if __name__ == "__main__":
    enrich_home_from_morning()
