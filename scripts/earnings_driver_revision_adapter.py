from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any, Mapping


class EarningsDriverRevisionError(ValueError):
    """Raised when driver revision/monitor integration would require guessing."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise EarningsDriverRevisionError(f"{field} is required")
    return text


def _number(value: Any, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EarningsDriverRevisionError(f"{field} must be canonical numeric or null")
    number = float(value)
    if not math.isfinite(number):
        raise EarningsDriverRevisionError(f"{field} must be finite")
    return number


def _node_map(model: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    nodes = model.get("nodes")
    if not isinstance(nodes, list):
        raise EarningsDriverRevisionError("model.nodes must be an array")
    result: dict[str, Mapping[str, Any]] = {}
    for raw in nodes:
        if not isinstance(raw, Mapping):
            raise EarningsDriverRevisionError("driver node must be a mapping")
        node_id = _required_text(raw.get("node_id"), "node_id")
        if node_id in result:
            raise EarningsDriverRevisionError(f"duplicate node_id: {node_id}")
        result[node_id] = raw
    return result


def _validate_same_model(before: Mapping[str, Any], after: Mapping[str, Any]) -> tuple[str, str]:
    before_security = _required_text(before.get("security_code"), "before.security_code")
    after_security = _required_text(after.get("security_code"), "after.security_code")
    if before_security != after_security:
        raise EarningsDriverRevisionError("security_code mismatch")
    before_fy = _required_text(before.get("target_fiscal_year"), "before.target_fiscal_year")
    after_fy = _required_text(after.get("target_fiscal_year"), "after.target_fiscal_year")
    if before_fy != after_fy:
        raise EarningsDriverRevisionError("target fiscal year mismatch")
    return before_security, before_fy


def build_driver_revision_context(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    revised_at: str,
    evidence_refs: list[str],
    reasoning: str,
    trigger_type: str = "KPI",
) -> dict[str, Any]:
    security_code, fiscal_year = _validate_same_model(before, after)
    before_nodes = _node_map(before)
    after_nodes = _node_map(after)
    if set(before_nodes) != set(after_nodes):
        raise EarningsDriverRevisionError("PR4 requires stable driver node identity; add/remove is reviewed separately")
    if not isinstance(evidence_refs, list) or not evidence_refs or not all(str(x).strip() for x in evidence_refs):
        raise EarningsDriverRevisionError("evidence_refs must be a non-empty explicit list")
    reasoning_text = _required_text(reasoning, "reasoning")
    revised_at_text = _required_text(revised_at, "revised_at")

    changes: list[dict[str, Any]] = []
    for node_id in sorted(before_nodes):
        old = before_nodes[node_id]
        new = after_nodes[node_id]
        for field in ("value", "assumption_text", "confidence"):
            old_value = old.get(field)
            new_value = new.get(field)
            if _canonical(old_value) == _canonical(new_value):
                continue
            item: dict[str, Any] = {
                "path": f"nodes.{node_id}.{field}",
                "node_id": node_id,
                "scenario": new.get("scenario"),
                "metric": new.get("metric"),
                "before": copy.deepcopy(old_value),
                "after": copy.deepcopy(new_value),
                "change_type": "UPDATED",
            }
            if field == "value":
                old_num = _number(old_value, f"{node_id}.before.value")
                new_num = _number(new_value, f"{node_id}.after.value")
                if old_num is not None and new_num is not None:
                    absolute = new_num - old_num
                    item["numeric_delta"] = {
                        "absolute": round(absolute, 10),
                        "pct": None if old_num == 0 else round(absolute / abs(old_num) * 100.0, 6),
                    }
            changes.append(item)

    if not changes:
        return {
            "status": "NO_REVISION",
            "security_code": security_code,
            "target_fiscal_year": fiscal_year,
            "changed_driver_nodes": [],
            "revision_record": None,
        }

    changed_node_ids = sorted({item["node_id"] for item in changes})
    identity_payload = {
        "security_code": security_code,
        "target_fiscal_year": fiscal_year,
        "revised_at": revised_at_text,
        "changed_node_ids": changed_node_ids,
    }
    digest = hashlib.sha256(_canonical(identity_payload).encode("utf-8")).hexdigest()[:16]
    record = {
        "entity_type": "COMPANY",
        "entity_id": security_code,
        "artifact_type": "SCENARIO",
        "artifact_ref": f"earnings-driver:{security_code}:{fiscal_year}",
        "revised_at": revised_at_text,
        "trigger_type": trigger_type,
        "change_summary": f"Earnings Driver changed: {', '.join(changed_node_ids)}",
        "changed_fields": changes,
        "reasoning": reasoning_text,
        "evidence_refs": copy.deepcopy(evidence_refs),
        "materiality": "MATERIAL",
        "author_type": "ANALYST",
        "as_of": revised_at_text.split("T", 1)[0],
        "driver_revision_context_id": f"driver-revision:{security_code}:{digest}",
    }
    return {
        "status": "REVISION_CONTEXT_READY",
        "security_code": security_code,
        "target_fiscal_year": fiscal_year,
        "changed_driver_nodes": changed_node_ids,
        "revision_record": record,
    }


def build_scenario_review_signal(
    model: Mapping[str, Any],
    *,
    kpi_id: str,
    evidence_ref: str,
    evidence_effect: str,
    affected_node_ids: list[str],
    observed_at: str,
    note: str,
) -> dict[str, Any]:
    security_code = _required_text(model.get("security_code"), "model.security_code")
    fiscal_year = _required_text(model.get("target_fiscal_year"), "model.target_fiscal_year")
    nodes = _node_map(model)
    kpi = _required_text(kpi_id, "kpi_id")
    evidence = _required_text(evidence_ref, "evidence_ref")
    observed = _required_text(observed_at, "observed_at")
    note_text = _required_text(note, "note")
    effect = _required_text(evidence_effect, "evidence_effect").upper()
    if effect not in {"SUPPORTS", "WEAKENS", "INVALIDATES", "NEUTRAL"}:
        raise EarningsDriverRevisionError("unsupported evidence_effect")
    if not isinstance(affected_node_ids, list) or not affected_node_ids:
        raise EarningsDriverRevisionError("affected_node_ids must be explicitly supplied")
    affected = sorted(set(_required_text(node_id, "affected_node_id") for node_id in affected_node_ids))
    missing = [node_id for node_id in affected if node_id not in nodes]
    if missing:
        raise EarningsDriverRevisionError(f"unknown affected node(s): {', '.join(missing)}")

    review_required = effect != "NEUTRAL"
    payload = {
        "security_code": security_code,
        "target_fiscal_year": fiscal_year,
        "kpi_id": kpi,
        "evidence_ref": evidence,
        "evidence_effect": effect,
        "affected_nodes": affected,
        "observed_at": observed,
        "note": note_text,
    }
    digest = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()[:16]
    return {
        "signal_id": f"scenario-review:{security_code}:{digest}",
        "status": "SCENARIO_REVIEW_REQUIRED" if review_required else "NO_SCENARIO_REVIEW",
        "security_code": security_code,
        "target_fiscal_year": fiscal_year,
        "kpi_id": kpi,
        "evidence_ref": evidence,
        "evidence_effect": effect,
        "affected_nodes": affected,
        "observed_at": observed,
        "note": note_text,
        "scenario_values_mutated": False,
        "trade_action": None,
    }
