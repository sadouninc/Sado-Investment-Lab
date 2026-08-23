"""Build owner-facing Market Compass Pages projection for #586 B4."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from scripts.market_compass_state_evaluator import (
    evaluate_market_compass_universe_states,
)
from scripts.market_compass_universe_projection import (
    project_market_compass_universe,
)

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site-src"
OUTPUT_FILE = SITE / "research" / "market-compass" / "index.md"

PORTFOLIO_FILE = ROOT / "data" / "portfolio" / "current.json"
SUBSECTOR_EVIDENCE_FILE = ROOT / "data" / "fixtures" / "intraday-subsector-flow-v1.json"
SUBSECTOR_MAPPING_FILE = ROOT / "data" / "masters" / "security-subsector-mapping-v1.json"

STATE_JAPANESE_LABELS = {
    "AVOID": "危険回避 (AVOID)",
    "WATCH": "要観察 (WATCH)",
    "BUY_WATCH": "買付打診 (BUY WATCH)",
    "REENTRY_READY": "再参入準備 (RE-ENTRY READY)",
}

INTEGRITY_JAPANESE_LABELS = {
    "PASS": "適合 (PASS)",
    "REVIEW": "要確認 (REVIEW)",
    "FAIL": "不合格 (FAIL)",
    "UNKNOWN": "不明 (UNKNOWN)",
}

AUTHORITY_JAPANESE_LABELS = {
    "VERIFIED": "確認済み (VERIFIED)",
    "PROVISIONAL": "仮確定 (PROVISIONAL)",
    "MISMATCH": "不一致 (MISMATCH)",
    "STALE": "期限切れ (STALE)",
    "STALE_RELATIVE_TO_EXIT": "売却確定後更新待ち (STALE_RELATIVE_TO_EXIT)",
    "UNKNOWN": "不明 (UNKNOWN)",
}

# Initial confirmed exits from W33 as defined in #586 B4
DEFAULT_REENTRY_WATCH_CANDIDATES = {
    "candidates": [
        {"security_code": "3778", "name": "さくらインターネット", "exit_date": "2026-08-14"},
        {"security_code": "4588", "name": "オンコリスバイオファーマ", "exit_date": "2026-08-14"},
        {"security_code": "5801", "name": "古河電気工業", "exit_date": "2026-08-14"},
        {"security_code": "6376", "name": "日機装", "exit_date": "2026-08-14"},
        {"security_code": "6702", "name": "富士通", "exit_date": "2026-08-14"},
    ]
}


def load_json_file(path: Path) -> dict[str, Any] | None:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def get_default_portfolio() -> dict[str, Any]:
    loaded = load_json_file(PORTFOLIO_FILE)
    if loaded is not None:
        return loaded
    return {
        "schema_version": 1,
        "as_of": "2026-08-08",
        "verification_status": "PROVISIONAL",
        "positions": [],
    }


def get_default_subsector_evidence() -> dict[str, dict[str, Any]]:
    loaded = load_json_file(SUBSECTOR_EVIDENCE_FILE)
    if loaded and isinstance(loaded, dict) and "subsector_evidence_by_security" in loaded:
        return loaded["subsector_evidence_by_security"]
    return {}


def get_default_subsector_mapping() -> dict[str, Any] | None:
    return load_json_file(SUBSECTOR_MAPPING_FILE)


def generate_market_compass_projection(
    portfolio: dict[str, Any] | None = None,
    reentry_watch: dict[str, Any] | None = None,
    subsector_evidence: dict[str, dict[str, Any]] | None = None,
    subsector_mapping: dict[str, Any] | None = None,
    evidence_as_of: str = "2026-08-21",
    expected_taxonomy_version: str = "v1",
) -> dict[str, Any]:
    port = portfolio if portfolio is not None else get_default_portfolio()
    reentry = reentry_watch if reentry_watch is not None else DEFAULT_REENTRY_WATCH_CANDIDATES
    evidence = subsector_evidence if subsector_evidence is not None else get_default_subsector_evidence()
    mapping = subsector_mapping if subsector_mapping is not None else get_default_subsector_mapping()

    universe = project_market_compass_universe(
        port,
        reentry,
        evidence,
        evidence_as_of=evidence_as_of,
        expected_taxonomy_version=expected_taxonomy_version,
        mapping=mapping,
    )

    return evaluate_market_compass_universe_states(universe)


def _render_state_badge(state: str | None, evaluation_status: str | None = None) -> str:
    if evaluation_status == "UNKNOWN" or state is None:
        return '<span class="mc-badge mc-badge-unknown">未評価 / 不明 (UNKNOWN)</span>'
    label = STATE_JAPANESE_LABELS.get(state, f"{state}")
    css_class = f"mc-badge-{state.lower().replace('_', '-')}"
    return f'<span class="mc-badge {css_class}">{html.escape(label)}</span>'


def _render_integrity_badge(integrity: str | None) -> str:
    val = (integrity or "UNKNOWN").upper()
    label = INTEGRITY_JAPANESE_LABELS.get(val, val)
    css_class = f"mc-integrity-{val.lower()}"
    return f'<span class="mc-integrity-badge {css_class}">{html.escape(label)}</span>'


def _render_authority_badge(status: str | None) -> str:
    val = status or "UNKNOWN"
    label = AUTHORITY_JAPANESE_LABELS.get(val, val)
    css_class = f"mc-authority-{val.lower().replace('_', '-')}"
    return f'<span class="mc-authority-badge {css_class}">{html.escape(label)}</span>'


def _render_score_value(val: float | int | None) -> str:
    if val is None:
        return '<span class="mc-score-unknown">UNKNOWN</span>'
    return f"<strong>{val}</strong>"


def _render_security_card(item: dict[str, Any], is_current_holding: bool) -> str:
    code = html.escape(str(item.get("security_code", "")))
    name = html.escape(str(item.get("security_name", "") or "名称未設定"))
    state = item.get("market_compass_state")
    eval_status = item.get("evaluation_status")
    integrity = item.get("fundamental_integrity")
    authority = item.get("portfolio_authority_status")
    score_total = item.get("score_total")
    scores = item.get("scores") or {}
    position = item.get("position") or {}
    reentry = item.get("reentry_candidate") or {}

    quantity = position.get("quantity") if is_current_holding else None
    pos_type = position.get("position_type") if is_current_holding else None
    exit_date = reentry.get("exit_date") if not is_current_holding else None

    lines: list[str] = []
    lines.append('<article class="mc-card">')

    # Card header: Security Code & Name + Badges
    lines.append('  <div class="mc-card-header">')
    lines.append('    <div class="mc-card-title">')
    lines.append(f'      <span class="mc-code">{code}</span>')
    lines.append(f'      <h3 class="mc-name">{name}</h3>')
    lines.append("    </div>")
    lines.append('    <div class="mc-badges">')
    lines.append(f"      {_render_state_badge(state, eval_status)}")
    lines.append(f"      {_render_integrity_badge(integrity)}")
    lines.append("    </div>")
    lines.append("  </div>")

    # Card meta: Position/Candidate details + Authority
    lines.append('  <div class="mc-card-meta">')
    if is_current_holding:
        pos_type_str = f" ({html.escape(str(pos_type))})" if pos_type else ""
        qty_str = f"保有数: {quantity}株{pos_type_str}" if quantity is not None else "現在保有"
        lines.append(f'    <span class="mc-meta-item">{qty_str}</span>')
    else:
        exit_str = f"売却確定日: {html.escape(str(exit_date))}" if exit_date else "売却済み候補"
        lines.append(f'    <span class="mc-meta-item">{exit_str}</span>')

    if authority:
        lines.append(f'    <span class="mc-meta-item">権限状態: {_render_authority_badge(authority)}</span>')
    lines.append("  </div>")

    # Warning banner if REENTRY_READY
    if state == "REENTRY_READY":
        lines.append('  <div class="mc-warning-banner">')
        lines.append('    <strong>⚠️ RE-ENTRY READY (再参入準備)</strong>')
        lines.append('    <p>スクリーニング条件への合致を示しています。実際の購入決定や売買発注を意味するものではありません。</p>')
        lines.append("  </div>")

    # Summary score bar
    lines.append('  <div class="mc-score-summary">')
    lines.append(f'    <span class="mc-score-label">総合スコア:</span>')
    lines.append(f'    <span class="mc-score-total">{_render_score_value(score_total)}</span>')
    lines.append("  </div>")

    # Collapsible Details for Score Components and Evidence (Progressive Disclosure)
    lines.append('  <details class="mc-card-details">')
    lines.append("    <summary>スコア内訳・詳細エビデンス表示</summary>")
    lines.append('    <div class="mc-details-body">')
    lines.append('      <ul class="mc-score-breakdown">')
    lines.append(f'        <li><span>過度下落 (Excess Decline):</span> {_render_score_value(scores.get("excess_decline"))}</li>')
    lines.append(f'        <li><span>バリュエーションリセット (Valuation Reset):</span> {_render_score_value(scores.get("valuation_reset"))}</li>')
    lines.append(f'        <li><span>ファンダメンタル強度 (Fundamental Strength):</span> {_render_score_value(scores.get("fundamental_strength"))}</li>')
    lines.append(f'        <li><span>リスク安定化 (Risk Stabilization):</span> {_render_score_value(scores.get("risk_stabilization"))}</li>')
    lines.append("      </ul>")

    intraday = item.get("intraday_evidence") or {}
    if intraday:
        ev_status = html.escape(str(intraday.get("status", "UNKNOWN")))
        ev_reason = html.escape(str(intraday.get("reason", "N/A")))
        lines.append('      <div class="mc-evidence-info">')
        lines.append(f'        <small>日中エビデンス状態: {ev_status} (理由: {ev_reason})</small>')
        lines.append("      </div>")

    lines.append("    </div>")
    lines.append("  </details>")

    lines.append("</article>")
    return "\n".join(lines)


def render_market_compass_page(evaluated_universe: dict[str, Any], boj_status: str = "GREEN") -> str:
    as_of = html.escape(str(evaluated_universe.get("as_of", "2026-08-21")))

    current_holdings = evaluated_universe.get("current_holdings", [])
    reentry_watch = evaluated_universe.get("reentry_watch", [])
    membership_unknown = evaluated_universe.get("membership_unknown", [])

    page: list[str] = []
    page.append("---")
    page.append("layout: site")
    page.append("title: Market Compass (市場コンパス)")
    page.append("description: 市場の先行リスク変化・保有株の危険管理・売却済み優良株のRe-entry候補をread-only投影")
    page.append("permalink: /research/market-compass/")
    page.append("---")
    page.append("")

    # Custom styles inline for mobile density (390px/320px support) & clear visual hierarchy
    page.append("<style>")
    page.append("""
.mc-container { max-width: 100%; box-sizing: border-box; word-break: break-word; }
.mc-header { margin-bottom: 1.5rem; }
.mc-breadcrumb { font-size: 0.85rem; color: var(--codex-text-muted, #666); margin-bottom: 0.5rem; }
.mc-section { margin-top: 2rem; margin-bottom: 2rem; }
.mc-section-title { font-size: 1.25rem; border-bottom: 2px solid var(--codex-border-emphasis, #a79678); padding-bottom: 0.3rem; margin-bottom: 1rem; }
.mc-grid { display: grid; grid-template-columns: 1fr; gap: 1rem; }
@media (min-width: 768px) { .mc-grid { grid-template-columns: repeat(2, 1fr); } }
.mc-card { background: var(--codex-surface-panel, #fbf8f1); border: 1px solid var(--codex-border-subtle, #d4c8b6); border-radius: 0.5rem; padding: 1rem; box-shadow: 0 2px 4px rgba(0,0,0,0.04); }
.mc-card-header { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.5rem; }
.mc-card-title { display: flex; align-items: center; gap: 0.5rem; }
.mc-code { font-weight: bold; background: var(--codex-border-subtle, #e5ded0); padding: 0.1rem 0.4rem; border-radius: 0.2rem; font-size: 0.85rem; }
.mc-name { margin: 0; font-size: 1.05rem; }
.mc-badges { display: flex; flex-wrap: wrap; gap: 0.3rem; }
.mc-badge { display: inline-block; padding: 0.15rem 0.5rem; font-size: 0.75rem; font-weight: bold; border-radius: 0.25rem; }
.mc-badge-avoid { background-color: #fde8e8; color: #9b1c1c; border: 1px solid #f8b4b4; }
.mc-badge-watch { background-color: #fef08a; color: #713f12; border: 1px solid #fde047; }
.mc-badge-buy-watch { background-color: #e0f2fe; color: #075985; border: 1px solid #bae6fd; }
.mc-badge-reentry-ready { background-color: #dcfce7; color: #166534; border: 1px solid #86efac; }
.mc-badge-unknown { background-color: #f3f4f6; color: #4b5563; border: 1px solid #e5e7eb; }
.mc-integrity-badge { display: inline-block; padding: 0.1rem 0.4rem; font-size: 0.7rem; border-radius: 0.2rem; }
.mc-integrity-pass { background: #f0fdf4; color: #15803d; }
.mc-integrity-review { background: #fffbeb; color: #b45309; }
.mc-integrity-fail { background: #fef2f2; color: #b91c1c; }
.mc-integrity-unknown { background: #f9fafb; color: #6b7280; }
.mc-authority-badge { font-size: 0.75rem; padding: 0.1rem 0.3rem; border-radius: 0.2rem; background: #f3f4f6; color: #374151; }
.mc-card-meta { font-size: 0.8rem; color: var(--codex-text-muted, #555); margin-bottom: 0.5rem; display: flex; flex-wrap: wrap; gap: 0.8rem; }
.mc-warning-banner { background-color: #fff8f6; border-left: 4px solid #dc2626; padding: 0.5rem 0.75rem; font-size: 0.8rem; margin: 0.5rem 0; border-radius: 0.2rem; }
.mc-warning-banner p { margin: 0.2rem 0 0 0; color: #991b1b; }
.mc-score-summary { display: flex; align-items: center; justify-content: space-between; font-size: 0.9rem; border-top: 1px dashed var(--codex-border-subtle, #d4c8b6); padding-top: 0.4rem; margin-top: 0.4rem; }
.mc-score-total { font-size: 1.1rem; }
.mc-card-details summary { font-size: 0.8rem; cursor: pointer; color: var(--codex-accent-brass, #8c6f3d); margin-top: 0.4rem; }
.mc-details-body { font-size: 0.8rem; margin-top: 0.4rem; padding-top: 0.4rem; border-top: 1px dotted var(--codex-border-subtle, #ccc); }
.mc-score-breakdown { list-style: none; padding-left: 0; margin: 0 0 0.4rem 0; }
.mc-score-breakdown li { display: flex; justify-content: space-between; margin-bottom: 0.2rem; }
.mc-macro-panel { background: var(--codex-surface-panel, #fbf8f1); border: 1px solid var(--codex-border-emphasis, #a79678); border-radius: 0.5rem; padding: 1rem; margin-bottom: 1.5rem; }
.mc-macro-status { font-weight: bold; padding: 0.2rem 0.6rem; border-radius: 0.3rem; display: inline-block; }
.mc-macro-green { background-color: #dcfce7; color: #166534; }
.mc-macro-orange { background-color: #ffedd5; color: #9a3412; }
.mc-macro-red { background-color: #fee2e2; color: #991b1b; }
.mc-macro-unknown { background-color: #f3f4f6; color: #4b5563; }
.mc-notice-box { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 0.4rem; padding: 0.8rem; font-size: 0.85rem; margin-bottom: 1rem; }
""")
    page.append("</style>")
    page.append("")

    page.append('<div class="mc-container">')

    # Breadcrumb & Page Header
    page.append('  <p class="mc-breadcrumb"><a href="{{ \'/\' | relative_url }}">Home</a> / Research / Market Compass</p>')
    page.append('  <div class="mc-header">')
    page.append('    <h1>🧭 Market Compass (市場コンパス v0.1)</h1>')
    page.append(f'    <p class="mc-meta">観測基準日: <strong>{as_of}</strong> | Authority: <code>READ_ONLY_EVIDENCE</code></p>')
    page.append('  </div>')

    # Macro Risk Context Section (#512 BOJ Early Warning)
    page.append('  <section class="mc-section">')
    page.append('    <h2 class="mc-section-title">1. マクロリスク状況 (BOJ Early Warning #512)</h2>')
    page.append('    <div class="mc-macro-panel">')

    boj_upper = (boj_status or "GREEN").upper()
    boj_label_map = {
        "GREEN": "GREEN (緑 / 観測非活性)",
        "ORANGE": "ORANGE (橙 / シャドー観測)",
        "RED": "RED (赤 / アクティブ観測)",
        "UNKNOWN": "UNKNOWN (不明)",
    }
    boj_label = boj_label_map.get(boj_upper, boj_upper)
    css_boj = f"mc-macro-{boj_upper.lower()}"

    page.append('      <p>日銀政策金利・マクロ先行リスク指標 (BOJ Sensor State):')
    page.append(f'        <span class="mc-macro-status {css_boj}">{html.escape(boj_label)}</span>')
    page.append('      </p>')
    page.append('      <small style="color: var(--codex-text-muted, #555);">')
    page.append('        ※ <strong>重要ルール:</strong> <code>BOJ RED != 全銘柄AVOID</code>、<code>RE-ENTRY READY != BOJリスク消失</code>。')
    page.append('        BOJシグナルはポートフォリオ全体のマクロ環境コンテキストであり、個別銘柄のAVOID/BUY判定を単体で生成しません。')
    page.append('      </small>')
    page.append('    </div>')
    page.append('  </section>')

    # Section A: Current Holdings (現在保有の危険管理)
    page.append('  <section class="mc-section">')
    page.append('    <h2 class="mc-section-title">2. 現在保有の危険管理 (Current Holdings)</h2>')
    page.append('    <div class="mc-notice-box">')
    page.append('      <strong>保有ポジション状態 (Canonical Portfolio):</strong> <code>data/portfolio/current.json</code>')
    has_provisional = any(
        item.get("portfolio_authority_status") == "PROVISIONAL"
        for item in current_holdings + membership_unknown
    )
    if has_provisional:
        page.append('      <p style="color: #b45309; margin: 0.3rem 0 0 0;">⚠️ <strong>注意:</strong> 現在のポートフォリオ状態は <code>PROVISIONAL</code> (仮確定) です。最新の約定明細照合まで <code>VERIFIED</code> として扱われません。</p>')
    page.append('    </div>')

    if current_holdings:
        page.append('    <div class="mc-grid">')
        for item in current_holdings:
            page.append(_render_security_card(item, is_current_holding=True))
        page.append('    </div>')
    else:
        page.append('    <p>現在保有中の銘柄はありません。</p>')
    page.append('  </section>')

    # Section B: Re-entry Watch (売却済み・再評価候補)
    page.append('  <section class="mc-section">')
    page.append('    <h2 class="mc-section-title">3. 売却済み・再評価候補 (Re-entry Watch)</h2>')
    page.append('    <div class="mc-notice-box">')
    page.append('      <p style="margin:0;">※ <strong>Re-entry Watch</strong> は「買い推奨」ではありません。売却確定後にファンダメンタルズ整合性が維持されている優良銘柄を、再評価候補として保持する read-only 観察面です。現在保有銘柄とは明確に分離して表示されます。</p>')
    page.append('    </div>')

    if reentry_watch:
        page.append('    <div class="mc-grid">')
        for item in reentry_watch:
            page.append(_render_security_card(item, is_current_holding=False))
        page.append('    </div>')
    else:
        page.append('    <p>Re-entry Watch 候補銘柄はありません。</p>')
    page.append('  </section>')

    # Section C: Membership Unknown / Data Quality & Semantics
    page.append('  <section class="mc-section">')
    page.append('    <h2 class="mc-section-title">4. 未確定状態・データ品質と原則 (Data Quality & Fail-Closed)</h2>')

    if membership_unknown:
        page.append('    <div class="mc-notice-box" style="border-color: #f87171;">')
        page.append('      <strong>未確定銘柄 (Membership UNKNOWN):</strong>')
        page.append('      <p>以下の銘柄はポートフォリオ権限不確定または売却確定日照合待ちのため、Fail-Closed セマンティクスにより <code>BUY_WATCH</code> / <code>REENTRY_READY</code> に昇格せず <code>UNKNOWN</code> として保護されています。</p>')
        page.append('      <ul>')
        for item in membership_unknown:
            c = html.escape(str(item.get("security_code")))
            n = html.escape(str(item.get("security_name", "名称不明")))
            m = html.escape(str(item.get("membership")))
            page.append(f'        <li>銘柄 {c} ({n}) - 区分: <code>{m}</code></li>')
        page.append('      </ul>')
        page.append('    </div>')

    page.append('    <div class="mc-notice-box">')
    page.append('      <h3>🔒 Read-Only & Fail-Closed セマンティクス保証</h3>')
    page.append('      <ul>')
    page.append('        <li><strong>同一基準日照合:</strong> 株価とベンチマークの下落率比較は同一終値ベースで行います。</li>')
    page.append('        <li><strong>予想PER非補完:</strong> Forward PERが取得不能な場合、Valuation Reset スコアは <code>UNKNOWN</code> とし、推定値補完を行いません。</li>')
    page.append('        <li><strong>UNKNOWN保護:</strong> <code>UNKNOWN</code> スコアは 0 や中立値に変換されず、条件非充足として安全側に倒れます。</li>')
    page.append('        <li><strong>非推奨・非発注:</strong> 自動売買推奨（BUY/SELL/HOLD）、注文発注、ポートフォリオ状態の自動変更は一切行いません。</li>')
    page.append('      </ul>')
    page.append('    </div>')
    page.append('  </section>')

    page.append('</div>')
    return "\n".join(page) + "\n"


def build() -> None:
    evaluated = generate_market_compass_projection()
    content = render_market_compass_page(evaluated, boj_status="GREEN")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    build()
