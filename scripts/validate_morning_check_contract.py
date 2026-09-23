#!/usr/bin/env python3
"""Pure, deterministic validator for the Morning Check v1 contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_SECTIONS = (
    "Overnight",
    "Japan Setup",
    "Money Flow",
    "Portfolio Risk",
    "Watchlist",
    "Events",
    "Morning Hypothesis",
    "Confidence+Invalidation",
)
ALLOWED_SOURCE_CLASSES = {"github_ssot", "current_market", "official_ir", "derived"}
ALLOWED_MISSING_POLICIES = {"UNKNOWN", "MISSING"}


def validate_contract(contract: Any) -> list[str]:
    """Return deterministic validation errors; an empty list means valid."""
    errors: list[str] = []
    if not isinstance(contract, dict):
        return ["contract must be a JSON object"]

    routine_version = contract.get("routine_version")
    if not isinstance(routine_version, str) or not routine_version.strip():
        errors.append("routine_version must be a non-empty string")

    if contract.get("owner_final_judgment_required") is not True:
        errors.append("owner_final_judgment_required must be true")

    separation = contract.get("separation")
    if not isinstance(separation, dict) or any(
        separation.get(key) is not True for key in ("fact", "hypothesis", "action_candidate")
    ):
        errors.append("fact/hypothesis/action_candidate separation must be explicitly true")

    sections = contract.get("sections")
    if not isinstance(sections, list):
        errors.append("sections must be a list")
        return errors

    names = [section.get("name") if isinstance(section, dict) else None for section in sections]
    if names != list(REQUIRED_SECTIONS):
        errors.append("sections must contain the required 8 names exactly once and in order")

    for section_index, section in enumerate(sections):
        if not isinstance(section, dict):
            errors.append(f"sections[{section_index}] must be an object")
            continue
        for input_kind in ("required_inputs", "optional_inputs"):
            inputs = section.get(input_kind)
            if not isinstance(inputs, list):
                errors.append(f"sections[{section_index}].{input_kind} must be a list")
                continue
            for input_index, item in enumerate(inputs):
                prefix = f"sections[{section_index}].{input_kind}[{input_index}]"
                if not isinstance(item, dict):
                    errors.append(f"{prefix} must be an object")
                    continue
                if item.get("source_class") not in ALLOWED_SOURCE_CLASSES:
                    errors.append(f"{prefix}.source_class is not allowed")
                policy = item.get("missing_policy")
                if policy not in ALLOWED_MISSING_POLICIES:
                    errors.append(f"{prefix}.missing_policy must be UNKNOWN or MISSING")

    return errors


def load_contract(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    errors = validate_contract(load_contract(args.path))
    if errors:
        for error in errors:
            print(error)
        return 1
    print("VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
