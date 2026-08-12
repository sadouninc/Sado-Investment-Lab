from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / ".github" / "pages" / "book.css").read_text(encoding="utf-8")


def css_block(selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS, re.DOTALL)
    assert match, f"missing CSS block: {selector}"
    return match.group(1)


def test_trade_filter_controls_stay_inside_grid_cells() -> None:
    label = css_block(".trade-filters label")
    controls = css_block(".trade-filters select, .trade-filters button")
    assert "min-width: 0" in label
    assert "width: 100%" in controls


def test_trade_filters_collapse_to_one_column_on_narrow_mobile() -> None:
    match = re.search(r"@media \(max-width: 420px\)\s*\{(.*)\}\s*$", CSS, re.DOTALL)
    assert match, "missing 420px mobile breakpoint"
    narrow = match.group(1)
    trade_filters = re.search(r"\.trade-filters\s*\{([^}]*)\}", narrow, re.DOTALL)
    assert trade_filters, "missing narrow .trade-filters override"
    assert "grid-template-columns: 1fr" in trade_filters.group(1)
