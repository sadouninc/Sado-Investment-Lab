from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / ".github" / "pages" / "concept.py"
CONCEPT_PATH = ROOT / ".github" / "pages" / "concept-v1.json"
OS_MAP_PATH = ROOT / ".github" / "pages" / "os-map-v1.json"

SPEC = importlib.util.spec_from_file_location("concept_priority", MODULE_PATH)
assert SPEC and SPEC.loader
concept = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = concept
SPEC.loader.exec_module(concept)

EXPECTED = {
    "investment-decision-cockpit",
    "bear-base-bull-forward-per",
    "hypothesis-must-happen-invalidation",
    "pre-trade-what-if-portfolio-impact",
    "money-flow-candidate-discovery",
}


def fixtures():
    data = concept.load_json(CONCEPT_PATH)
    os_map = concept.load_json(OS_MAP_PATH)
    return data, os_map


def test_initial_priority_fixture_set_is_complete_and_valid() -> None:
    data, os_map = fixtures()
    concept.validate_all(data, os_map)
    assert {record["feature_id"] for record in data["concepts"]} == EXPECTED


def test_generic_guides_are_japanese_first_and_fail_closed() -> None:
    data, os_map = fixtures()
    for record in data["concepts"]:
        if record["feature_id"] == "investment-decision-cockpit":
            continue
        rendered = concept.render_guide(record, os_map)
        assert "最初の30秒で見るポイント" in rendered
        assert "なぜ見るのか" in rendered
        assert "状態の意味" in rendered
        assert "次に進む" in rendered
        assert "根拠を見る" in rendered
        assert "UNKNOWN" in rendered
        assert "UNAVAILABLE" in rendered
        assert "STALE" in rendered
        assert "BUY" in rendered or "売買" in rendered
        assert "<style" not in rendered
        assert "sil-" not in rendered
        assert "/assets/design-system.css" in rendered


def test_priority_guides_only_reference_existing_route_truth() -> None:
    data, os_map = fixtures()
    routes = concept.route_inventory(os_map)
    for record in data["concepts"]:
        refs = [record["route_ref"], *record["next_destination_refs"], *record["evidence_refs"]]
        assert set(refs) <= routes


def test_priority_guide_output_paths_are_stable_and_unique() -> None:
    data, _ = fixtures()
    paths = [concept.output_path(record) for record in data["concepts"]]
    assert len(paths) == len(set(paths))
    for record, path in zip(data["concepts"], paths):
        assert path == ROOT / "site-src" / "concepts" / record["feature_id"] / "index.md"
