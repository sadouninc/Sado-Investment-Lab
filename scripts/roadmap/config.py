from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_STAGE_KEYS = {
    "id",
    "name",
    "purpose",
    "knowledge_areas",
    "machine_areas",
    "presentation_areas",
    "related_issues",
    "entry_conditions",
    "done_conditions",
}


def load_roadmap_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_roadmap_config(payload)
    return payload


def validate_roadmap_config(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != "1.0":
        raise ValueError("schema_version must be 1.0")

    stages = payload.get("stages")
    if not isinstance(stages, list) or len(stages) != 8:
        raise ValueError("stages must contain exactly stage_0 through stage_7")

    expected_ids = [f"stage_{i}" for i in range(8)]
    actual_ids = [stage.get("id") if isinstance(stage, dict) else None for stage in stages]
    if actual_ids != expected_ids:
        raise ValueError("stages must be ordered stage_0 through stage_7")

    known_ids = set(expected_ids)
    done_condition_ids: set[str] = set()

    for stage in stages:
        if not isinstance(stage, dict):
            raise ValueError("each stage must be an object")
        missing = REQUIRED_STAGE_KEYS - set(stage)
        if missing:
            raise ValueError(f"{stage.get('id', '<unknown>')} missing keys: {sorted(missing)}")
        unknown = set(stage) - REQUIRED_STAGE_KEYS
        if unknown:
            raise ValueError(f"{stage['id']} has unknown keys: {sorted(unknown)}")

        for key in ("name", "purpose"):
            if not isinstance(stage[key], str) or not stage[key].strip():
                raise ValueError(f"{stage['id']} {key} must be a non-empty string")

        for key in ("knowledge_areas", "machine_areas", "presentation_areas"):
            _validate_unique_string_list(stage["id"], key, stage[key])

        issues = stage["related_issues"]
        if not isinstance(issues, list) or any(not isinstance(issue, int) or issue <= 0 for issue in issues):
            raise ValueError(f"{stage['id']} related_issues must be positive integers")
        if len(issues) != len(set(issues)):
            raise ValueError(f"{stage['id']} related_issues must not contain duplicates")

        dependencies = stage["entry_conditions"]
        _validate_unique_string_list(stage["id"], "entry_conditions", dependencies)
        for dependency in dependencies:
            if dependency not in known_ids:
                raise ValueError(f"{stage['id']} references unknown entry condition {dependency}")
            if dependency == stage["id"]:
                raise ValueError(f"{stage['id']} cannot depend on itself")
            if int(dependency.split("_")[1]) >= int(stage["id"].split("_")[1]):
                raise ValueError(f"{stage['id']} entry conditions must reference earlier stages")

        conditions = stage["done_conditions"]
        if not isinstance(conditions, list) or not conditions:
            raise ValueError(f"{stage['id']} done_conditions must be a non-empty list")
        for condition in conditions:
            if not isinstance(condition, dict) or set(condition) != {"id", "description"}:
                raise ValueError(f"{stage['id']} done condition must contain only id and description")
            condition_id = condition["id"]
            description = condition["description"]
            if not isinstance(condition_id, str) or not condition_id.strip():
                raise ValueError(f"{stage['id']} done condition id must be non-empty")
            if condition_id in done_condition_ids:
                raise ValueError(f"duplicate done condition id: {condition_id}")
            done_condition_ids.add(condition_id)
            if not isinstance(description, str) or not description.strip():
                raise ValueError(f"{stage['id']} done condition description must be non-empty")


def _validate_unique_string_list(stage_id: str, key: str, value: Any) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{stage_id} {key} must be a list of non-empty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{stage_id} {key} must not contain duplicates")
