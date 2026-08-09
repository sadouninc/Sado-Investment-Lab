from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ARTIFACT_TYPES = {"RESEARCH", "SCENARIO", "HYPOTHESIS", "VALUATION"}
TRIGGER_TYPES = {"EARNINGS", "IR", "POLICY", "KPI", "MANAGEMENT", "MARKET", "MANUAL_REVIEW", "OTHER"}
CHANGE_TYPES = {"UPDATED", "ADDED", "REMOVED", "CONFIRMED_UNCHANGED"}
MATERIALITY = {"NON_MATERIAL", "MATERIAL", "THESIS_CHANGING"}
AUTHOR_TYPES = {"OWNER", "SYSTEM", "ANALYST"}


class ResearchRevisionError(ValueError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def deterministic_revision_id(record: Mapping[str, Any]) -> str:
    required = ("entity_type", "entity_id", "artifact_type", "artifact_ref", "revised_at")
    values = [str(record.get(key) or "").strip() for key in required]
    if any(not value for value in values):
        raise ResearchRevisionError("revision identity fields are required")
    digest = hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()[:16]
    return f"revision:{values[1]}:{digest}"


def numeric_delta(before: Any, after: Any) -> dict[str, float | None]:
    if before is None or after is None or isinstance(before, bool) or isinstance(after, bool):
        return {"absolute": None, "pct": None}
    try:
        old = float(before)
        new = float(after)
    except (TypeError, ValueError):
        return {"absolute": None, "pct": None}
    absolute = new - old
    pct = None if old == 0 else absolute / abs(old) * 100.0
    return {"absolute": round(absolute, 10), "pct": None if pct is None else round(pct, 6)}


def changed_fields(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Deterministic top-level field diff for the v1 contract."""
    changes: list[dict[str, Any]] = []
    for key in sorted(set(before) | set(after)):
        old = before.get(key)
        new = after.get(key)
        if _canonical_json(old) == _canonical_json(new):
            continue
        if key not in before:
            change_type = "ADDED"
        elif key not in after:
            change_type = "REMOVED"
        else:
            change_type = "UPDATED"
        item = {"path": key, "before": old, "after": new, "change_type": change_type}
        delta = numeric_delta(old, new)
        if delta["absolute"] is not None:
            item["numeric_delta"] = delta
        changes.append(item)
    return changes


def validate_revision(record: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(record)
    required = (
        "entity_type", "entity_id", "artifact_type", "artifact_ref", "revised_at",
        "trigger_type", "change_summary", "changed_fields", "reasoning",
        "evidence_refs", "materiality", "author_type", "as_of",
    )
    missing = [key for key in required if result.get(key) in (None, "")]
    if missing:
        raise ResearchRevisionError("missing required fields: " + ", ".join(missing))
    if result["artifact_type"] not in ARTIFACT_TYPES:
        raise ResearchRevisionError("invalid artifact_type")
    if result["trigger_type"] not in TRIGGER_TYPES:
        raise ResearchRevisionError("invalid trigger_type")
    if result["materiality"] not in MATERIALITY:
        raise ResearchRevisionError("invalid materiality")
    if result["author_type"] not in AUTHOR_TYPES:
        raise ResearchRevisionError("invalid author_type")
    if not isinstance(result["changed_fields"], list) or not result["changed_fields"]:
        raise ResearchRevisionError("changed_fields must contain an actual artifact change")
    for change in result["changed_fields"]:
        if not isinstance(change, Mapping) or change.get("change_type") not in CHANGE_TYPES:
            raise ResearchRevisionError("invalid changed_fields entry")
        if not change.get("path"):
            raise ResearchRevisionError("changed field path is required")
    if not isinstance(result["evidence_refs"], list):
        raise ResearchRevisionError("evidence_refs must be an array")
    result["revision_id"] = deterministic_revision_id(result)
    result.setdefault("previous_revision_ref", None)
    return result


def scenario_numeric_change(
    *,
    field_path: str,
    before: float | int | None,
    after: float | int | None,
    before_target_fiscal_year: str,
    after_target_fiscal_year: str,
) -> dict[str, Any]:
    if before_target_fiscal_year != after_target_fiscal_year:
        raise ResearchRevisionError("FY mismatch: do not calculate a scenario revision delta across fiscal years")
    if before is None or after is None:
        raise ResearchRevisionError("missing previous/current value must not be treated as zero")
    delta = numeric_delta(before, after)
    return {
        "path": field_path,
        "before": before,
        "after": after,
        "change_type": "UPDATED",
        "target_fiscal_year": before_target_fiscal_year,
        "numeric_delta": delta,
    }


def load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_revision(path: Path, record: Mapping[str, Any]) -> str:
    candidate = validate_revision(record)
    history = load_history(path)
    same = [row for row in history if row.get("revision_id") == candidate["revision_id"]]
    if same:
        if any(_canonical_json(row) == _canonical_json(candidate) for row in same):
            return "UNCHANGED"
        raise ResearchRevisionError("conflicting payload for same revision identity")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(candidate, ensure_ascii=False, sort_keys=True) + "\n")
    return "INSERTED"
