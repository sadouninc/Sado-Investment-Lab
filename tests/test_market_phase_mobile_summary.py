from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / ".github" / "pages" / "market-phase.js").read_text(encoding="utf-8")


def test_market_phase_exposes_real_date_range_and_ticks() -> None:
    assert 'range.textContent = `表示期間: ${formatDay(days[0])} — ${formatDay(days[days.length - 1])}`;' in JS
    assert 'class="phase-date-tick"' in JS
    assert "tickIndexes" in JS


def test_market_phase_uses_collision_safe_direct_series_labels() -> None:
    assert "function stackLabelColumn" in JS
    assert "function layoutEndpointLabels" in JS
    assert "const twoColumns = rows.length > 18;" in JS
    assert 'class="phase-line-label"' in JS
    assert 'class="phase-label-leader"' in JS
    assert 'class="phase-endpoint-marker"' in JS
    assert 'data-phase-code=' in JS
    assert "compactSymbolLabel" in JS
    assert "phase-series-choice" in JS
    assert 'input type="checkbox"' in JS
    assert "index % 5" not in JS


def test_many_series_reserve_plot_space_for_labels() -> None:
    assert "const plotRight = series.length > 18 ? 690 : 820;" in JS
    assert "labelX: 718" in JS
    assert "labelX: 858" in JS
    assert "labelY" in JS


def test_selected_correlation_is_primary_and_fail_closed() -> None:
    assert "選択銘柄内の相関" in JS
    assert "相関を比較するには2銘柄以上選択してください" in JS
    assert "データ不足を0相関として扱いません" in JS
    assert 'const value = row[right];' in JS
    assert 'return value == null ? null : Number(value);' in JS


def test_comparison_and_discovery_are_separate_views() -> None:
    assert 'target.id = "phase-selected-pairs"' in JS
    assert 'target.id = "phase-related-discovery"' in JS
    assert "関連銘柄を探す" in JS
    assert "比較中の銘柄とは分離し" in JS
    assert '!selectedCodes.has(other)' in JS


def test_chart_and_heatmap_share_one_selection_state() -> None:
    assert "let selectedCodes = new Set();" in JS
    assert "data.symbols.filter(item => selectedCodes.has(item.code))" in JS
    assert "const codes = [...selectedCodes];" in JS
    assert "renderAllSelectionViews" in JS


def test_mobile_market_phase_keeps_progressive_explanation() -> None:
    assert 'matchMedia("(max-width: 700px)")' in JS
    assert 'summary.id = "phase-mobile-correlation-summary"' in JS
    assert "相関の見方" in JS
    assert "個別銘柄の相関を確認" in JS


def test_selected_correlation_explains_direction() -> None:
    assert 'const correlationDirection = value => value >= 0 ? "同方向" : "逆方向";' in JS
    assert '["方向", row => correlationDirection(row.correlation)]' in JS


def test_market_phase_does_not_change_canonical_payload() -> None:
    assert "data.correlation.pearson" in JS
    assert "data.top_positive_pairs" in JS
    assert "data.top_negative_pairs" in JS
    assert "data.correlation =" not in JS
    assert "data.symbols =" not in JS
