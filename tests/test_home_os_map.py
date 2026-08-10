from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / ".github" / "pages" / "home_os_map.py"
CONFIG_PATH = ROOT / ".github" / "pages" / "os-map-v1.json"
TEMPLATE_PATH = ROOT / ".github" / "pages" / "home-os-map-template.md"
HOME_PATH = ROOT / ".github" / "pages" / "home.md"
DESIGN_SYSTEM_SOURCE = ROOT / ".github" / "pages" / "design-system-v1.css"
DESIGN_SYSTEM_PUBLISHED = ROOT / "assets" / "images" / "design-system-v1.css"

SPEC = importlib.util.spec_from_file_location("home_os_map", MODULE_PATH)
assert SPEC and SPEC.loader
home_os_map = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = home_os_map
SPEC.loader.exec_module(home_os_map)


def test_os_map_has_exact_nine_stage_loop_and_known_destinations() -> None:
    payload = home_os_map.load_os_map(CONFIG_PATH)

    assert [stage["stage_id"] for stage in payload["stages"]] == [
        "observe",
        "discover",
        "understand",
        "hypothesize",
        "decide",
        "pretrade",
        "record",
        "learn",
        "observe_next",
    ]
    assert payload["loop_label_ja"] == (
        "観測 → 発見 → 理解 → 仮説 → 判断 → 売買前確認 → "
        "執行/記録 → 検証/学習 → 次の観測"
    )
    for stage in payload["stages"]:
        if stage["availability"] == "AVAILABLE":
            assert stage["primary_destination"] in home_os_map.KNOWN_ROUTES


def test_home_is_deterministic_render_of_template_and_config() -> None:
    payload = home_os_map.load_os_map(CONFIG_PATH)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    rendered = home_os_map.render_home(template, payload)

    assert rendered == HOME_PATH.read_text(encoding="utf-8")
    assert rendered.index("今日見る") < rendered.index("重要な変化・状態")
    assert rendered.index("重要な変化・状態") < rendered.index("Investment OS 全体像")
    assert rendered.index("Investment OS 全体像") < rendered.index("主要入口")
    assert 'data-stage-id="decide"' in rendered
    assert "/risk-preflight/" in rendered
    assert "/trade-journal/" in rendered


def test_available_destination_must_be_in_shared_route_inventory() -> None:
    payload = home_os_map.load_os_map(CONFIG_PATH)
    broken = copy.deepcopy(payload)
    broken["stages"][0]["primary_destination"] = "/invented-route/"

    with pytest.raises(ValueError, match="not in route inventory"):
        home_os_map.validate_os_map(broken)


def test_unavailable_destination_must_fail_closed_without_route() -> None:
    payload = home_os_map.load_os_map(CONFIG_PATH)
    unavailable = copy.deepcopy(payload)
    unavailable["stages"][0]["availability"] = "UNAVAILABLE"
    unavailable["stages"][0]["primary_destination"] = None

    home_os_map.validate_os_map(unavailable)
    rendered = home_os_map.render_home(
        TEMPLATE_PATH.read_text(encoding="utf-8"), unavailable
    )
    observe = rendered.split('data-stage-id="observe"', 1)[1].split("</article>", 1)[0]
    assert "接続先は未設定です" in observe
    assert "sil-evidence-link" not in observe


def test_unavailable_destination_cannot_keep_a_guessed_route() -> None:
    payload = home_os_map.load_os_map(CONFIG_PATH)
    broken = copy.deepcopy(payload)
    broken["stages"][0]["availability"] = "UNAVAILABLE"

    with pytest.raises(ValueError, match="must not invent a route"):
        home_os_map.validate_os_map(broken)


def test_home_uses_visual_design_system_v1_semantics() -> None:
    home = HOME_PATH.read_text(encoding="utf-8")
    source_css = DESIGN_SYSTEM_SOURCE.read_text(encoding="utf-8")
    published_css = DESIGN_SYSTEM_PUBLISHED.read_text(encoding="utf-8")

    assert "/assets/images/design-system-v1.css" in home
    for semantic in (
        "--sil-accent-primary",
        "--sil-state-unavailable",
        ".sil-summary-card",
        ".sil-status-chip",
        ".sil-action",
        ".sil-evidence-link",
        ".sil-disclosure",
    ):
        assert semantic in source_css
        assert semantic in published_css


def test_home_remains_read_only_and_does_not_claim_priority_scoring() -> None:
    home = HOME_PATH.read_text(encoding="utf-8")

    assert "Home独自のBUY/SELL判定や優先順位スコアは作りません" in home
    assert "Home専用のCanonical truthを作らない" in home
    assert "取得できていない状態を「問題なし」「最新」とは扱いません" in home
