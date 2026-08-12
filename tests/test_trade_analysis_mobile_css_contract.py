from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / ".github" / "pages" / "book.css").read_text(encoding="utf-8")


def test_trade_filter_controls_stay_inside_grid_cells() -> None:
    assert ".trade-filters label" in CSS
    assert "min-width: 0" in CSS
    assert ".trade-filters select" in CSS
    assert "width: 100%" in CSS


def test_trade_filters_collapse_to_one_column_on_narrow_mobile() -> None:
    assert "@media (max-width: 420px)" in CSS
    narrow = CSS.split("@media (max-width: 420px)", 1)[1]
    assert ".trade-filters" in narrow
    assert "grid-template-columns: 1fr" in narrow
