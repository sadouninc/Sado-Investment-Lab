from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / ".github" / "pages" / "enrich_home_today.py"
CSS_PATH = ROOT / "assets" / "images" / "home-os-map.css"
spec = importlib.util.spec_from_file_location("enrich_home_today", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def dataset() -> dict:
    return {
        "as_of": "2026-08-11",
        "data_quality": {"status": "PARTIAL", "completeness_label": "6 / 8"},
        "source_status": [
            {"name": "market", "status": "OK", "as_of": "2026-08-11"},
            {"name": "sector_rotation", "status": "OK", "as_of": "2026-08-11"},
        ],
        "sector_rotation": {
            "as_of": "2026-08-11",
            "taxonomy": "TOPIX-17",
            "sectors": [
                {
                    "id": "sector:a",
                    "name": "電機・精密",
                    "previous_state": "COLD",
                    "state": "WARMING",
                    "flow_score": 55.0,
                },
                {
                    "id": "sector:b",
                    "name": "機械",
                    "previous_state": "WARMING",
                    "state": "INFLOW",
                    "flow_score": 61.0,
                },
                {
                    "id": "sector:c",
                    "name": "銀行",
                    "previous_state": "HOT",
                    "state": "HOT",
                    "flow_score": 72.0,
                },
            ],
        },
        "warnings": ["portfolio source is stale: fixture"],
    }


def portfolio_dataset(*, status: str = "OK") -> dict:
    payload = dataset()
    payload["source_status"].append(
        {
            "name": "portfolio",
            "status": status,
            "as_of": "2026-08-12" if status != "STALE" else "2026-08-01",
            "source_reference": "data/canonical/portfolio-state.json",
            "reason": "fixture stale" if status == "STALE" else None,
        }
    )
    payload["portfolio"] = {
        "positions": [
            {"security_code": "6622", "name": "ダイヘン", "quantity": 100},
            {"security_code": "3110", "name": "日東紡", "quantity": 200},
        ]
    }
    return payload


def home_text() -> str:
    return (
        "before\n"
        + module.STATUS_SECTION_START
        + "\nold status\n  </section>\n\n"
        + module.STATUS_SECTION_END
        + "\nafter\n"
    )


def test_render_uses_existing_canonical_status_without_mutating_input():
    payload = dataset()
    before = deepcopy(payload)
    rendered = module.render_status_section(payload, expected_as_of=date(2026, 8, 11))
    assert "Morning Dataset: 一部情報不足 / PARTIAL" in rendered
    assert "市場データ" in rendered
    assert "Sector Rotation" in rendered
    assert "WARMING 1件 / INFLOW 1件" in rendered
    assert "portfolio source is stale: fixture" in rendered
    assert "順位や推奨はHomeで生成しません" in rendered
    assert payload == before


def test_heatmap_projects_canonical_state_and_transition_without_recalculation():
    payload = dataset()
    before = deepcopy(payload)
    rendered = module.render_sector_heatmap(payload)

    assert "市場・テーマの動き" in rendered
    assert "電機・精密" in rendered
    assert "COLD → WARMING" in rendered
    assert "↗ 初動" in rendered
    assert "WARMING → INFLOW" in rendered
    assert "⇧ 流入へ移行" in rendered
    assert "HOT → HOT" in rendered
    assert "→ 継続" in rendered
    assert "as of: 2026-08-11" in rendered
    assert "/market-analysis/2026/sector-rotation/" in rendered
    assert 'data-sector-state="warming"' in rendered
    assert 'data-sector-state="inflow"' in rendered
    assert payload == before


def test_heatmap_missing_sector_source_fails_closed_without_invented_cells():
    payload = dataset()
    payload["sector_rotation"] = None
    payload["source_status"] = [
        {"name": "market", "status": "OK", "as_of": "2026-08-11"},
        {"name": "sector_rotation", "status": "MISSING", "reason": "fixture missing"},
    ]
    rendered = module.render_sector_heatmap(payload)
    assert "Sector Rotationは取得できません" in rendered
    assert "fixture missing" in rendered
    assert "home-heatmap-cell" not in rendered


def test_heatmap_mobile_does_not_depend_on_horizontal_scroll():
    css = CSS_PATH.read_text(encoding="utf-8")
    assert ".home-heatmap-grid" in css
    assert "grid-template-columns: 1fr" in css
    heatmap_block = css.split(".home-heatmap-grid", 1)[1]
    assert "overflow-x: auto" not in heatmap_block


def test_portfolio_impact_renders_holdings_but_keeps_impact_unknown():
    payload = portfolio_dataset()
    before = deepcopy(payload)

    rendered = module.render_portfolio_impact(payload)

    assert "自分の保有銘柄にどう関係する？" in rendered
    assert "ダイヘン" in rendered
    assert "日東紡" in rendered
    assert "6622" in rendered
    assert "影響判定: 未接続 / UNKNOWN" in rendered
    assert "自分への影響: 未判定 / UNKNOWN" in rendered
    assert "/risk-preflight/" in rendered
    assert "BUY/SELL" in rendered
    assert payload == before


def test_portfolio_impact_stale_is_freshness_problem_not_negative_signal():
    rendered = module.render_portfolio_impact(portfolio_dataset(status="STALE"))

    assert 'data-state="stale"' in rendered
    assert "保有情報が古いため、銘柄評価ではなく鮮度問題" in rendered
    assert "自分への影響: 未判定 / UNKNOWN" in rendered


def test_portfolio_impact_missing_fails_closed_without_fake_empty_holdings():
    payload = dataset()
    payload["source_status"].append(
        {"name": "portfolio", "status": "MISSING", "reason": "canonical missing"}
    )
    payload["portfolio"] = None

    rendered = module.render_portfolio_impact(payload)

    assert "自分への影響は判定できません / UNAVAILABLE" in rendered
    assert "home-portfolio-position" not in rendered
    assert "Portfolio source: 取得できません / MISSING" in rendered


def test_portfolio_mobile_uses_stack_grid_not_horizontal_table():
    css = CSS_PATH.read_text(encoding="utf-8")
    assert ".home-portfolio-grid" in css
    mobile = css.split("@media (max-width: 640px)", 1)[1]
    assert ".home-portfolio-grid" in mobile
    assert "grid-template-columns: 1fr" in mobile
    assert "overflow-x: auto" not in mobile


def test_missing_dataset_fails_closed_as_unavailable():
    rendered = module.render_status_section(None)
    assert "Morning Datasetを取得できません" in rendered
    assert "HeatMapを表示できません" in rendered
    assert "自分への影響は判定できません" in rendered
    assert 'data-state="unavailable"' in rendered
    assert "問題なし" in rendered


def test_previous_business_day_dataset_is_not_shown_as_normal_partial():
    payload = dataset()
    rendered = module.render_status_section(
        payload, expected_as_of=date(2026, 8, 12)
    )
    assert "NOT_GENERATED_TODAY" in rendered
    assert "今日のMorning Datasetはまだ生成されていません" in rendered
    assert "表示中: 2026-08-11" in rendered
    assert "source completenessのPARTIALとは別" in rendered
    assert 'data-state="stale"' in rendered


def test_expected_business_date_uses_jst_and_skips_weekend():
    saturday_utc = datetime.fromisoformat("2026-08-15T01:00:00+00:00")
    assert module.expected_jst_business_date(saturday_utc) == date(2026, 8, 14)


def test_missing_source_status_is_not_promoted_to_ok():
    payload = dataset()
    payload["source_status"] = []
    rendered = module.render_status_section(payload)
    assert "取得できません / MISSING" in rendered
    assert "source status not available" in rendered


def test_enrich_replaces_status_area_adds_market_and_portfolio_sections():
    rendered = module.enrich_text(
        home_text(), portfolio_dataset(), expected_as_of=date(2026, 8, 11)
    )
    assert rendered.startswith("before\n")
    assert "old status" not in rendered
    assert "市場・テーマの動き" in rendered
    assert "自分の保有銘柄にどう関係する？" in rendered
    assert "ダイヘン" in rendered
    assert module.STATUS_SECTION_END in rendered
    assert rendered.endswith("after\n")
    assert "WARMING 1件 / INFLOW 1件" in rendered
