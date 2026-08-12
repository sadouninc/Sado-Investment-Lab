from __future__ import annotations

from dataclasses import dataclass
import html


@dataclass(frozen=True)
class LiveCockpitFirstView:
    company_name: str
    security_code: str
    freshness_html: str
    price_as_of: str
    decision_delta_html: str
    expectation_html: str
    thesis_health: str
    hypothesis_status_html: str
    warning_count: int


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_first_view(view: LiveCockpitFirstView) -> str:
    """Render the shared 30-second Live Cockpit hierarchy.

    All investment semantics are injected by the company-specific adapter.
    This shell only owns structure and presentation order; it must not infer
    scenario choice, market-expectation gaps, warnings, or trade actions.
    """
    company_name = view.company_name.strip() or "対象企業を取得できません"
    security_code = view.security_code.strip() or "UNKNOWN"
    price_as_of = view.price_as_of.strip() or "取得できません"
    thesis_health = view.thesis_health.strip() or "取得できません"
    warning_count = max(int(view.warning_count), 0)

    return f"""<div class=\"content-grid cockpit-first-view\">
  <div class=\"content-card cockpit-identity-summary\"><strong>{_e(company_name)} / {_e(security_code)}</strong><span>情報鮮度: {view.freshness_html}</span><span class=\"muted\">株価基準日: {_e(price_as_of)}</span></div>
  {view.decision_delta_html}
  {view.expectation_html}
  <div class=\"content-card cockpit-thesis-summary\"><strong>今の投資仮説は？ / Warning / Thesis Health</strong><span>Health: <code>{_e(thesis_health)}</code></span><span>仮説状態: {view.hypothesis_status_html}</span><span>確認すべきwarning: {_e(warning_count)}件</span></div>
</div>
<div class=\"content-card cockpit-decision-loop\">
  <strong>判断ループ — 次にどこを見る？</strong>
  <p>意味を確認 → 根拠を掘る → 売買前のPF影響を確認 → 判断・取引を記録、の順に既存Canonical画面へ進みます。</p>
  <div class=\"codex-action-row\">
    <a class=\"codex-action codex-action--secondary\" href=\"{{{{ '/concepts/investment-decision-cockpit/' | relative_url }}}}\">Cockpitの見方を確認</a>
    <a class=\"codex-action codex-action--secondary\" href=\"{{{{ '/companies/' | relative_url }}}}\">企業研究・Evidenceを見る</a>
    <a class=\"codex-action codex-action--primary\" href=\"{{{{ '/risk-preflight/' | relative_url }}}}\">売買前のPF影響を確認</a>
    <a class=\"codex-action codex-action--secondary\" href=\"{{{{ '/trade-journal/' | relative_url }}}}\">判断・取引の記録を見る</a>
  </div>
  <span class=\"muted\">Decision Snapshotのbackend contractは既存ですが、専用Pages routeはまだ接続されていません。存在しない画面を生成済みとは扱いません。</span>
</div>"""
