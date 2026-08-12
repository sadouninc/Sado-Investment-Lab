from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / ".github" / "pages" / "market-phase.js").read_text(encoding="utf-8")


def test_mobile_market_phase_uses_summary_before_full_matrix() -> None:
    assert 'matchMedia("(max-width: 700px)")' in JS
    assert 'summary.id = "phase-mobile-correlation-summary"' in JS
    assert "相関上位" in JS
    assert "相関下位" in JS
    assert "選択銘柄の相関" in JS
    assert "40銘柄の完全相関行列を表示" in JS


def test_mobile_market_phase_keeps_full_matrix_as_progressive_disclosure() -> None:
    assert 'document.createElement("details")' in JS
    assert 'details.append(heatmap)' in JS
    assert "renderHeatmap();" in JS


def test_mobile_market_phase_does_not_change_canonical_payload() -> None:
    assert "data.correlation.pearson" in JS
    assert "data.top_positive_pairs" in JS
    assert "data.top_negative_pairs" in JS
    assert "data.correlation =" not in JS
    assert "data.symbols =" not in JS
