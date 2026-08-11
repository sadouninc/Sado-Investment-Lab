from __future__ import annotations

import json
from pathlib import Path
from typing import Any


NAV_GROUPS = ("home", "discover", "understand", "decide", "record", "review")
OS_STAGE_IDS = (
    "observe", "discover", "understand", "hypothesize", "decide",
    "pretrade", "record", "learn", "observe_next",
)
VALID_AVAILABILITY = {"AVAILABLE", "UNMAPPED"}


def load_navigation(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_navigation(payload)
    return payload


def validate_navigation(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != "1.0":
        raise ValueError("unsupported navigation schema_version")

    groups = payload.get("navigation_groups")
    group_ids = tuple(group.get("id") for group in groups or [])
    if group_ids != NAV_GROUPS:
        raise ValueError("navigation groups must match the fixed 6-purpose contract")

    stage_map = payload.get("os_stage_to_navigation")
    if set(stage_map or {}) != set(OS_STAGE_IDS):
        raise ValueError("OS stage mapping must cover exactly the shared 9-stage model")
    for stage_id, mapping in stage_map.items():
        primary = mapping.get("primary")
        secondary = mapping.get("secondary", [])
        if primary not in NAV_GROUPS:
            raise ValueError(f"unknown primary navigation group for {stage_id}: {primary}")
        if any(item not in NAV_GROUPS for item in secondary):
            raise ValueError(f"unknown secondary navigation group for {stage_id}")

    routes = payload.get("routes")
    if not isinstance(routes, list) or not routes:
        raise ValueError("routes must not be empty")

    canonical_seen: set[str] = set()
    route_seen: set[str] = set()
    for record in routes:
        for field in (
            "route", "primary_journey_stage", "secondary_journey_stages",
            "user_facing_label_ja", "parent_route", "canonical_destination",
            "legacy_aliases", "concept_route", "availability",
        ):
            if field not in record:
                raise ValueError(f"route record missing field: {field}")

        availability = record["availability"]
        if availability not in VALID_AVAILABILITY:
            raise ValueError(f"invalid availability: {availability}")
        if record["primary_journey_stage"] not in NAV_GROUPS:
            raise ValueError("route uses unknown navigation group")
        if any(item not in NAV_GROUPS for item in record["secondary_journey_stages"]):
            raise ValueError("route uses unknown secondary navigation group")

        route = record["route"]
        canonical = record["canonical_destination"]
        if availability == "AVAILABLE":
            if not route or not canonical:
                raise ValueError("AVAILABLE route requires route and canonical_destination")
            if route in route_seen:
                raise ValueError(f"duplicate route: {route}")
            route_seen.add(route)
            if canonical in canonical_seen:
                raise ValueError(f"duplicate canonical destination: {canonical}")
            canonical_seen.add(canonical)
        else:
            if route is not None or canonical is not None:
                raise ValueError("UNMAPPED record must not invent route or canonical destination")


def resolve_route(payload: dict[str, Any], route: str) -> dict[str, Any]:
    validate_navigation(payload)
    for record in payload["routes"]:
        if record["route"] == route:
            return record
    return {
        "route": route,
        "primary_journey_stage": "home",
        "secondary_journey_stages": [],
        "user_facing_label_ja": "未分類のページ",
        "parent_route": "/",
        "canonical_destination": None,
        "legacy_aliases": [],
        "concept_route": None,
        "availability": "UNMAPPED",
    }
