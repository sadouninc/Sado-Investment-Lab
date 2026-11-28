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

from live_cockpit_shell import LiveCockpitFirstView, render_first_view
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
            rendered.append(f'<a href="https://github.com/sadouninc/Sado-Investment-Lab/issues/{number}">{_e(text)}</a>')
        else:
            rendered.append(f"<code>{_e(text)}</code>")
    return " / ".join(rendered)


def _scenario_card(label: str, scenario: Mapping[str, Any]) -> str:
    eps = scenario.get("eps")
    per = scenario.get("forward_per")
    eps_text = "取得できません" if eps is None else f"{float(eps):,.2f}円"
    per_text = "取得できません" if per is None else f"{float(per):,.2f}倍"
    return '<div class="content-card scenario-card">' f"<strong>{_e(label)}</strong>" f"<span>EPS: {_e(eps_text)}</span>" f"<span>Forward PER: {_e(per_text)}</span>" "</div>"


def _scenario_delta(model: Mapping[str, Any]):
    valuation = model["valuation"]
    base = valuation.get("base") or {}
    previous_raw = (model.get("decision_history") or {}).get("previous_snapshot") or {}
    if previous_raw.get("basis") != "split_adjusted_2026-10-01":
        previous_raw = {}
    previous = ScenarioSnapshot(
        scenario=previous_raw.get("scenario") if previous_raw.get("scenario") in {"Bear", "Base", "Bull"} else "UNKNOWN",
        eps=previous_raw.get("eps"),
        price=previous_raw.get("price"),
        forward_per=previous_raw.get("forward_per"),
        premise=previous_raw.get("note"),
    )
    current = ScenarioSnapshot(
        scenario="Base" if base else "UNKNOWN",
        eps=base.get("eps"),
        price=valuation.get("reference_price"),
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
  <details class="progressive-disclosure"><summary>Previous / Current の詳細値</summary><div class="table-scroll"><table>
    <thead><tr><th>指標</th><th>Previous</th><th>Current</th></tr></thead><tbody>
      <tr><th>Scenario</th><td>{_e(delta.previous.scenario)}</td><td>{_e(delta.current.scenario)}</td></tr>
      <tr><th>EPS</th><td>{_e(previous_eps)}</td><td>{_e(current_eps)}</td></tr>
      <tr><th>Forward PER</th><td>{_e(previous_per)}</td><td>{_e(current_per)}</td></tr>
    </tbody></table></div></details>
  <span class="muted">Previous snapshot値はCanonical sourceに存在する場合だけ表示します。現在値から過去値を逆算しません。比較ref: {_refs([history.get('comparison_ref')] if history.get('comparison_ref') else [])}</span>
</div>
"""


def _expectation_first_view(expectations: Mapping[str, Any]) -> str:
    status = str(expectations.get("status") or "UNKNOWN").upper()
    consensus = expectations.get("consensus_value")
    company = expectations.get("company_guidance_value")
    sado = expectations.get("sado_base_value")
    company_gap = expectations.get("company_vs_consensus_pct")
    sado_gap = expectations.get("sado_vs_consensus_pct")
    has_comparison = (
        expectations.get("external_consensus_ref")
        and all(value is not None for value in (consensus, company, sado, company_gap, sado_gap))
    )
    if status == "UNAVAILABLE" or not has_comparison:
        message = "市場期待データは現在取得できません。差なし・0として扱いません。"
    else:
        message = (
            f"FY2027 EPS: 市場予想 {float(consensus):,.2f}円 / "
            f"会社予想 {float(company):,.2f}円 ({float(company_gap) * 100:+.1f}%) / "
            f"Sado Base {float(sado):,.2f}円 ({float(sado_gap) * 100:+.1f}%)。"
        )
    caveat = "二次データのproxyであり、市場全体の真の期待とは断定しません。"
    return (
        '<div class="content-card cockpit-expectation-summary">'
        f"<strong>市場期待との差は？</strong><span class=\"status-chip\">{_status(status)}</span>"
        f"<span>{_e(message)} {_e(caveat)}</span>"
        '<a href="#market-expectations">市場予想・会社予想との比較を見る</a></div>'
    )


def _judgment_summary(model: Mapping[str, Any]) -> str:
    review = model["review_context"]
    valuation = model["valuation"]
    history = model["decision_history"]
    hypothesis = model["hypothesis"]
    why_now = list(review.get("why_now") or [])
    focus = why_now[0] if why_now else "確認理由を取得できません。"
    price_as_of = valuation.get("price_as_of")
    freshness = (
        f"株価基準日: {price_as_of} / 最新株価は要確認"
        if price_as_of
        else "株価基準日を取得できないため、最新株価は要確認"
    )

    delta = _scenario_delta(model)
    previous_raw = history.get("previous_snapshot") or {}
    comparable = all(
        value is not None
        for value in (
            delta.previous.eps,
            delta.current.eps,
            delta.previous.forward_per,
            delta.current.forward_per,
        )
    )
    if comparable:
        eps_change = float(delta.current.eps) - float(delta.previous.eps)
        per_change = float(delta.current.forward_per) - float(delta.previous.forward_per)
        change_summary = (
            f"EPSは前回比 {eps_change:+.2f}円、Forward PERは {per_change:+.2f}倍。"
        )
        change = (
            f"EPS {float(delta.previous.eps):,.2f}→{float(delta.current.eps):,.2f}円 "
            f"({eps_change:+.2f}円)、Forward PER "
            f"{float(delta.previous.forward_per):,.2f}→{float(delta.current.forward_per):,.2f}倍 "
            f"({per_change:+.2f}倍)。前回 {previous_raw.get('as_of') or '日付不明'} / "
            f"今回株価基準 {price_as_of or '日付不明'}、同一分割調整basis。"
        )
    else:
        change_summary = "同一basisの前回snapshotがなく、前回差は比較できません。"
        change = "同一basisの前回snapshotがないため、前回との差は比較できません。"

    must_happen = list(hypothesis.get("must_happen") or [])
    invalidation = list(hypothesis.get("invalidation_conditions") or [])
    thesis = (
        f"仮説の成立条件（達成確認ではありません）: {must_happen[0]}"
        if must_happen
        else "仮説の成立条件は未取得です。"
    )
    if invalidation:
        thesis += f" / 主な無効化条件: {invalidation[0]}"
    warning_count = sum(
        len(model[name].get("warnings") or [])
        for name in ("earnings_driver", "valuation", "expectations")
    )
    next_check = "FY2027 Q2の利益転換、最新株価、市場期待との比較を確認する。"
    return f"""
<section class="notice-card cockpit-judgment-summary" aria-labelledby="judgment-summary-title">
  <h2 id="judgment-summary-title">30秒で分かる判断材料</h2>
  <p><strong>前回からの変化:</strong> {_e(change_summary)}</p>
  <p><strong>情報の古さ:</strong> {_e(freshness)} / 全体状態: {_status(model.get("overall_status"))}</p>
  <p><strong>次に確認すること:</strong> {_e(next_check)} <a href="#market-expectations">市場期待の比較へ</a></p>
  <details>
    <summary>確認理由・数値basis・投資仮説の詳細</summary>
    <p><strong>今回の注目点（なぜ今日見る？）:</strong> {_e(focus)} <span class="muted">これは日付付き既存資料の確認理由であり、今日の新事実ではありません。</span></p>
    <p><strong>前回差の詳細:</strong> {_e(change)}</p>
    <p><strong>今の投資仮説:</strong> {_e(thesis)} / 警告 {_e(warning_count)}件</p>
  </details>
</section>
"""


def _decision_history_summary(model: Mapping[str, Any]) -> str:
    history = model["decision_history"]
    previous = history.get("previous_snapshot") or {}
    delta = _scenario_delta(model)
    comparable = all(
        value is not None
        for value in (
            delta.previous.eps,
            delta.current.eps,
            delta.previous.forward_per,
            delta.current.forward_per,
        )
    )
    if comparable:
        previous_decision = (
            f"{previous.get('as_of') or '日付不明'}時点の"
            f"{previous.get('scenario') or 'シナリオ不明'}判断です。"
        )
        per_change = float(delta.current.forward_per) - float(delta.previous.forward_per)
        current_change = (
            f"{delta.scenario_transition}。EPSは "
            f"{float(delta.previous.eps):,.2f}→{float(delta.current.eps):,.2f}円、"
            f"Forward PERは {float(delta.previous.forward_per):,.2f}→"
            f"{float(delta.current.forward_per):,.2f}倍（{per_change:+.2f}倍）です。"
        )
    else:
        previous_decision = "同一条件で比較できる前回判断を取得できません。"
        current_change = "前回との差は比較できません。現在値から過去値を推測しません。"

    return f"""
<div class="content-card cockpit-decision-history-summary">
  <p><strong>前回の判断:</strong> {_e(previous_decision)}</p>
  <p><strong>今回変わった点:</strong> {_e(current_change)}</p>
  <p><strong>次に確認すること:</strong> 最新株価と市場期待を確認し、前回判断を更新する必要があるか検討します。</p>
</div>
<details class="cockpit-decision-history-evidence">
  <summary>判断履歴の根拠IDを見る</summary>
  <ul>
    <li>最新判断の参照先: {_refs([history.get('latest_decision_ref')] if history.get('latest_decision_ref') else [])}</li>
    <li>現在の検討期間: {_refs([history.get('latest_episode_ref')] if history.get('latest_episode_ref') else [])}</li>
    <li>前回比較の参照先: {_refs([history.get('comparison_ref')] if history.get('comparison_ref') else [])}</li>
    <li>変更しない過去snapshot: {_refs([history.get('historical_snapshot_ref')] if history.get('historical_snapshot_ref') else [])}</li>
  </ul>
</details>
過去snapshotを現在のResearch / Valuationで書き換えません。
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
    warnings = [f"{section}: {warning}" for section in ("earnings_driver", "valuation", "expectations") for warning in (model[section].get("warnings") or [])]
    base_profit = earnings.get("base_profit") or {}
    base_eps = earnings.get("base_eps") or {}
    guidance = earnings.get("company_guidance") or {}
    base_profit_text = "取得できません" if base_profit.get("value") is None else f"{float(base_profit['value']):,.0f}百万円"
    base_eps_text = "取得できません" if base_eps.get("value") is None else f"{float(base_eps['value']):,.2f}円"
    guidance_text = "取得できません" if guidance.get("net_income_million_jpy") is None else f"{float(guidance['net_income_million_jpy']):,.0f}百万円"
    scenario_html = "".join([_scenario_card("Bear", valuation.get("bear") or {}), _scenario_card("Base", valuation.get("base") or {}), _scenario_card("Bull", valuation.get("bull") or {})])
    delta_html = _scenario_delta_html(model)
    expectation_html = _expectation_first_view(expectations)
    warning_html = _list(warnings, "重大warningなし")
    stale = freshness.get("stale_components") or []
    unknown = freshness.get("unknown_components") or []
    price_as_of = valuation.get("price_as_of") or "取得できません"
    warning_count = len(warnings)
    judgment_summary_html = _judgment_summary(model)
    decision_history_html = _decision_history_summary(model)
    first_view_html = render_first_view(
        LiveCockpitFirstView(
            company_name="ダイヘン",
            security_code=str(model.get("security_code") or "UNKNOWN"),
            freshness_html=_status(freshness.get("overall")),
            price_as_of=str(price_as_of),
            decision_delta_html=delta_html,
            expectation_html=expectation_html,
            thesis_health=str(health),
            hypothesis_status_html=_status(hypothesis.get("status")),
            warning_count=warning_count,
        )
    )

    return f"""---
layout: site
title: ダイヘン 投資判断コックピット
description: ダイヘンについて今日見る理由、利益予想、割安度、仮説、ポートフォリオ、前回判断を1画面で確認する
permalink: /decision-cockpit/daihen/
---

<p class="breadcrumb"><a href="{{{{ '/' | relative_url }}}}">Home</a> / ダイヘン 投資判断コックピット</p>

# 🎯 ダイヘン 投資判断コックピット

{judgment_summary_html}
<div class="notice-card"><strong>この画面は売買指示を生成しません。</strong><br>既存Canonical outputを読み取り専用でまとめ、判断に必要な不足・古さ・要確認事項を隠さず表示します。</div>
{first_view_html}

## ⚠ 先に確認する注意点
- 全体状態: {_status(model.get('overall_status'))}
- 情報鮮度: {_status(freshness.get('overall'))}
- 古いcomponent: {_e(', '.join(stale) if stale else 'なし')}
- 鮮度不明component: {_e(', '.join(unknown) if unknown else 'なし')}
{warning_html}

## 1. 利益予想 — なぜこのBase？
<div class="content-grid"><div class="content-card"><strong>Base純利益</strong><span>{_e(base_profit_text)}</span><span>{_status(earnings.get('status'))}</span></div><div class="content-card"><strong>Base EPS</strong><span>{_e(base_eps_text)}</span><span>対象: {_e(base_eps.get('target_fiscal_year') or '不明')}</span></div><div class="content-card"><strong>会社予想 純利益</strong><span>{_e(guidance_text)}</span><span>説明coverage: <code>{_e(earnings.get('explanation_coverage') or 'UNKNOWN')}</code></span></div></div>
根拠driver: {_refs(earnings.get('driver_refs'))}  
Source: {_refs(earnings.get('source_refs'))}
> `PARTIAL` は完全導出を意味しません。説明できない部分をAIが補完していません。

## 2. Bear / Base / Bull とForward PER
<div class="content-grid scenario-grid">{scenario_html}</div>
- 株価基準日: **{_e(valuation.get('price_as_of') or '取得できません')}**
- 対象年度: **{_e(valuation.get('target_fiscal_year') or '取得できません')}**
- 状態: {_status(valuation.get('status'))} / 鮮度: {_status(valuation.get('freshness'))}
- Source: {_refs(valuation.get('source_refs'))}
**株価情報が古い場合、現在の割安度として無警告では使用しません。**

<div id="market-expectations"></div>

## 3. 市場期待との差
状態: {_status(expectations.get('status'))}
<div class="table-scroll"><table>
<thead><tr><th>比較軸</th><th>FY2027 EPS</th><th>Consensusとの差</th></tr></thead>
<tbody>
<tr><th>External Consensus</th><td>{_e(f"{float(expectations['consensus_value']):,.2f}円" if expectations.get('consensus_value') is not None else "取得できません")}</td><td>基準</td></tr>
<tr><th>会社予想</th><td>{_e(f"{float(expectations['company_guidance_value']):,.2f}円" if expectations.get('company_guidance_value') is not None else "取得できません")}</td><td>{_e(f"{float(expectations['company_vs_consensus_pct']) * 100:+.1f}%" if expectations.get('company_vs_consensus_pct') is not None else "比較できません")}</td></tr>
<tr><th>Sado Base</th><td>{_e(f"{float(expectations['sado_base_value']):,.2f}円" if expectations.get('sado_base_value') is not None else "取得できません")}</td><td>{_e(f"{float(expectations['sado_vs_consensus_pct']) * 100:+.1f}%" if expectations.get('sado_vs_consensus_pct') is not None else "比較できません")}</td></tr>
</tbody></table></div>
- Consensus coverage: **{_e(expectations.get('analyst_count') or '不明')}名** / range **{_e(f"{float(expectations['consensus_low']):,.2f}〜{float(expectations['consensus_high']):,.2f}円" if expectations.get('consensus_low') is not None and expectations.get('consensus_high') is not None else "取得できません")}**
- Revision direction: **{_e(expectations.get('direction') or 'UNKNOWN')}**
- Company Guidance: {_refs([expectations.get('company_guidance_ref')] if expectations.get('company_guidance_ref') else [])}
- External Consensus: {_refs([expectations.get('external_consensus_ref')] if expectations.get('external_consensus_ref') else [])}
- Sado Base: {_refs([expectations.get('sado_base_ref')] if expectations.get('sado_base_ref') else [])}
- Latest Actual: {_refs([expectations.get('latest_actual_ref')] if expectations.get('latest_actual_ref') else [])}
**Consensusは二次データによる観測可能なproxyであり、市場全体の真の期待とは断定しません。取得できない場合もgap=0や「差なし」とは表示しません。**

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
{decision_history_html}

## 7. 次に確認する場所
- 利益予想の根拠: {_refs(earnings.get('driver_refs'))}
- 次checkpoint: {_refs(review.get('next_checkpoint_refs'))}
- 仮説source: {_refs(hypothesis.get('source_refs'))}
- 全source refs: {_refs(model.get('source_refs'))}

---
## 30秒チェック
この画面の最初のviewportと警告を見て、次を確認します。
1. なぜ今日ダイヘンを見るのか
2. 前回から何が変わったか
3. Base EPSの主な根拠は何か
4. Bear / Base / BullのForward PERはどうか
5. 市場期待データは利用可能か
6. 何が起きたら仮説が崩れるか
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
    target.write_text(page_content(model), encoding="utf-8")

    home = SITE / "index.md"
    home_text = home.read_text(encoding="utf-8")
    marker = "<!-- daihen-cockpit-link -->"
    block = f"{marker}\n- [ダイヘン 投資判断コックピットを開く]({{{{ '/decision-cockpit/daihen/' | relative_url }}}})\n"
    if marker not in home_text:
        home.write_text(home_text.rstrip() + "\n\n" + block, encoding="utf-8")


if __name__ == "__main__":
    build()
