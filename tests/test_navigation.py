from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / ".github" / "pages" / "navigation.py"
CONFIG_PATH = ROOT / ".github" / "pages" / "navigation-v1.json"
OS_MAP_PATH = ROOT / ".github" / "pages" / "os-map-v1.json"
CONCEPT_PATH = ROOT / ".github" / "pages" / "concept-v1.json"

SPEC = importlib.util.spec_from_file_location("navigation", MODULE_PATH)
assert SPEC and SPEC.loader
navigation = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = navigation
SPEC.loader.exec_module(navigation)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_six_purpose_navigation_and_nine_stage_mapping_are_fixed() -> None:
    payload = navigation.load_navigation(CONFIG_PATH)
    assert tuple(group["id"] for group in payload["navigation_groups"]) == navigation.NAV_GROUPS
    assert set(payload["os_stage_to_navigation"]) == set(navigation.OS_STAGE_IDS)
    assert payload["os_stage_to_navigation"]["hypothesize"] == {
        "primary": "understand", "secondary": ["decide"]
    }
    assert payload["os_stage_to_navigation"]["pretrade"]["primary"] == "decide"
    assert payload["os_stage_to_navigation"]["record"]["primary"] == "record"
    assert payload["os_stage_to_navigation"]["learn"]["primary"] == "review"


def test_navigation_reuses_all_available_home_os_map_destinations() -> None:
    payload = navigation.load_navigation(CONFIG_PATH)
    os_map = load_json(OS_MAP_PATH)
    inventory = {record["route"] for record in payload["routes"] if record["availability"] == "AVAILABLE"}
    shared_routes = {
        stage["primary_destination"]
        for stage in os_map["stages"]
        if stage["availability"] == "AVAILABLE"
    }
    shared_routes.update(
        entry["route"] for entry in os_map["today_entries"]
        if entry["availability"] == "AVAILABLE"
    )
    assert shared_routes <= inventory


def test_concept_route_is_optional_relation_not_second_route_truth() -> None:
    payload = navigation.load_navigation(CONFIG_PATH)
    concepts = load_json(CONCEPT_PATH)["concepts"]
    cockpit = next(record for record in payload["routes"] if record["route"] == "/decision-cockpit/daihen/")
    concept = concepts[0]
    assert cockpit["route"] == concept["route_ref"]
    assert cockpit["concept_route"] == "/concepts/investment-decision-cockpit/"
    assert concept["os_stage_ref"] == "decide"


def test_major_user_journeys_are_inventoryed_without_fake_portfolio_route() -> None:
    payload = navigation.load_navigation(CONFIG_PATH)
    by_route = {record["route"]: record for record in payload["routes"] if record["route"]}
    assert by_route["/companies/"]["primary_journey_stage"] == "understand"
    assert by_route["/decision-cockpit/daihen/"]["primary_journey_stage"] == "decide"
    assert by_route["/trade-journal/"]["primary_journey_stage"] == "record"
    assert by_route["/trade-analysis/"]["primary_journey_stage"] == "review"
    portfolio = next(record for record in payload["routes"] if record.get("feature_id") == "portfolio-current")
    assert portfolio["availability"] == "UNMAPPED"
    assert portfolio["route"] is None
    assert portfolio["canonical_destination"] is None


def test_duplicate_canonical_destination_fails_closed() -> None:
    payload = navigation.load_navigation(CONFIG_PATH)
    broken = copy.deepcopy(payload)
    duplicate = copy.deepcopy(next(record for record in broken["routes"] if record["route"] == "/companies/"))
    duplicate["route"] = "/fake-company-alias/"
    broken["routes"].append(duplicate)
    with pytest.raises(ValueError, match="duplicate canonical destination"):
        navigation.validate_navigation(broken)


def test_unknown_route_resolves_to_unmapped_without_inventing_canonical_path() -> None:
    payload = navigation.load_navigation(CONFIG_PATH)
    resolved = navigation.resolve_route(payload, "/route-that-does-not-exist/")
    assert resolved["availability"] == "UNMAPPED"
    assert resolved["canonical_destination"] is None
    assert resolved["concept_route"] is None


def test_navigation_config_does_not_mutate_source_contracts() -> None:
    before_os = OS_MAP_PATH.read_text(encoding="utf-8")
    before_concept = CONCEPT_PATH.read_text(encoding="utf-8")
    navigation.load_navigation(CONFIG_PATH)
    assert OS_MAP_PATH.read_text(encoding="utf-8") == before_os
    assert CONCEPT_PATH.read_text(encoding="utf-8") == before_concept
