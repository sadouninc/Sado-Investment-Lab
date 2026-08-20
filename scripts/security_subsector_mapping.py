"""Canonical security-to-subsector mapping validator and read-only lookup for #756."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "data/contracts/security-subsector-mapping-v1.schema.json"
MAPPING_PATH = ROOT / "data/masters/security-subsector-mapping-v1.json"


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_mapping(mapping: dict[str, Any]) -> None:
    jsonschema.Draft202012Validator(
        load_schema(), format_checker=jsonschema.FormatChecker()
    ).validate(mapping)

    for record in mapping["records"]:
        start = date.fromisoformat(record["effective_from"])
        end_raw = record["effective_to"]
        if end_raw is not None and date.fromisoformat(end_raw) < start:
            raise ValueError("effective_to must be on or after effective_from")

    by_security: dict[str, list[dict[str, Any]]] = {}
    for record in mapping["records"]:
        by_security.setdefault(record["security_code"], []).append(record)
    for security_code, records in by_security.items():
        ordered = sorted(records, key=lambda item: item["effective_from"])
        for previous, current in zip(ordered, ordered[1:]):
            previous_end = previous["effective_to"]
            if previous_end is None or current["effective_from"] <= previous_end:
                raise ValueError(f"overlapping active mappings for {security_code}")


def load_mapping(path: Path = MAPPING_PATH) -> dict[str, Any]:
    mapping = json.loads(path.read_text(encoding="utf-8"))
    validate_mapping(mapping)
    return mapping


def lookup_security_subsector(
    security_code: str,
    as_of: str | date,
    expected_taxonomy_version: str,
    mapping: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic mapping state without inferring a subsector."""
    if not isinstance(security_code, str) or not security_code:
        raise ValueError("security_code must be a non-empty canonical string")
    target_date = date.fromisoformat(as_of) if isinstance(as_of, str) else as_of
    if not isinstance(target_date, date):
        raise ValueError("as_of must be an ISO date or date")
    if not expected_taxonomy_version:
        raise ValueError("expected_taxonomy_version must be non-empty")

    source = load_mapping() if mapping is None else mapping
    validate_mapping(source)

    active = []
    for record in source["records"]:
        if record["security_code"] != security_code:
            continue
        start = date.fromisoformat(record["effective_from"])
        end = date.fromisoformat(record["effective_to"]) if record["effective_to"] else None
        if start <= target_date and (end is None or target_date <= end):
            active.append(record)

    if len(active) > 1:
        raise ValueError(f"multiple active mappings for {security_code} on {target_date.isoformat()}")
    if not active:
        return {
            "status": "NO_EFFECTIVE_RECORD",
            "security_code": security_code,
            "subsector_id": None,
            "taxonomy_version": None,
        }

    record = active[0]
    if record["taxonomy_version"] != expected_taxonomy_version:
        return {
            "status": "TAXONOMY_MISMATCH",
            "security_code": security_code,
            "subsector_id": None,
            "taxonomy_version": record["taxonomy_version"],
        }
    if record["status"] == "UNMAPPED":
        return {
            "status": "UNMAPPED",
            "security_code": security_code,
            "subsector_id": None,
            "taxonomy_version": record["taxonomy_version"],
            "source_refs": record["source_refs"],
            "as_of": record["as_of"],
        }
    return {
        "status": "MAPPED",
        "security_code": security_code,
        "subsector_id": record["subsector_id"],
        "taxonomy_version": record["taxonomy_version"],
        "source_refs": record["source_refs"],
        "as_of": record["as_of"],
    }
