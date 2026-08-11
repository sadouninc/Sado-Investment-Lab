from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / ".github" / "pages" / "concept.py"
CONCEPT_PATH = ROOT / ".github" / "pages" / "concept-v1.json"
OS_MAP_PATH = ROOT / ".github" / "pages" / "os-map-v1.json"
OUTPUT_PATH = ROOT / "site-src" / "concepts" / "investment-decision-cockpit" / "index.md"
DESIGN_SYSTEM = ROOT / ".github" / "pages" / "design-system.css"

SPEC = importlib.util.spec_from_file_location("concept", MODULE_PATH)
assert SPEC and SPEC.loader
concept = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = concept
SPEC.loader.exec_module(concept)


def fixture():
    data = concept.load_json(CONCEPT_PATH)
    return data["concepts"][0], concept.load_json(OS_MAP_PATH)


def test_cockpit_contract_uses_shared_route_and_os_stage_truth() -> None:
    record, os_map = fixture()
    concept.validate_concept(record, os_map)
    assert record["route_ref"] == "/decision-cockpit/daihen/"
    assert record["os_stage_ref"] == "decide"
    assert len(record["first_checks"]) <= 3


def test_unknown_route_or_evidence_fails_closed() -> None:
    record, os_map = fixture()
    broken = copy.deepcopy(record)
    broken["evidence_refs"] = ["/invented-evidence/"]
    with pytest.raises(ValueError, match="unknown route/evidence ref"):
        concept.validate_concept(broken, os_map)


def test_all_human_meanings_for_fail_closed_states_are_required() -> None:
    record, os_map = fixture()
    broken = copy.deepcopy(record)
    broken["common_states"] = broken["common_states"][:-1]
    with pytest.raises(ValueError, match="UNKNOWN / UNAVAILABLE / STALE"):
        concept.validate_concept(broken, os_map)


def test_render_is_japanese_first_and_does_not_mutate_input() -> None:
    record, os_map = fixture()
    before = copy.deepcopy(record)
    rendered = concept.render(record, os_map)
    assert record == before
    for heading in ["最初の30秒で見る3点", "判断の流れ", "状態の意味", "次に進む", "根拠を見る"]:
        assert heading in rendered
    for status in ["UNKNOWN", "UNAVAILABLE", "STALE"]:
        assert status in rendered
    assert "BUY / SELL / ADD / REDUCEを自動決定しない" in rendered
    assert "前回判断 → 現在との差 → 市場期待との差 → 仮説確認 → Valuation → 売買前PF影響 → 判断Snapshot → 次checkpoint" in rendered


def test_render_adopts_canonical_design_system_without_second_theme() -> None:
    record, os_map = fixture()
    rendered = concept.render(record, os_map)
    css = DESIGN_SYSTEM.read_text(encoding="utf-8")

    assert "/assets/design-system.css" in rendered
    for class_name in (
        "codex-page-shell",
        "codex-page-header",
        "codex-summary-card",
        "codex-status-chip",
        "codex-alert",
        "codex-action",
        "codex-evidence",
        "codex-disclosure",
    ):
        assert class_name in rendered
        assert f".{class_name}" in css
    assert "sil-" not in rendered
    assert "<style" not in rendered


def test_rendered_fixture_matches_generator_and_preserves_visual_priority() -> None:
    record, os_map = fixture()
    rendered = concept.render(record, os_map)
    assert rendered == OUTPUT_PATH.read_text(encoding="utf-8")
    assert rendered.index("最初の30秒で見る3点") < rendered.index("判断の流れ")
    assert rendered.index("判断の流れ") < rendered.index("状態の意味")
    assert rendered.index("状態の意味") < rendered.index("次に進む")
    assert "Live Cockpitを開く" in rendered
    assert "/risk-preflight/" in rendered
    assert "/trade-journal/" in rendered


def test_required_fields_and_first_checks_are_validated() -> None:
    record, os_map = fixture()
    missing = copy.deepcopy(record)
    del missing["purpose_ja"]
    with pytest.raises(ValueError, match="missing required fields"):
        concept.validate_concept(missing, os_map)
    too_many = copy.deepcopy(record)
    too_many["first_checks"] = ["a", "b", "c", "d"]
    with pytest.raises(ValueError, match="1..3"):
        concept.validate_concept(too_many, os_map)
