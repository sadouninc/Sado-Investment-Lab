#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = [
    "Overnight", "Japan Setup", "Money Flow", "Portfolio Risk",
    "Watchlist", "Events", "Morning Hypothesis", "Confidence+Invalidation",
]
SOURCE_CLASSES = {"github_ssot", "current_market", "official_ir", "derived"}
MISSING_POLICIES = {"UNKNOWN", "MISSING"}
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def validate(contract):
    errors = []
    if not isinstance(contract, dict):
        return ["contract must be a JSON object"]

    version = contract.get("routine_version")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        errors.append("routine_version must be non-empty semver")
    if contract.get("owner_final_judgment_required") is not True:
        errors.append("owner_final_judgment_required must be true")
    if contract.get("missing_data_policy") != "UNKNOWN_OR_MISSING_NO_SILENT_ZERO_OR_NEUTRAL":
        errors.append("missing_data_policy must prohibit silent zero/neutral coercion")
    if contract.get("separation") != ["fact", "hypothesis", "action-candidate"]:
        errors.append("fact/hypothesis/action-candidate separation is required")

    sections = contract.get("sections")
    if not isinstance(sections, list):
        errors.append("required sections must exist exactly once in canonical order")
        return errors
    if any(not isinstance(section, dict) for section in sections):
        errors.append("each section must be an object")
        return errors
    if [section.get("name") for section in sections] != REQUIRED_SECTIONS:
        errors.append("required sections must exist exactly once in canonical order")
        return errors

    for section in sections:
        name = section.get("name")
        for key in ("required_inputs", "optional_inputs"):
            inputs = section.get(key)
            if not isinstance(inputs, list):
                errors.append(f"{name}.{key} must be a list")
                continue
            for item in inputs:
                if not isinstance(item, dict):
                    errors.append(f"{name}.{key} input must be an object")
                    continue
                if item.get("source_class") not in SOURCE_CLASSES:
                    errors.append(f"{name}.{key} has unknown source_class")
                    continue
                if key == "required_inputs" and item.get("missing_policy") not in MISSING_POLICIES:
                    errors.append(f"{name} required input needs UNKNOWN/MISSING policy")
    return errors


def _result(errors):
    print(json.dumps({"valid": False, "errors": errors}, ensure_ascii=False, sort_keys=True))
    return 1


def main(path=None):
    if not path:
        return _result(["contract path argument is required"])
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return _result([f"contract file unreadable: {exc.__class__.__name__}"])
    try:
        contract = json.loads(raw)
    except json.JSONDecodeError:
        return _result(["contract file contains invalid JSON"])

    errors = validate(contract)
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) == 2 else None))
