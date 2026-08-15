from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / ".github" / "pages" / "build_ai_morning_reports.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_ai_morning_reports", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_at_is_rendered_in_jst():
    module = load_module()
    assert module.generated_at_label("2026-08-14T02:40:17+00:00") == "2026-08-14 11:40 JST"


def test_generated_at_fails_closed_when_timezone_is_missing():
    module = load_module()
    assert module.generated_at_label("2026-08-14T02:40:17") == ""
    assert module.generated_at_label("not-a-date") == ""


def test_dataset_status_is_japanese_first_and_keeps_missing_semantics():
    module = load_module()
    assert module.dataset_status_label("OK") == "データ状態: 取得済み"
    assert module.dataset_status_label("PARTIAL") == "データ状態: 一部取得できていません"
    assert module.dataset_status_label("STALE") == "データ状態: 情報が古いため再確認が必要"
    assert module.dataset_status_label("UNAVAILABLE") == "データ状態: 現在取得できません"
    assert module.dataset_status_label("UNKNOWN") == "データ状態: 確認できません"


def test_latest_card_prioritizes_update_market_watch_and_status():
    module = load_module()
    card = module.latest_report_card(
        "2026-08-14",
        "/reports/morning/2026-08-14/",
        {"market": "日経平均は反発", "strategy": "押し目を監視", "watch": "ダイヘン", "risk": ""},
        "PARTIAL",
        "2026-08-14T02:40:17+00:00",
    )

    assert "最新レポート 2026-08-14" in card
    assert "更新: 2026-08-14 11:40 JST" in card
    assert "市場: 日経平均は反発" in card
    assert "注目: ダイヘン" in card
    assert "データ状態: 一部取得できていません" in card
    assert "Data quality" not in card
    assert "Model:" not in card
