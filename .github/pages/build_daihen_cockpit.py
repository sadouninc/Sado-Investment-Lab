from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from scripts.daihen_operational_read_model import build_daihen_operational_read_model

PAGES_DIR = Path(__file__).resolve().parent
if str(PAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PAGES_DIR))

from scenario_delta import ScenarioSnapshot, build_scenario_delta


ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site-src"
FIXTURE = ROOT / "data" / "fixtures" / "acceptance" / "6622-daihen-operational-v1.json"
GENERATED_AT = "2026-08-09T19:30:00+09:00"


STATUS_JA = {
    "OK": "確認可能",
    "PARTIAL": "一部情報不足",
    "NEEDS_REVIEW": "要確認",
    "UNAVAILABLE": "現在取得できません",
    "NOT_RUN": "まだ確認を実行していません",
    "CURRENT": "現在確認できる情報",
    "STALE": "情報が古いため再確認が必要",
    "UNKNOWN": "鮮度を確認できません",
}

DIRECTION_JA = {
    "IMPROVED": "改善",
    "UNCHANGED": "維持",
    "DETERIORATED": "悪化",
    "EXPANDED": "拡大",
    "NARROWED": "縮小",
    "UNKNOWN": "比較情報不足",
}


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _status(value: Any) -> str:
    text = str(value or "UNKNOWN").upper()
    return f"{_e(STATUS_JA.get(text, text))} <code>{_e(text)}</code>"


def _list(items: Any, empty: str = "情報なし") -> str:
    values = list(items or [])
    if not values:
        return f'<p class="muted">{_e(empty)}</p>'
    return "<ul>" + "".join(f"<li>{_e(item)}</li>" for item in values) + "</ul>"


def _refs(items: Any) -> str:
    values = list(items or [])
    if not values:
        return '<span class="muted">参照なし</span>'
    rendered: list[str] = []
    for ref in values:
        text = str(ref)
        if text.startswith("issue:") and text.split(":", 1)[1].isdigit():
            number = text.split(":", 1)[1]
            rendered.append(
                f'<a href="https://github.com/sadouninc/Sado-Investment-Lab/issues/{number}">{_e(text)}</a>'
            )
        else:
            rendered.append(f"<code>{_e(text)}</code>")
    return " / ".join(rendered)


def _scenario_card(label: str, scenario: Mapping[str, Any]) -> str:
    eps = scenario.get("eps")
    per = scenario.get("forward_per")
    eps_text = "取得できません" if eps is None else f"{float(eps):,.2f}円"
    per_text = "取得できません" if per is None else f"{float(per):,.2f}倍"
    return (
        '<div class="content-card scenario-card">'
        f"<strong>{_e(label)}</strong>"
        f"<span>EPS: {_e(eps_text)}</span>"
        f"<span>Forward PER: {_e(per_text)}</span>"
        "</div>"
    )


def _scenario_delta(model: Mapping[str, Any]):
    valuation = model["valuation"]
    base = valuation.get("base") or {}
    previous = ScenarioSnapshot(
        scenario="UNKNOWN",
        eps=None,
        price=None,
        forward_per=None,
    )
    current = ScenarioSnapshot(
        scenario="Base" if base else "UNKNOWN",
        eps=base.get("eps"),
        price=None,
        forward_per=base.get("forward_per"),
    )
    return build_scenario_delta(previous, current)


def _scenario_delta_html(model: Mapping[str, Any]) -> str:
    delta = _scenario_delta(model)
    history = model["decision_history"]
    previous_eps = "取得できません" if delta.previous.eps is None else f"{delta.previous.eps:,.2f}円"
    current_eps = "取得できません" if delta.current.eps is None else f"{delta.current.eps:,.2f}円"
    previous_per = "取得できません" if delta.previous.forward_per is None else f"{delta.previous.forward_per:,.2f}倍"
    current_per = "取得できません" if delta.current.forward_per is None else f"{delta.current.forward_per:,.2f}倍"
    return f"""
<div class="content-card scenario-delta-summary">
  <strong>前回から何が変わった？</strong>
  <span class="status-chip">Scenario: {_e(delta.scenario_transition)}</span>
  <span>{_e(delta.summary_ja)}</span>
  <div class="content-grid scenario-delta-directions">
    <div><strong>業績見通し</strong><span class="delta-indicator">{_e(DIRECTION_JA[delta.earnings_direction])} <code>{_e(delta.earnings_direction)}</code></span></div>
    <div><strong>Valuation余地</strong><span class="delta-indicator">{_e(DIRECTION_JA[delta.valuation_direction])} <code>{_e(delta.valuation_direction)}</code></span></div>
  </div>
  <details class="progressive-disclosure">
    <summary>Previous / Current の詳細値</summary>
    <div class="table-scroll"><table>
      <thead><tr><th>指標</th><th>Previous</th><th>Current</th></tr></thead>
      <tbody>
        <tr><th>Scenario</th><td>{_e(delta.previous.scenario)}</td><td>{_e(delta.current.scenario)}</td></tr>
        <tr><th>EPS</th><td>{_e(previous_eps)}</td><td>{_e(current_eps)}</td></tr>
        <tr><th>Forward PER</th><td>{_e(previous_per)}</td><td>{_e(current_per)}</td></tr>
      </tbody>
    </table></div>
  </details>
  <span class="muted">Previous snapshot値はCanonical sourceに存在する場合だけ表示します。現在値から過去値を逆算しません。比較ref: {_refs([history.get('comparison_ref')] if history.get('comparison_ref') else [])}</span>
</div>
"""


def _expectation_first_view(expectations: Mapping[str, Any]) -> str:
    status = str(expectations.get("status") or "UNKNOWN").upper()
    if status == "UNAVAILABLE":
        message = "市場期待データは現在取得できません。差なし・0として扱いません。"
    elif status in {"PARTIAL", "STALE", "UNKNOWN"}:
        message = "市場期待との差は情報不足または鮮度制約付きです。根拠を確認してから判断します。"
    else:
        message = "市場期待との差はCanonical evidenceが確認できる範囲だけ表示します。"
    return f"""
<div class="content-card cockpit-expectation-summary">
  <strong>市場期待との差は？</strong>
  <span class="status-chip">{_status(status)}</span>
  <span>{_e(message)}</span>
</div>
"""


def page_content(model: Mapping[str, Any]) -> str:
    review = model["review_context"]
    earnings = model["earnings_driver"]
    valuation = model["valuation"]
    expectations = model["expectations"]
    hypothesis = model["hypothesis"]
    portfolio = model["portfolio_preflight"]
    history = model["decision_history"]
    freshness = model["freshness"]

    why_now = list(review.get("why_now") or [])
    why_now_text = why_now[0] if why_now else "今日見る理由を取得できません"
    last_change = review.get("last_material_change_at") or "時刻不明"
    health = hypothesis.get("health") or "取得できません"

    warnings = []
    for section_name in ("earnings_driver", "valuation", "expectations"):
        for warning in model[section_name].get("warnings") or []:
            warnings.append(f"{section_name}: {warning}")

    base_profit = earnings.get("base_profit") or {}
    base_eps = earnings.get("base_eps") or {}
    guidance = earnings.get("company_guidance") or {}
    base_profit_text = "取得できません" if base_profit.get("value") is None else f"{float(base_profit['value']):,.0f}百万円"
    base_eps_text = "取得できません" if base_eps.get("value") is None else f"{float(base_eps['value']):,.2f}円"
    guidance_text = "取得できません" if guidance.get("net_income_million_jpy") is None else f"{float(guidance['net_income_million_jpy']):,.0f}百万円"

    scenario_html = "".join([
        _scenario_card("Bear", valuation.get("bear") or {}),
        _scenario_card("Base", valuation.get("base") or {}),
        _scenario_card("Bull", valuation.get("bull") or {}),
    ])
    delta_html = _scenario_delta_html(model)
    expectation_html = _expectation_first_view(expectations)
    warning_html = _list(warnings, "重大warningなし")
    stale = freshness.get("stale_components") or []
    unknown = freshness.get("unknown_components") or []
    price_as_of = valuation.get("price_as_of") or "取得できません"
    warning_count = len(warnings)

    return f"""---
layout: site
title: ダイヘン 投資判断コックピット
description: ダイヘンについて今日見る理由、利益予想、割安度、仮説、ポートフォリオ、前回判断を1画面で確認する
permalink: /decision-cockpit/daihen/
---

<p class="breadcrumb"><a href="{{{{ '/' | relative_url }}}}">Home</a> / ダイヘン 投資判断コックピット</p>

# 🎯 ダイヘン 投資判断コックピット

<p><strong>今日見る理由:</strong> {_e(why_now_text)} <span class="muted">最終重要変化: {_e(last_change)}</span></p>

<div class="notice-card"><strong>この画面は売買指示を生成しません。</strong><br>既存Canonical outputを読み取り専用でまとめ、判断に必要な不足・古さ・要確認事項を隠さず表示します。</div>

<div class="content-grid cockpit-first-view">
  <div class="content-card cockpit-identity-summary"><strong>ダイヘン / 6622</strong><span>情報鮮度: {_status(freshness.get('overall'))}</span><span class="muted">株価基準日: {_e(price_as_of)}</span></div>
  {delta_html}
  {expectation_html}
  <div class="content-card cockpit-thesis-summary"><strong>Warning / Thesis Health</strong><span>Health: <code>{_e(health)}</code></span><span>仮説状態: {_status(hypothesis.get('status'))}</span><span>確認すべきwarning: {_e(warning_count)}件</span></div>
</div>

## ⚠ 先に確認する注意点

- 全体状態: {_status(model.get('overall_status'))}
- 情報鮮度: {_status(freshness.get('overall'))}
- 古いcomponent: {_e(', '.join(stale) if stale else 'なし')}
- 鮮度不明component: {_e(', '.join(unknown) if unknown else 'なし')}

{warning_html}

## 1. 利益予想 — なぜこのBase？

<div class="content-grid">
  <div class="content-card"><strong>Base純利益</strong><span>{_e(base_profit_text)}</span><span>{_status(earnings.get('status'))}</span></div>
  <div class="content-card"><strong>Base EPS</strong><span>{_e(base_eps_text)}</span><span>対象: {_e(base_eps.get('target_fiscal_year') or '不明')}</span></div>
  <div class="content-card"><strong>会社予想 純利益</strong><span>{_e(guidance_text)}</span><span>説明coverage: <code>{_e(earnings.get('explanation_coverage') or 'UNKNOWN')}</code></span></div>
</div>

根拠driver: {_refs(earnings.get('driver_refs'))}  
Source: {_refs(earnings.get('source_refs'))}

> `PARTIAL` は完全導出を意味しません。説明できない部分をAIが補完していません。

## 2. Bear / Base / Bull とForward PER

<div class="content-grid scenario-grid">
{scenario_html}
</div>

- 株価基準日: **{_e(valuation.get('price_as_of') or '取得できません')}**
- 対象年度: **{_e(valuation.get('target_fiscal_year') or '取得できません')}**
- 状態: {_status(valuation.get('status'))} / 鮮度: {_status(valuation.get('freshness'))}
- Source: {_refs(valuation.get('source_refs'))}

**株価情報が古い場合、現在の割安度として無警告では使用しません。**

## 3. 市場期待との差

状態: {_status(expectations.get('status'))}

- Company Guidance: {_refs([expectations.get('company_guidance_ref')] if expectations.get('company_guidance_ref') else [])}
- External Consensus: {_refs([expectations.get('external_consensus_ref')] if expectations.get('external_consensus_ref') else [])}
- Sado Base: {_refs([expectations.get('sado_base_ref')] if expectations.get('sado_base_ref') else [])}
- Latest Actual: {_refs([expectations.get('latest_actual_ref')] if expectations.get('latest_actual_ref') else [])}

**Consensusを取得できない場合、gap=0や「差なし」とは表示しません。**

## 4. 投資仮説は生きているか

### Must happen
{_list(hypothesis.get('must_happen'), '取得できません')}

### 反証・無効化条件
{_list(hypothesis.get('invalidation_conditions'), '取得できません')}

Supporting evidence: {_refs(hypothesis.get('supporting_evidence_refs'))}  
Challenging evidence: {_refs(hypothesis.get('challenging_evidence_refs'))}

## 5. 売買前のポートフォリオ影響

状態: {_status(portfolio.get('status'))}

{_list(portfolio.get('unknown_dimensions'), '不明dimensionなし')}

[売買前のポートフォリオ確認を開く]({{{{ '/risk-preflight/' | relative_url }}}})

未設定ルールや未実行preflightから安全/危険を推測しません。

## 6. 前回判断と現在を分けて確認

- 最新Decision: {_refs([history.get('latest_decision_ref')] if history.get('latest_decision_ref') else [])}
- Investment Episode: {_refs([history.get('latest_episode_ref')] if history.get('latest_episode_ref') else [])}
- Current comparison: {_refs([history.get('comparison_ref')] if history.get('comparison_ref') else [])}
- **Historical immutable snapshot**: {_refs([history.get('historical_snapshot_ref')] if history.get('historical_snapshot_ref') else [])}

過去snapshotを現在のResearch / Valuationで書き換えません。

## 7. 次に確認する場所

- 利益予想の根拠: {_refs(earnings.get('driver_refs'))}
- 次checkpoint: {_refs(review.get('next_checkpoint_refs'))}
- 仮説source: {_refs(hypothesis.get('source_refs'))}
- 全source refs: {_refs(model.get('source_refs'))}

---

## 30秒チェック

この画面の最初のviewportと警告を見て、次を確認します。

1. 対象銘柄と情報鮮度はどうか
2. 前回から何が変わったか
3. 市場期待との差は確認可能か
4. Warning / Thesis Healthに変化があるか
5. Base EPSの主な根拠は何か
6. 何が起きたら仮説が崩れるのか
7. 次にどこを確認するか

<p class="muted">Generated from #257 PR-A read model. Presentation layer only / no upstream write-back.</p>
"""


def load_model() -> dict[str, Any]:
    upstream = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return build_daihen_operational_read_model(upstream, generated_at=GENERATED_AT)


def build() -> None:
    model = load_model()
    target = SITE / "decision-cockpit" / "daihen" / "index.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page_content(model).rstrip() + "\n", encoding="utf-8")

    home = SITE / "index.md"
    if home.is_file():
        text = home.read_text(encoding="utf-8")
        marker = "## 🎯 ダイヘン 投資判断コックピット"
        if marker not in text:
            text += (
                "\n\n---\n\n"
                f"{marker}\n\n"
                "今日見る理由、利益予想、Bear/Base/Bull、仮説、ポートフォリオ、前回判断を1画面で確認します。\n\n"
                "[ダイヘン 投資判断コックピットを開く]({{ '/decision-cockpit/daihen/' | relative_url }})\n"
            )
            home.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    build()
