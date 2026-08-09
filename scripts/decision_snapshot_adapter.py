from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Iterable, Mapping

from scripts.investment_decision_journal import validate_decision


class DecisionSnapshotAdapterError(ValueError):
    pass


_COMPONENTS = (
    "portfolio",
    "market_price",
    "research",
    "valuation",
    "hypothesis",
    "expectations",
    "risk_preflight",
    "evidence",
    "checkpoints",
    "opportunity_set",
)

_REQUIRED_FOR_COMPLETE = {
    "portfolio",
    "market_price",
    "research",
    "valuation",
    "hypothesis",
    "expectations",
}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionSnapshotAdapterError(f"{field} must be a non-empty string")
    return value.strip()


def _dt(value: Any, field: str) -> datetime:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DecisionSnapshotAdapterError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise DecisionSnapshotAdapterError(f"{field} must include timezone")
    return parsed


def _record_time(record: Mapping[str, Any]) -> tuple[str, datetime]:
    for field in ("captured_at", "observed_at", "recorded_at"):
        if record.get(field) is not None:
            return field, _dt(record[field], field)
    raise DecisionSnapshotAdapterError(
        "source record requires captured_at, observed_at, or recorded_at; date-only as_of is not sufficient"
    )


def _validate_record(record: Mapping[str, Any], *, component: str, security_code: str) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise DecisionSnapshotAdapterError(f"{component} source must be an object")
    item = deepcopy(dict(record))
    if "owner_judgment" in item or "decision" in item:
        raise DecisionSnapshotAdapterError("snapshot adapter must not generate owner decision fields")
    if component not in {"evidence", "checkpoints", "opportunity_set"}:
        code = item.get("security_code")
        if code is not None and str(code) != security_code:
            raise DecisionSnapshotAdapterError(f"{component} security_code mismatch")
    _text(item.get("ref"), f"{component}.ref")
    _record_time(item)
    payload = item.get("data")
    if not isinstance(payload, Mapping):
        raise DecisionSnapshotAdapterError(f"{component}.data must be an object")
    item["data"] = deepcopy(dict(payload))
    return item


def _latest_before(
    records: Iterable[Mapping[str, Any]],
    *,
    component: str,
    security_code: str,
    decided_at: datetime,
) -> dict[str, Any] | None:
    eligible: list[tuple[datetime, str, dict[str, Any]]] = []
    for raw in records:
        item = _validate_record(raw, component=component, security_code=security_code)
        _, observed = _record_time(item)
        if observed <= decided_at:
            eligible.append((observed, item["ref"], item))
    if not eligible:
        return None
    eligible.sort(key=lambda entry: (entry[0], entry[1]))
    return eligible[-1][2]


def _component_default(component: str) -> dict[str, Any] | list[Any] | None:
    if component == "portfolio":
        return {
            "ref": None,
            "position_state": "UNKNOWN",
            "quantity": None,
            "account_context": "UNKNOWN",
            "as_of": None,
            "freshness": "UNKNOWN",
        }
    if component == "market_price":
        return {"value": None, "as_of": None, "source_ref": None, "status": "UNAVAILABLE"}
    if component == "research":
        return {"ref": None, "status": "MISSING"}
    if component == "valuation":
        return {
            "ref": None,
            "bear": None,
            "base": None,
            "bull": None,
            "target_fiscal_year": None,
            "price_as_of": None,
            "warnings": [],
        }
    if component == "hypothesis":
        return {
            "ref": None,
            "health": None,
            "must_happen": [],
            "invalidation_conditions": [],
            "next_checkpoints": [],
        }
    if component == "expectations":
        return {
            "ref": None,
            "status": "UNAVAILABLE",
            "company_guidance_ref": None,
            "external_consensus_ref": None,
            "sado_scenario_ref": None,
        }
    if component == "risk_preflight":
        return {"ref": None, "status": "NOT_RUN"}
    if component in {"evidence", "checkpoints"}:
        return []
    if component == "opportunity_set":
        return None
    raise DecisionSnapshotAdapterError(f"unsupported component: {component}")


def _project_single(component: str, record: dict[str, Any] | None) -> Any:
    if record is None:
        return _component_default(component)
    data = deepcopy(record["data"])
    if component in {"portfolio", "research", "valuation", "hypothesis", "expectations", "risk_preflight"}:
        data.setdefault("ref", record["ref"])
    if component == "market_price":
        data.setdefault("source_ref", record["ref"])
    if component == "opportunity_set":
        return record["ref"]
    return data


def _collect_multi(
    records: Iterable[Mapping[str, Any]],
    *,
    component: str,
    security_code: str,
    decided_at: datetime,
) -> list[str]:
    refs: list[tuple[datetime, str]] = []
    for raw in records:
        item = _validate_record(raw, component=component, security_code=security_code)
        _, observed = _record_time(item)
        if observed <= decided_at:
            refs.append((observed, item["ref"]))
    refs.sort(key=lambda item: (item[0], item[1]))
    return [ref for _, ref in refs]


def _is_missing(component: str, value: Any) -> bool:
    if component == "portfolio":
        return value.get("freshness") in {"UNKNOWN"} or value.get("ref") is None
    if component == "market_price":
        return value.get("status") in {"UNAVAILABLE"} or value.get("value") is None
    if component == "research":
        return value.get("status") in {"MISSING", "UNKNOWN"} or value.get("ref") is None
    if component == "valuation":
        return value.get("ref") is None or all(value.get(k) is None for k in ("bear", "base", "bull"))
    if component == "hypothesis":
        return value.get("ref") is None
    if component == "expectations":
        return value.get("status") in {"UNAVAILABLE"} or value.get("ref") is None
    return False


def build_decision_snapshot_bundle(
    decision: Mapping[str, Any],
    *,
    sources: Mapping[str, Iterable[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Build an immutable decision-time read/capture bundle without look-ahead.

    Source records must expose an explicit timezone-aware observation/capture timestamp.
    `as_of` alone is intentionally insufficient because it cannot prove that the artifact
    was available before the decision. The adapter never creates owner judgment fields.
    """
    validated = validate_decision(dict(decision))
    decided_at = _dt(validated["decided_at"], "decided_at")
    code = validated["security_code"]

    unknown_components = set(sources) - set(_COMPONENTS)
    if unknown_components:
        raise DecisionSnapshotAdapterError(f"unsupported source components: {sorted(unknown_components)}")

    bundle: dict[str, Any] = {
        "decision_ref": validated["decision_id"],
        "captured_at": validated["decided_at"],
        "security_code": code,
    }
    selected_refs: list[str] = []

    for component in _COMPONENTS:
        records = list(sources.get(component, []))
        if component in {"evidence", "checkpoints"}:
            value = _collect_multi(
                records,
                component=component,
                security_code=code,
                decided_at=decided_at,
            )
            bundle["evidence_refs" if component == "evidence" else "checkpoint_refs"] = value
            selected_refs.extend(value)
            continue
        selected = _latest_before(
            records,
            component=component,
            security_code=code,
            decided_at=decided_at,
        )
        projected = _project_single(component, selected)
        if component == "opportunity_set":
            bundle["opportunity_set_ref"] = projected
        else:
            bundle[component] = projected
        if selected is not None:
            selected_refs.append(selected["ref"])

    missing = [
        component
        for component in sorted(_REQUIRED_FOR_COMPLETE)
        if _is_missing(component, bundle[component])
    ]
    bundle["missing_components"] = missing
    if len(missing) == len(_REQUIRED_FOR_COMPLETE):
        bundle["snapshot_status"] = "UNKNOWN"
    elif missing:
        bundle["snapshot_status"] = "PARTIAL"
    else:
        bundle["snapshot_status"] = "COMPLETE"
    bundle["source_refs"] = sorted(set(selected_refs))
    return bundle


def capture_decision_snapshot_bundle(
    bundle: Mapping[str, Any], existing: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    current = deepcopy(dict(bundle))
    _text(current.get("decision_ref"), "decision_ref")
    _dt(current.get("captured_at"), "captured_at")
    _text(current.get("security_code"), "security_code")
    if current.get("snapshot_status") not in {"COMPLETE", "PARTIAL", "UNKNOWN"}:
        raise DecisionSnapshotAdapterError("unsupported snapshot_status")
    if existing is None:
        return current
    prior = deepcopy(dict(existing))
    if prior != current:
        raise DecisionSnapshotAdapterError("immutable decision snapshot bundle conflict")
    return prior
