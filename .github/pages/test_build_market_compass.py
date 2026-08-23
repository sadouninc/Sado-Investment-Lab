"""Focused unit and integration tests for owner-facing Market Compass Pages projection (#586 B4)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest

HERE = Path(__file__).resolve().parent
BUILDER_PATH = HERE / "build_market_compass.py"

spec = importlib.util.spec_from_file_location("build_market_compass", BUILDER_PATH)
bmc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bmc)


def test_section_separation_and_membership():
    """Verify Current Holdings and Re-entry Watch are strictly separated."""
    portfolio = {
        "as_of": "2026-08-08",
        "verification_status": "VERIFIED",
        "positions": [
            {"security_code": "6702", "security_name": "富士通", "quantity": 100},
            {"security_code": "6622", "security_name": "ダイヘン", "quantity": 100},
        ],
    }
    reentry_watch = {
        "as_of": "2026-08-15",
        "macro_state": "RED",
        "candidates": [
            {
                "security_code": "6702",
                "name": "富士通",
                "exit_date": "2026-08-14",
                "exit_price": 3715.0,
                "benchmark": "TOPIX",
            },
        ],
    }
    subsector_evidence = {
        "6702": {"status": "PASS"},
        "6622": {"status": "PASS"},
    }

    evaluated = bmc.generate_market_compass_projection(
        portfolio=portfolio,
        reentry_watch=reentry_watch,
        subsector_evidence=subsector_evidence,
    )

    current_codes = [x["security_code"] for x in evaluated["current_holdings"]]
    reentry_codes = [x["security_code"] for x in evaluated["reentry_watch"]]

    assert "6622" in current_codes
    assert "6702" not in current_codes
    assert "6702" in reentry_codes
    assert "6622" not in reentry_codes
    assert evaluated["as_of"] == "2026-08-15"
    assert evaluated["macro_state"] == "RED"

    rendered = bmc.render_market_compass_page(evaluated)

    assert "2. 現在保有の危険管理 (Current Holdings)" in rendered
    assert "3. 売却済み・再評価候補 (Re-entry Watch)" in rendered
    assert "Re-entry Watch" in rendered
    assert "富士通" in rendered
    assert "売却価格: 3715.0円" in rendered
    assert "ベンチマーク: TOPIX" in rendered


def test_provisional_authority_and_unknown_visibility():
    """Verify PROVISIONAL authority warning and fail-closed UNKNOWN visibility."""
    portfolio = {
        "as_of": "2026-08-15",
        "verification_status": "PROVISIONAL",
        "positions": [
            {"security_code": "9999", "security_name": "テスト銘柄", "quantity": 100},
        ],
    }
    reentry_watch = {"as_of": "2026-08-15", "macro_state": "ORANGE", "candidates": []}
    subsector_evidence = {}  # Missing evidence triggers UNKNOWN

    evaluated = bmc.generate_market_compass_projection(
        portfolio=portfolio,
        reentry_watch=reentry_watch,
        subsector_evidence=subsector_evidence,
    )

    rendered = bmc.render_market_compass_page(evaluated)

    assert "PROVISIONAL" in rendered
    assert "仮確定" in rendered
    assert "最新の約定明細照合まで" in rendered
    assert "UNKNOWN" in rendered
    assert "ORANGE (橙 / シャドー観測)" in rendered


def test_reentry_ready_warning_and_boj_context():
    """Verify REENTRY_READY displays owner-facing warning and BOJ is context only."""
    evaluated_mock = {
        "as_of": "2026-08-15",
        "macro_state": "RED",
        "current_holdings": [],
        "reentry_watch": [
            {
                "security_code": "6702",
                "security_name": "富士通",
                "market_compass_state": "REENTRY_READY",
                "evaluation_status": "EVALUATED",
                "fundamental_integrity": "PASS",
                "portfolio_authority_status": "STALE_RELATIVE_TO_EXIT",
                "score_total": 75,
                "scores": {
                    "excess_decline": 20,
                    "valuation_reset": 20,
                    "fundamental_strength": 20,
                    "risk_stabilization": 15,
                },
                "reentry_candidate": {"exit_date": "2026-08-14"},
            }
        ],
        "membership_unknown": [],
    }

    rendered = bmc.render_market_compass_page(evaluated_mock)

    assert "RE-ENTRY READY (再参入準備)" in rendered
    assert "実際の購入決定や売買発注を意味するものではありません" in rendered
    assert "RED (赤 / アクティブ観測)" in rendered
    assert "BOJ RED != 全銘柄AVOID" in rendered


def test_buy_watch_japanese_label_is_non_directive():
    """Verify BUY_WATCH Japanese label is non-directive (買い候補を監視)."""
    evaluated_mock = {
        "as_of": "2026-08-15",
        "macro_state": "RED",
        "current_holdings": [
            {
                "security_code": "6622",
                "security_name": "ダイヘン",
                "market_compass_state": "BUY_WATCH",
                "evaluation_status": "EVALUATED",
                "fundamental_integrity": "PASS",
                "portfolio_authority_status": "VERIFIED",
                "score_total": 55,
                "scores": {
                    "excess_decline": 15,
                    "valuation_reset": 15,
                    "fundamental_strength": 15,
                    "risk_stabilization": 10,
                },
                "position": {"quantity": 100, "position_type": "margin_long"},
            }
        ],
        "reentry_watch": [],
        "membership_unknown": [],
    }

    rendered = bmc.render_market_compass_page(evaluated_mock)

    assert "買い候補を監視 (BUY WATCH)" in rendered
    assert "買付打診" not in rendered


def test_w33_reentry_watch_json_dynamic_loading():
    """Verify default reentry watch is loaded from canonical W33 JSON artifact."""
    default_reentry = bmc.get_default_reentry_watch()

    assert default_reentry.get("as_of") == "2026-08-15"
    assert default_reentry.get("macro_state") == "RED"
    assert len(default_reentry.get("candidates", [])) == 5

    candidate_codes = [c["security_code"] for c in default_reentry["candidates"]]
    assert "6702" in candidate_codes
    assert "4588" in candidate_codes
    assert "5801" in candidate_codes
    assert "3778" in candidate_codes
    assert "6376" in candidate_codes

    evaluated = bmc.generate_market_compass_projection()
    assert evaluated["as_of"] == "2026-08-15"
    assert evaluated["macro_state"] == "RED"

    rendered = bmc.render_market_compass_page(evaluated)
    assert "RED (赤 / アクティブ観測)" in rendered
    assert "GREEN (緑 / 観測非活性)" not in rendered


def test_missing_json_fails_closed():
    """Verify missing JSON falls back fail-closed to UNKNOWN rather than inventing defaults."""
    empty_portfolio = bmc.generate_market_compass_projection(
        portfolio={"as_of": "UNKNOWN", "verification_status": "PROVISIONAL", "positions": []},
        reentry_watch={"as_of": "UNKNOWN", "macro_state": "UNKNOWN", "candidates": []},
    )

    assert empty_portfolio["as_of"] == "UNKNOWN"
    assert empty_portfolio["macro_state"] == "UNKNOWN"

    rendered = bmc.render_market_compass_page(empty_portfolio)
    assert "UNKNOWN (不明)" in rendered


def test_no_duplicate_threshold_logic_in_pages_layer():
    """Verify Pages builder does not duplicate state evaluator threshold constants."""
    source_code = BUILDER_PATH.read_text(encoding="utf-8")

    # The canonical state evaluator owns threshold numbers like >= 70, >= 50, score_total < 50
    assert "score_total >= 70" not in source_code
    assert "score_total >= 50" not in source_code
    assert "risk_stabilization >= 15" not in source_code
    assert "risk_stabilization >= 10" not in source_code


def test_mobile_responsive_layout_primitives():
    """Verify responsive primitives support 390px and 320px viewports without horizontal overflow."""
    portfolio = {
        "as_of": "2026-08-08",
        "verification_status": "VERIFIED",
        "positions": [
            {"security_code": "6622", "security_name": "ダイヘン", "quantity": 100},
        ],
    }

    evaluated = bmc.generate_market_compass_projection(portfolio=portfolio)
    rendered = bmc.render_market_compass_page(evaluated)

    assert "max-width: 100%" in rendered
    assert "box-sizing: border-box" in rendered
    assert "word-break: break-word" in rendered
    assert "@media (min-width: 768px)" in rendered
