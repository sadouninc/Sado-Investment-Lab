from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / ".github" / "pages" / "enrich_home_today.py"
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
            "sectors": [
                {"id": "sector:a", "state": "WARMING"},
                {"id": "sector:b", "state": "INFLOW"},
                {"id": "sector:c", "state": "HOT"},
            ],
        },
        "warnings": ["portfolio source is stale: fixture"],
    }


def home_text() -> str:
    return (
        "before\n"
        + module.STATUS_SECTION_START
        + "\nold status\n  </section>\n\n"
        + module.STATUS_SECTION_END
        + "\nafter\n"
    )


def test_render_uses_existing_canonical_status_without_ranking_or_trade_action():
    payload = dataset()
    before = deepcopy(payload)
    rendered = module.render_status_section(payload)
    assert "Morning Dataset: 一部情報不足 / PARTIAL" in rendered
    assert "市場データ" in rendered
    assert "Sector Rotation" in rendered
    assert "WARMING 1件 / INFLOW 1件" in rendered
    assert "portfolio source is stale: fixture" in rendered
    assert "順位や推奨はHomeで生成しません" in rendered
    assert "BUY" not in rendered
    assert "SELL" not in rendered
    assert payload == before


def test_missing_dataset_fails_closed_as_unavailable():
    rendered = module.render_status_section(None)
    assert "Morning Datasetを取得できません" in rendered
    assert 'data-state="unavailable"' in rendered
    assert "問題なし" in rendered


def test_missing_source_status_is_not_promoted_to_ok():
    payload = dataset()
    payload["source_status"] = []
    rendered = module.render_status_section(payload)
    assert "取得できません / MISSING" in rendered
    assert "source status not available" in rendered


def test_enrich_replaces_only_status_section_and_preserves_following_map():
    rendered = module.enrich_text(home_text(), dataset())
    assert rendered.startswith("before\n")
    assert "old status" not in rendered
    assert module.STATUS_SECTION_END in rendered
    assert rendered.endswith("after\n")
    assert "WARMING 1件 / INFLOW 1件" in rendered
