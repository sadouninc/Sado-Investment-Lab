from __future__ import annotations

import copy
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONCEPT_PATH = Path(__file__).with_name("concept-v1.json")
OS_MAP_PATH = Path(__file__).with_name("os-map-v1.json")
OUTPUT_ROOT = ROOT / "site-src" / "concepts"
OUTPUT_PATH = OUTPUT_ROOT / "investment-decision-cockpit" / "index.md"

REQUIRED = {
    "feature_id", "title_ja", "route_ref", "os_stage_ref", "purpose_ja", "first_checks",
    "why_it_matters", "common_states", "next_destination_refs", "evidence_refs",
    "non_goals", "contract_refs", "last_reviewed_at",
}
FAIL_CLOSED_STATES = {"UNKNOWN", "UNAVAILABLE", "STALE"}
JAPANESE_TEXT = re.compile(r"[ぁ-んァ-ヶ一-龠々]")
ROUTE_LABELS = {
    "/decision-cockpit/daihen/": "Live Cockpitを開く",
    "/risk-preflight/": "売買前の影響を確認する",
    "/trade-journal/": "判断・取引の記録を見る",
    "/companies/": "企業研究の根拠を見る",
    "/framework/": "投資Frameworkを確認する",
    "/reports/morning/": "Morning Reportを確認する",
    "/research/market-phase/ai-semiconductor/": "Market Phaseを確認する",
}
STATUS_TOKENS = {
    "UNKNOWN": "unknown",
    "UNAVAILABLE": "unavailable",
    "STALE": "stale",
}
FIRST_VIEW_CHECKS = (
    "前回判断からの変化",
    "市場期待との差",
    "Warning・Thesis Health（仮説の健全性）",
)
DECIDE_FLOW = (
    "対象・鮮度を確認",
    "前回との差",
    "市場期待との差",
    "Warning・Thesis Health",
    "Evidenceを確認",
    "現在の判断を整理",
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def route_inventory(os_map: dict) -> set[str]:
    routes = {entry["route"] for entry in os_map.get("today_entries", []) if entry.get("route")}
    routes |= {stage["primary_destination"] for stage in os_map.get("stages", []) if stage.get("primary_destination")}
    return routes


def _validate_japanese_first_title(record: dict) -> None:
    if record["feature_id"] == "investment-decision-cockpit":
        return
    title = record["title_ja"].strip()
    if not title or not JAPANESE_TEXT.search(title):
        raise ValueError("generic guide title_ja must contain Japanese")
    first_japanese = JAPANESE_TEXT.search(title)
    first_ascii = re.search(r"[A-Za-z]", title)
    if first_ascii and first_japanese and first_ascii.start() < first_japanese.start():
        raise ValueError("generic guide title_ja must be Japanese-first")
    if len(title) > 24:
        raise ValueError("generic guide title_ja must stay compact for mobile")


def validate_concept(record: dict, os_map: dict) -> None:
    missing = REQUIRED - record.keys()
    if missing:
        raise ValueError(f"missing required fields: {sorted(missing)}")
    _validate_japanese_first_title(record)
    if not 1 <= len(record["first_checks"]) <= 3:
        raise ValueError("first_checks must contain 1..3 items")
    stages = {stage["stage_id"] for stage in os_map["stages"]}
    if record["os_stage_ref"] not in stages:
        raise ValueError("unknown os_stage_ref")
    routes = route_inventory(os_map)
    for ref in [record["route_ref"], *record["next_destination_refs"], *record["evidence_refs"]]:
        if ref not in routes:
            raise ValueError(f"unknown route/evidence ref: {ref}")
    states = {item["status"]: item["meaning_ja"] for item in record["common_states"]}
    if set(states) != FAIL_CLOSED_STATES:
        raise ValueError("UNKNOWN / UNAVAILABLE / STALE meanings are required")
    if any(not text.strip() for text in states.values()):
        raise ValueError("state meanings must be explicit")


def validate_all(data: dict, os_map: dict) -> None:
    feature_ids: set[str] = set()
    for record in data.get("concepts", []):
        validate_concept(record, os_map)
        feature_id = record["feature_id"]
        if feature_id in feature_ids:
            raise ValueError(f"duplicate feature_id: {feature_id}")
        feature_ids.add(feature_id)


def _link(ref: str, class_name: str = "codex-action codex-action--secondary") -> str:
    label = html.escape(ROUTE_LABELS.get(ref, ref))
    route = html.escape(ref, quote=True)
    return f'<a class="{class_name}" href="{{{{ \'{route}\' | relative_url }}}}">{label}</a>'


def _states(record: dict) -> str:
    return "\n".join(
        '<article class="codex-alert" '
        f'data-state="{STATUS_TOKENS[item["status"]]}">'
        f'<strong><span class="codex-status-chip" data-state="{STATUS_TOKENS[item["status"]]}">'
        f'{html.escape(item["status"])}</span></strong>'
        f'<p>{html.escape(item["meaning_ja"])}</p>'
        '</article>'
        for item in record["common_states"]
    )


def _non_goals(record: dict) -> str:
    return "\n".join(f"<li>{html.escape(text)}</li>" for text in record["non_goals"])


def _evidence(record: dict) -> str:
    return "\n".join(
        '<div class="codex-evidence">'
        f'{_link(ref)}'
        '<div class="codex-evidence__meta">Canonical source / route truthを参照</div>'
        '</div>'
        for ref in record["evidence_refs"]
    )


def _stage_label(record: dict, os_map: dict) -> str:
    for index, stage in enumerate(os_map["stages"], 1):
        if stage["stage_id"] == record["os_stage_ref"]:
            return f"Sado Investment Codex / {index} {stage['purpose_ja']}"
    raise ValueError("unknown os_stage_ref")


def render(record: dict, os_map: dict) -> str:
    """Render the Cockpit fixture while keeping #317 and #418 visual contracts aligned."""
    before = copy.deepcopy(record)
    validate_concept(record, os_map)

    checks = "\n".join(
        '<article class="codex-summary-card">'
        f'<p class="codex-card-question">最初に見る {index}</p>'
        f'<h3>{html.escape(text)}</h3>'
        '</article>'
        for index, text in enumerate(FIRST_VIEW_CHECKS, 1)
    )
    states = _states(record)
    next_links = "".join(_link(ref) for ref in record["next_destination_refs"])
    evidence = "".join(
        '<div class="codex-evidence">'
        f'{_link(ref)}'
        '<div class="codex-evidence__meta">Canonical source / route truthを参照</div>'
        '</div>'
        for ref in record["evidence_refs"]
    )
    non_goals = "".join(f"<li>{html.escape(text)}</li>" for text in record["non_goals"])
    flow = " → ".join(html.escape(item) for item in DECIDE_FLOW)
    contracts = " / ".join(html.escape(item) for item in record["contract_refs"])

    output = f'''---
layout: site
title: 投資判断コックピット — 見方ガイド
permalink: /concepts/investment-decision-cockpit/
---

<link rel="stylesheet" href="{{{{ '/assets/design-system.css' | relative_url }}}}">

<div class="codex-page-shell">
  <header class="codex-page-header">
    <span class="codex-instrument-icon" aria-hidden="true">◇</span>
    <p class="codex-card-question">Sado Investment Codex / 5 判断</p>
    <h1>投資判断コックピット</h1>
    <p>前回からの変化・市場期待との差・投資仮説の健全性を、最初の30秒で確認する画面です。</p>
    <div class="codex-page-header__meta"><span>最終確認: {html.escape(record['last_reviewed_at'])}</span></div>
  </header>

  <section aria-labelledby="first-checks">
    <h2 id="first-checks">最初の30秒で見る3点</h2>
    <p>対象と鮮度を確認したら、次の3点を順に見ます。売買前のポートフォリオ影響は、判断を整理した後のRisk Preflightで確認します。</p>
    <div class="codex-summary-grid">
{checks}
    </div>
  </section>

  <section aria-labelledby="decision-flow"><h2 id="decision-flow">判断の流れ — What do I think?</h2><div class="codex-evidence"><strong>{flow}</strong><div class="codex-evidence__meta">Cockpitは「自分は今どう考えるか」を整理するDecideの画面です。「何をするか」はRisk Preflightへ、実行後の記録はTrade Journalへhandoffします。</div></div></section>

  <section aria-labelledby="state-meaning"><h2 id="state-meaning">状態の意味</h2><p>取得不能や古い情報を、正常・中立・悲観へ丸めません。</p>
{states}</section>

  <section aria-labelledby="next-actions"><h2 id="next-actions">判断の次に進む</h2><p>ここから先はAct / Recordです。Cockpitの判断材料と混ぜず、目的ごとの既存画面へ進みます。</p><div class="codex-action-row">{_link(record['route_ref'], 'codex-action codex-action--primary')}{next_links}</div></section>

  <section aria-labelledby="evidence-links"><h2 id="evidence-links">根拠を見る</h2>{evidence}</section>

  <details class="codex-disclosure"><summary>この機能がしないこと</summary><div class="codex-disclosure__body"><ul>{non_goals}</ul></div></details>
  <details class="codex-disclosure"><summary>設計・実装情報</summary><div class="codex-disclosure__body"><p>Concept contract: {contracts}</p></div></details>
</div>'''
    if record != before:
        raise AssertionError("Concept rendering mutated canonical input")
    return output


def render_generic(record: dict, os_map: dict) -> str:
    before = copy.deepcopy(record)
    validate_concept(record, os_map)
    title = record["title_ja"]
    checks = "\n".join(
        '<article class="codex-summary-card">'
        f'<p class="codex-card-question">最初に見る {index}</p>'
        f'<h3>{html.escape(text)}</h3>'
        '</article>'
        for index, text in enumerate(record["first_checks"], 1)
    )
    next_links = "\n".join(_link(ref) for ref in record["next_destination_refs"])
    contracts = " / ".join(html.escape(item) for item in record["contract_refs"])

    output = f'''---
layout: site
title: {html.escape(title)} | 見方ガイド
permalink: /concepts/{html.escape(record['feature_id'], quote=True)}/
---

<link rel="stylesheet" href="{{{{ '/assets/design-system.css' | relative_url }}}}">

<div class="codex-page-shell concept-guide--compact-title">
  <header class="codex-page-header">
    <span class="codex-instrument-icon" aria-hidden="true">◇</span>
    <p class="codex-card-question">{html.escape(_stage_label(record, os_map))}</p>
    <span class="codex-status-chip" data-state="normal">見方ガイド</span>
    <h1>{html.escape(title)}</h1>
    <p>{html.escape(record['purpose_ja'])}</p>
    <div class="codex-page-header__meta">
      <span>最終確認: {html.escape(record['last_reviewed_at'])}</span>
      <span>Concept contract: {contracts}</span>
    </div>
  </header>

  <section aria-labelledby="first-checks">
    <h2 id="first-checks">最初の30秒で見るポイント</h2>
    <div class="codex-summary-grid">
{checks}
    </div>
  </section>

  <section aria-labelledby="why-it-matters">
    <h2 id="why-it-matters">なぜ見るのか</h2>
    <div class="codex-evidence"><strong>{html.escape(record['why_it_matters'])}</strong></div>
  </section>

  <section aria-labelledby="state-meaning">
    <h2 id="state-meaning">状態の意味</h2>
    <p>UNKNOWN / UNAVAILABLE / STALEを正常値へ丸めず、確認できないこと自体を判断材料として残します。</p>
{_states(record)}
  </section>

  <section aria-labelledby="next-actions">
    <h2 id="next-actions">次に進む</h2>
    <div class="codex-action-row">
      {_link(record['route_ref'], 'codex-action codex-action--primary')}
{next_links}
    </div>
  </section>

  <section aria-labelledby="evidence-links">
    <h2 id="evidence-links">根拠を見る</h2>
{_evidence(record)}
  </section>

  <details class="codex-disclosure">
    <summary>この機能がしないこと</summary>
    <div class="codex-disclosure__body"><ul>
{_non_goals(record)}
    </ul></div>
  </details>
</div>
'''
    if record != before:
        raise AssertionError("Concept rendering mutated canonical input")
    return output


def render_guide(record: dict, os_map: dict) -> str:
    if record["feature_id"] == "investment-decision-cockpit":
        return render(record, os_map)
    return render_generic(record, os_map)


def output_path(record: dict) -> Path:
    return OUTPUT_ROOT / record["feature_id"] / "index.md"


def main() -> None:
    data = load_json(CONCEPT_PATH)
    os_map = load_json(OS_MAP_PATH)
    validate_all(data, os_map)
    for record in data["concepts"]:
        target = output_path(record)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_guide(record, os_map), encoding="utf-8")


if __name__ == "__main__":
    main()
