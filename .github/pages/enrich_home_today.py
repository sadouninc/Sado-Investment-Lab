from __future__ import annotations

from copy import deepcopy
import html
import json
from pathlib import Path
from typing import Any, Mapping

from scripts.morning_dataset.providers import SectorRotationProvider

ROOT = Path(__file__).resolve().parents[2]
SITE_HOME = ROOT / "site-src" / "index.md"
MORNING_DATASET = ROOT / "data" / "generated" / "public" / "morning-dataset.json"

STATUS_SECTION_START = '  <section class="home-os-section" aria-labelledby="status-title">'
STATUS_SECTION_END = '  <section class="home-os-section" aria-labelledby="map-title">'

STATUS_LABELS = {
    "OK": ("normal", "確認可能"),
    "PARTIAL": ("caution", "一部情報不足"),
    "STALE": ("stale", "情報が古い"),
    "MISSING": ("unavailable", "取得できません"),
}


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _status(value: Any) -> tuple[str, str, str]:
    status = str(value or "MISSING").upper()
    token, label = STATUS_LABELS.get(status, ("unknown", "状態不明"))
    return status, token, label


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


def render_status_section(dataset: Mapping[str, Any] | None) -> str:
    if not isinstance(dataset, Mapping):
        return f'''{STATUS_SECTION_START}
    <p class="eyebrow">STATUS</p>
    <h2 id="status-title">重要な変化・状態</h2>
    <div class="codex-alert" data-state="unavailable">
      <strong>Morning Datasetを取得できません</strong>
      <p>取得不能を「問題なし」「最新」とは扱いません。Morning Dataset生成後に再確認してください。</p>
    </div>
  </section>

'''

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
    return f'''{STATUS_SECTION_START}
    <p class="eyebrow">STATUS</p>
    <h2 id="status-title">重要な変化・状態</h2>
    <div class="codex-alert" data-state="{quality_token}">
      <strong>Morning Dataset: {_e(quality_label)} / {_e(quality_status)}</strong>
      <p>Dataset as of: {_e(dataset.get('as_of') or '時点不明')} / completeness: {_e(quality.get('completeness_label') or '不明')}</p>
    </div>
    <div class="codex-summary-grid home-primary-grid">
{cards}
    </div>
{warning_html}
  </section>

'''


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


def enrich_text(text: str, dataset: Mapping[str, Any] | None) -> str:
    start = text.find(STATUS_SECTION_START)
    end = text.find(STATUS_SECTION_END)
    if start < 0 or end < 0 or end <= start:
        raise ValueError("Home status section boundary not found")
    return text[:start] + render_status_section(dataset) + text[end:]


def enrich_home_from_morning(home_path: Path = SITE_HOME, dataset_path: Path = MORNING_DATASET) -> None:
    text = home_path.read_text(encoding="utf-8")
    home_path.write_text(enrich_text(text, load_dataset(dataset_path)), encoding="utf-8")


if __name__ == "__main__":
    enrich_home_from_morning()
