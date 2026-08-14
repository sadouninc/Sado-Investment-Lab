from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / ".github" / "pages" / "book.css").read_text(encoding="utf-8")
JS = (ROOT / ".github" / "pages" / "trade-analysis.js").read_text(encoding="utf-8")


def test_mobile_group_table_keeps_five_primary_columns_without_horizontal_scroll() -> None:
    assert "#ta-group-table .sortable-table" in CSS
    assert "min-width: 0" in CSS
    assert "table-layout: fixed" in CSS
    assert "font-size: 13px" in CSS
    assert "#ta-group-table th:nth-child(6)" in CSS
    assert "display: none" in CSS


def test_mobile_trade_representation_uses_semantic_card_order() -> None:
    assert 'window.matchMedia("(max-width: 700px)")' in JS
    assert "renderMobileTrades" in JS
    assert 'data-trade-mobile-card' in JS
    security = JS.index('${escapeHtml(t.security_code)} ${escapeHtml(t.security_name)}')
    context = JS.index('${escapeHtml(t.close_date)} ・ ${escapeHtml(t.account_type)} ・ ${escapeHtml(t.position_side)}')
    pnl = JS.index('${money(t.net_pnl)}')
    assert security < context < pnl


def test_mobile_trade_representation_reuses_shared_primitives() -> None:
    assert 'class="content-card" data-trade-mobile-card' in JS
    assert 'class="${t.net_pnl < 0 ? "loss" : "gain"}"' in JS
    assert "trade-analysis-mobile" not in CSS


def test_desktop_trade_table_remains_available_and_sortable() -> None:
    assert "renderDesktopTrades" in JS
    assert 'class="sortable-table"' in JS
    assert 'data-sort="${key}"' in JS
    assert 'mobileQuery.addEventListener("change"' in JS
