from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping

from scripts.expectation_revision import validate_snapshot
from scripts.research_revision_ledger import validate_revision


class RevisionLeadTimeError(ValueError):
    """Raised when Sado-vs-consensus revision timing cannot be compared safely."""


SUPPORTED_DIRECTIONS = {"UP", "DOWN", "FLAT"}


def _dt(value: Any, field: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise RevisionLeadTimeError(f"{field} is required")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise RevisionLeadTimeError(f"{field} must include timezone")
    return parsed


def _direction(before: Any, after: Any) -> str:
    if before is None or after is None or isinstance(before, bool) or isinstance(after, bool):
        raise RevisionLeadTimeError("numeric before/after values are required")
    try:
        old = float(before)
        new = float(after)
    except (TypeError, ValueError) as exc:
        raise RevisionLeadTimeError("numeric before/after values are required") from exc
    delta = new - old
    if abs(delta) <= 1e-12:
        return "FLAT"
    return "UP" if delta > 0 else "DOWN"


def _mapped_change(revision: Mapping[str, Any], mapping: Mapping[str, Any]) -> dict[str, Any]:
    field_path = str(mapping.get("field_path") or "").strip()
    if not field_path:
        raise RevisionLeadTimeError("mapping.field_path is required")
    changes = [row for row in revision.get("changed_fields") or [] if str(row.get("path")) == field_path]
    if len(changes) != 1:
        raise RevisionLeadTimeError("exactly one mapped changed_field is required")
    return dict(changes[0])


def _basis_snapshot(snapshot: Mapping[str, Any], mapping: Mapping[str, Any], entity_id: str) -> bool:
    return (
        str(snapshot.get("security_code")) == entity_id
        and str(snapshot.get("target_fiscal_period")) == str(mapping.get("target_fiscal_period"))
        and str(snapshot.get("metric")) == str(mapping.get("metric"))
        and str(snapshot.get("unit")) == str(mapping.get("unit"))
        and str(snapshot.get("expectation_type")) == "CONSENSUS"
    )


def _consensus_revisions(
    history: Iterable[Mapping[str, Any]],
    *,
    mapping: Mapping[str, Any],
    entity_id: str,
) -> list[dict[str, Any]]:
    rows = [validate_snapshot(dict(raw)) for raw in history]
    rows = [row for row in rows if _basis_snapshot(row, mapping, entity_id)]
    rows = [row for row in rows if (row.get("coverage") or {}).get("status") != "UNAVAILABLE"]
    rows.sort(key=lambda row: (_dt(row.get("observed_at"), "observed_at"), str(row.get("expectation_id"))))

    revisions: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for row in rows:
        if previous is not None and previous.get("value") is not None and row.get("value") is not None:
            revisions.append(
                {
                    "from_ref": previous["expectation_id"],
                    "to_ref": row["expectation_id"],
                    "observed_at": row["observed_at"],
                    "before": float(previous["value"]),
                    "after": float(row["value"]),
                    "direction": _direction(previous["value"], row["value"]),
                }
            )
        previous = row
    return revisions


def measure_revision_lead_time(
    sado_revision_raw: Mapping[str, Any],
    expectation_history: Iterable[Mapping[str, Any]],
    *,
    mapping: Mapping[str, Any],
) -> dict[str, Any]:
    """Measure timing between one explicit Sado scenario revision and consensus revisions.

    This function measures observation timing only. A later consensus revision in the same
    direction is not interpreted as proof that the Sado forecast was correct or causal.
    """
    revision = validate_revision(sado_revision_raw)
    if revision.get("artifact_type") != "SCENARIO":
        raise RevisionLeadTimeError("artifact_type=SCENARIO is required")

    entity_id = str(revision.get("entity_id") or "").strip()
    if str(mapping.get("security_code") or entity_id) != entity_id:
        raise RevisionLeadTimeError("security_code mapping mismatch")
    for field in ("target_fiscal_period", "metric", "unit"):
        if not mapping.get(field):
            raise RevisionLeadTimeError(f"mapping.{field} is required")

    change = _mapped_change(revision, mapping)
    sado_direction = _direction(change.get("before"), change.get("after"))
    revised_at = _dt(revision.get("revised_at"), "revised_at")
    consensus = _consensus_revisions(expectation_history, mapping=mapping, entity_id=entity_id)

    prior_same_direction = [
        row for row in consensus
        if _dt(row["observed_at"], "observed_at") <= revised_at and row["direction"] == sado_direction
    ]
    if prior_same_direction:
        latest = prior_same_direction[-1]
        lag_hours = (revised_at - _dt(latest["observed_at"], "observed_at")).total_seconds() / 3600.0
        return {
            "security_code": entity_id,
            "revision_id": revision["revision_id"],
            "field_path": mapping["field_path"],
            "target_fiscal_period": mapping["target_fiscal_period"],
            "metric": mapping["metric"],
            "unit": mapping["unit"],
            "sado_direction": sado_direction,
            "sado_revised_at": revision["revised_at"],
            "status": "CONSENSUS_ALREADY_MOVED",
            "matching_consensus_revision_ref": latest["to_ref"],
            "matching_consensus_observed_at": latest["observed_at"],
            "lead_time_hours": None,
            "consensus_lead_hours": round(lag_hours, 6),
            "interpretation": "Consensus had already revised in the same direction before or at the Sado revision; do not classify as Sado-led.",
        }

    later_same_direction = [
        row for row in consensus
        if _dt(row["observed_at"], "observed_at") > revised_at and row["direction"] == sado_direction
    ]
    if not later_same_direction:
        return {
            "security_code": entity_id,
            "revision_id": revision["revision_id"],
            "field_path": mapping["field_path"],
            "target_fiscal_period": mapping["target_fiscal_period"],
            "metric": mapping["metric"],
            "unit": mapping["unit"],
            "sado_direction": sado_direction,
            "sado_revised_at": revision["revised_at"],
            "status": "NO_MATCHING_CONSENSUS_REVISION",
            "matching_consensus_revision_ref": None,
            "matching_consensus_observed_at": None,
            "lead_time_hours": None,
            "consensus_lead_hours": None,
            "interpretation": "No later same-basis consensus revision in the same direction is currently observed.",
        }

    matched = later_same_direction[0]
    lead_hours = (_dt(matched["observed_at"], "observed_at") - revised_at).total_seconds() / 3600.0
    return {
        "security_code": entity_id,
        "revision_id": revision["revision_id"],
        "field_path": mapping["field_path"],
        "target_fiscal_period": mapping["target_fiscal_period"],
        "metric": mapping["metric"],
        "unit": mapping["unit"],
        "sado_direction": sado_direction,
        "sado_revised_at": revision["revised_at"],
        "status": "SADO_REVISION_PRECEDED_MATCHING_CONSENSUS",
        "matching_consensus_revision_ref": matched["to_ref"],
        "matching_consensus_observed_at": matched["observed_at"],
        "lead_time_hours": round(lead_hours, 6),
        "consensus_lead_hours": None,
        "interpretation": "Sado revision was observed before the first later same-basis consensus revision in the same direction; this is timing evidence, not proof of forecast accuracy or causality.",
    }
