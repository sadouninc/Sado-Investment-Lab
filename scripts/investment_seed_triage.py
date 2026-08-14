from __future__ import annotations

from copy import deepcopy
from typing import Any

TRIAGE_DIMENSIONS = (
    "novelty",
    "magnitude",
    "transmission_plausibility",
    "signal_lead",
    "japan_equity_relevance",
    "expectation_gap_potential",
    "evidence_quality",
    "counter_evidence_strength",
)
LEVELS = {"UNKNOWN", "LOW", "MEDIUM", "HIGH"}


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _string_list(value: Any, field: str, *, required: bool = False) -> list[str]:
    if value is None:
        value = []
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    result = [_require_text(item, f"{field} entry") for item in value]
    if required and not result:
        raise ValueError(f"{field} must contain at least one entry")
    return result


def _validate_dimension(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    level = _require_text(value.get("level"), f"{field}.level").upper()
    if level not in LEVELS:
        raise ValueError(f"unsupported {field}.level: {level}")
    rationale = _require_text(value.get("rationale"), f"{field}.rationale")
    evidence_refs = _string_list(value.get("evidence_refs"), f"{field}.evidence_refs")
    return {
        "level": level,
        "rationale": rationale,
        "evidence_refs": evidence_refs,
    }


def _validate_evidence_entries(value: Any, field: str) -> list[dict[str, Any]]:
    if value is None:
        value = []
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    result: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(value):
        prefix = f"{field}[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{prefix} must be an object")
        evidence_id = _require_text(item.get("evidence_id"), f"{prefix}.evidence_id")
        if evidence_id in seen_ids:
            raise ValueError(f"duplicate evidence_id: {evidence_id}")
        seen_ids.add(evidence_id)
        result.append(
            {
                "evidence_id": evidence_id,
                "statement": _require_text(item.get("statement"), f"{prefix}.statement"),
                "source_refs": _string_list(
                    item.get("source_refs"),
                    f"{prefix}.source_refs",
                    required=True,
                ),
            }
        )
    return result


def validate_triage_contract(contract: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(contract, dict):
        raise ValueError("triage contract must be an object")
    result = deepcopy(contract)
    result["origin_seed_ref"] = _require_text(result.get("origin_seed_ref"), "origin_seed_ref")

    provenance = result.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("provenance must be an object")
    result["provenance"] = {
        "observation_refs": _string_list(
            provenance.get("observation_refs"),
            "provenance.observation_refs",
            required=True,
        ),
        "inference_refs": _string_list(
            provenance.get("inference_refs"),
            "provenance.inference_refs",
        ),
    }

    dimensions = result.get("dimensions")
    if not isinstance(dimensions, dict):
        raise ValueError("dimensions must be an object")
    missing = [name for name in TRIAGE_DIMENSIONS if name not in dimensions]
    extra = sorted(set(dimensions) - set(TRIAGE_DIMENSIONS))
    if missing:
        raise ValueError(f"missing triage dimensions: {', '.join(missing)}")
    if extra:
        raise ValueError(f"unsupported triage dimensions: {', '.join(extra)}")
    result["dimensions"] = {
        name: _validate_dimension(dimensions[name], f"dimensions.{name}")
        for name in TRIAGE_DIMENSIONS
    }

    result["evidence"] = _validate_evidence_entries(result.get("evidence"), "evidence")
    result["counter_evidence"] = _validate_evidence_entries(
        result.get("counter_evidence"), "counter_evidence"
    )
    evidence_ids = {item["evidence_id"] for item in result["evidence"]}
    counter_ids = {item["evidence_id"] for item in result["counter_evidence"]}
    overlap = evidence_ids & counter_ids
    if overlap:
        raise ValueError(
            "evidence and counter_evidence IDs must remain distinct: "
            + ", ".join(sorted(overlap))
        )
    all_evidence_ids = evidence_ids | counter_ids
    for name, dimension in result["dimensions"].items():
        unknown = sorted(set(dimension["evidence_refs"]) - all_evidence_ids)
        if unknown:
            raise ValueError(
                f"dimensions.{name}.evidence_refs contain unknown refs: "
                + ", ".join(unknown)
            )

    result["transmission_paths"] = _string_list(
        result.get("transmission_paths"), "transmission_paths"
    )
    result["japan_equity_links"] = _string_list(
        result.get("japan_equity_links"), "japan_equity_links"
    )
    result["next_checkpoint"] = (
        None
        if result.get("next_checkpoint") is None
        else _require_text(result.get("next_checkpoint"), "next_checkpoint")
    )
    result["beyond_topic_reason"] = (
        None
        if result.get("beyond_topic_reason") is None
        else _require_text(result.get("beyond_topic_reason"), "beyond_topic_reason")
    )
    return result


def evaluate_research_candidate_readiness(contract: dict[str, Any]) -> dict[str, Any]:
    """Evaluate explicit promotion evidence without mutating lifecycle or making an investment decision."""
    validated = validate_triage_contract(contract)
    blockers: list[dict[str, str]] = []
    passed: list[str] = []

    def check(condition: bool, code: str, message: str) -> None:
        if condition:
            passed.append(code)
        else:
            blockers.append({"code": code, "message": message})

    check(
        bool(validated["evidence"]),
        "EVIDENCE_PRESENT",
        "At least one evidence item is required.",
    )
    check(
        bool(validated["transmission_paths"]),
        "TRANSMISSION_PATH_PRESENT",
        "At least one transmission path must be explainable.",
    )
    check(
        bool(validated["japan_equity_links"]),
        "JAPAN_EQUITY_LINK_PRESENT",
        "A Japan equity candidate or value-chain exploration target is required.",
    )
    check(
        bool(validated["counter_evidence"]),
        "COUNTER_EVIDENCE_PRESENT",
        "At least one explicit counter-evidence item or falsification condition is required.",
    )
    check(
        validated["next_checkpoint"] is not None,
        "NEXT_CHECKPOINT_PRESENT",
        "A next checkpoint is required.",
    )
    check(
        validated["beyond_topic_reason"] is not None,
        "BEYOND_TOPIC_REASON_PRESENT",
        "Explain why the seed is more than topical attention.",
    )

    passed.append("TRIAGE_DIMENSIONS_EXPLICIT")

    return {
        "origin_seed_ref": validated["origin_seed_ref"],
        "decision": (
            "READY_FOR_RESEARCH_CANDIDATE" if not blockers else "NEEDS_MORE_EVIDENCE"
        ),
        "passed_checks": passed,
        "blocking_reasons": blockers,
        "dimension_snapshot": {
            name: validated["dimensions"][name]["level"] for name in TRIAGE_DIMENSIONS
        },
        "auto_transition": False,
        "investment_decision": None,
    }
