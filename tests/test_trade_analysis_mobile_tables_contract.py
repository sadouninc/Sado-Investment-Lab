from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / ".github" / "pages" / "book.css").read_text(encoding="utf-8")


def test_mobile_group_table_keeps_five_primary_columns_without_horizontal_scroll() -> None:
    assert "#ta-group-table .sortable-table" in CSS
    assert "min-width: 0" in CSS
    assert "table-layout: fixed" in CSS
    assert "font-size: 13px" in CSS
    assert "#ta-group-table th:nth-child(6)" in CSS
    assert "display: none" in CSS


def test_mobile_trade_table_prevents_vertical_security_name_wrapping() -> None:
    assert "#ta-trades .sortable-table td:nth-child(3)" in CSS
    assert "white-space: nowrap" in CSS
    assert "text-overflow: ellipsis" in CSS
    assert "overflow: hidden" in CSS


def test_mobile_trade_table_hides_secondary_columns() -> None:
    for column in (4, 6, 7, 8, 10, 11):
        assert f"#ta-trades th:nth-child({column})" in CSS
