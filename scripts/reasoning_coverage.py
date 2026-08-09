#!/usr/bin/env python3
"""Deterministic read-only Reasoning Coverage projection for Issue #271 PR1."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

SECTION_ORDER = (
    "why_candidate",
    "business_driver",
    "base_scenario",
    "bear_bull_range",
    "valuation",
    "hypothesis",
    "invalidation",
    "market_expectation",
    "next_evidence",
)

SECTION_STATUSES = {
    "why_candidate": {"SUPPORTED", "PARTIAL", "UNKNOWN"},
    "business_driver": {"SUPPORTED", "PARTIAL", "UNKNOWN"},
    "base_scenario": {"SUPPORTED", "PARTIAL", "OWNER_ASSUMPTION", "UNKNOWN"},
    "bear_bull_range": {"SUPPORTED", "PARTIAL", "UNKNOWN"},
    "valuation": {"SUPPORTED", "PARTIAL", "STALE", "UNKNOWN"},
    "hypothesis": {"SUPPORTED", "PARTIAL", "NOT_YET_DEFINED", "CONFLICTING"},
    "invalidation": {"DEFINED", "PARTIAL", "NOT_YET_DEFINED"},
    "market_expectation": {"SUPPORTED", "PARTIAL", "UNAVAILABLE", "UNKNOWN"},
    "next_evidence": {"DEFINED", "PARTIAL", "UNKNOWN"},
}

PROVENANCE = {
    "KNOWN_FACT",
    "SUPPORTED_INTERPRETATION",
    "OWNER_ASSUMPTION",
    "SYSTEM_DERIVED",
    "UNKNOWN",
    "NOT_YET_DEFINED",
    "CONFLICTING",
    "STALE",
}

OVERALL = {"WELL_SUPPORTED", "PARTIAL", "RESEARCH_GAPS", "CONFLICTING"}


class ReasoningCoverageError(ValueError):
    pass


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReasoningCoverageError(f"{field} must be a non-empty string")
    return value.strip()


def _refs(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ReasoningCoverageError(f"{field} must be an array")
    result = []
    for index, item in enumerate(value):
        result.append(_text(item, f"{field}[{index}]"))
    return sorted(set(result))


def _uncertainties(value: Any, field: str, *, owner_only: bool = False) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ReasoningCoverageError(f"{field} must be an array")
    result: list[dict[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ReasoningCoverageError(f"{field}[{index}] must be an object")
        text = _text(item.get("text"), f"{field}[{index}].text")
        provenance = _text(item.get("provenance"), f"{field}[{index}].provenance")
        if provenance not in PROVENANCE:
            raise ReasoningCoverageError(f"unsupported provenance: {provenance}")
        if owner_only and provenance != "OWNER_ASSUMPTION":
            raise ReasoningCoverageError("owner_uncertainties must remain owner-entered OWNER_ASSUMPTION")
        result.append({"text": text, "provenance": provenance})
    return sorted(result, key=lambda row: (row["provenance"], row["text"]))


def _validate_section(name: str, raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ReasoningCoverageError(f"sections.{name} must be an object")
    status = _text(raw.get("status"), f"sections.{name}.status")
    if status not in SECTION_STATUSES[name]:
        raise ReasoningCoverageError(f"unsupported {name} status: {status}")
    out: dict[str, Any] = {"status": status}
    for key in ("refs", "assumption_refs"):
        if key in raw:
            out[key] = _refs(raw.get(key), f"sections.{name}.{key}")
    if "value_ref" in raw:
        value_ref = raw.get("value_ref")
        out["value_ref"] = None if value_ref is None else _text(value_ref, f"sections.{name}.value_ref")
    if "uncertainties" in raw:
        out["uncertainties"] = _uncertainties(raw.get("uncertainties"), f"sections.{name}.uncertainties")
    if "conditions" in raw:
        out["conditions"] = _refs(raw.get("conditions"), f"sections.{name}.conditions")
    if "items" in raw:
        out["items"] = _refs(raw.get("items"), f"sections.{name}.items")
    if "known" in raw:
        out["known"] = _refs(raw.get("known"), f"sections.{name}.known")
    return out


def _derive_overall(sections: dict[str, dict[str, Any]]) -> str:
    statuses = [sections[name]["status"] for name in SECTION_ORDER]
    if "CONFLICTING" in statuses:
        return "CONFLICTING"
    gap_states = {"UNKNOWN", "NOT_YET_DEFINED", "UNAVAILABLE"}
    if any(status in gap_states for status in statuses):
        return "RESEARCH_GAPS"
    partial_states = {"PARTIAL", "OWNER_ASSUMPTION", "STALE"}
    if any(status in partial_states for status in statuses):
        return "PARTIAL"
    return "WELL_SUPPORTED"


def project_reasoning_coverage(record: dict[str, Any]) -> dict[str, Any]:
    """Validate and canonicalize a coverage projection without mutating upstream artifacts.

    PR1 intentionally does not generate prompts, research actions, trade recommendations,
    scores, confidence, or inferred Owner reasons. Those belong to later slices or Owner input.
    """
    if not isinstance(record, dict):
        raise ReasoningCoverageError("coverage input must be an object")
    source = deepcopy(record)
    security_code = _text(source.get("security_code"), "security_code")
    as_of = _text(source.get("as_of"), "as_of")
    raw_sections = source.get("sections")
    if not isinstance(raw_sections, dict):
        raise ReasoningCoverageError("sections must be an object")
    missing = [name for name in SECTION_ORDER if name not in raw_sections]
    if missing:
        raise ReasoningCoverageError(f"missing coverage sections: {', '.join(missing)}")
    unknown = sorted(set(raw_sections) - set(SECTION_ORDER))
    if unknown:
        raise ReasoningCoverageError(f"unknown coverage sections: {', '.join(unknown)}")

    sections = {name: _validate_section(name, raw_sections[name]) for name in SECTION_ORDER}
    owner_uncertainties = _uncertainties(source.get("owner_uncertainties"), "owner_uncertainties", owner_only=True)
    system_uncertainties = _uncertainties(source.get("system_uncertainties"), "system_uncertainties")
    canonical_refs = _refs(source.get("canonical_refs"), "canonical_refs")

    overall = _derive_overall(sections)
    supplied_overall = source.get("overall")
    if supplied_overall is not None:
        supplied = _text(supplied_overall, "overall")
        if supplied not in OVERALL or supplied != overall:
            raise ReasoningCoverageError("overall must match deterministic section projection")

    return {
        "schema_version": 1,
        "security_code": security_code,
        "as_of": as_of,
        "sections": sections,
        "canonical_refs": canonical_refs,
        "owner_uncertainties": owner_uncertainties,
        "system_uncertainties": system_uncertainties,
        "next_research_actions": [],
        "overall": overall,
    }
