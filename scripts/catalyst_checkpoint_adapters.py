from __future__ import annotations

from typing import Any, Mapping

from scripts.catalyst_calendar import CalendarValidationError, EventRecord


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CalendarValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _schedule_fields(raw: Mapping[str, Any]) -> dict[str, Any]:
    precision = str(raw.get("date_precision") or "UNKNOWN").upper()
    payload: dict[str, Any] = {"date_precision": precision}
    allowed = {
        "DATETIME": "scheduled_at",
        "DATE": "scheduled_date",
        "MONTH": "scheduled_month",
    }
    if precision in allowed:
        key = allowed[precision]
        payload[key] = raw.get(key)
    elif precision == "WINDOW":
        payload["window_start"] = raw.get("window_start")
        payload["window_end"] = raw.get("window_end")
    elif precision != "UNKNOWN":
        raise CalendarValidationError(f"unsupported date_precision: {precision}")
    return payload


def build_hypothesis_checkpoint_event(
    hypothesis: Mapping[str, Any], checkpoint: Mapping[str, Any] | str
) -> EventRecord:
    """Project an explicit #130 checkpoint into the shared #151 Event contract.

    String checkpoints are preserved as UNKNOWN-date events instead of inventing a
    date. Structured checkpoints may provide an explicit precision/schedule.
    """

    security_code = _text(hypothesis.get("security_code"), "security_code")
    hypothesis_ref = _text(
        hypothesis.get("hypothesis_id") or hypothesis.get("source_research_ref"),
        "hypothesis_ref",
    )

    if isinstance(checkpoint, str):
        title = _text(checkpoint, "checkpoint")
        raw: Mapping[str, Any] = {
            "checkpoint_key": title,
            "title": title,
            "date_precision": "UNKNOWN",
            "source_ref": hypothesis_ref,
            "authority": "INTERNAL",
            "status": "DISCOVERED",
        }
    elif isinstance(checkpoint, Mapping):
        raw = checkpoint
        title = _text(raw.get("title") or raw.get("checkpoint"), "checkpoint.title")
    else:
        raise CalendarValidationError("checkpoint must be a string or object")

    event_key = _text(
        raw.get("checkpoint_key") or raw.get("event_key") or title,
        "checkpoint_key",
    )
    payload = {
        "event_key": event_key,
        "event_type": "HYPOTHESIS_CHECKPOINT",
        "entity_type": "HYPOTHESIS",
        "entity_id": hypothesis_ref,
        "title": title,
        "source_ref": raw.get("source_ref") or hypothesis_ref,
        "authority": raw.get("authority", "INTERNAL"),
        "status": raw.get("status", "SCHEDULED" if str(raw.get("date_precision") or "UNKNOWN").upper() != "UNKNOWN" else "DISCOVERED"),
        "expected_review": raw.get("expected_review", ["REVIEW_THESIS"]),
        "related_refs": sorted({hypothesis_ref, f"company:{security_code}"}),
        **_schedule_fields(raw),
    }
    return EventRecord.from_mapping(payload)


def build_decision_review_event(
    decision: Mapping[str, Any], review_checkpoint: Mapping[str, Any]
) -> EventRecord:
    """Project an explicit #133 review due/checkpoint into the shared Event contract.

    A review date is never derived from the original decision timestamp. The caller
    must provide explicit schedule precision or UNKNOWN.
    """

    decision_id = _text(decision.get("decision_id"), "decision_id")
    security_code = _text(decision.get("security_code"), "security_code")
    title = _text(
        review_checkpoint.get("title") or "Decision review",
        "review_checkpoint.title",
    )
    event_key = _text(
        review_checkpoint.get("event_key") or f"{decision_id}:review",
        "review_checkpoint.event_key",
    )
    payload = {
        "event_key": event_key,
        "event_type": "DECISION_REVIEW",
        "entity_type": "DECISION",
        "entity_id": decision_id,
        "title": title,
        "source_ref": review_checkpoint.get("source_ref") or decision_id,
        "authority": review_checkpoint.get("authority", "INTERNAL"),
        "status": review_checkpoint.get("status", "SCHEDULED" if str(review_checkpoint.get("date_precision") or "UNKNOWN").upper() != "UNKNOWN" else "DISCOVERED"),
        "expected_review": review_checkpoint.get("expected_review", ["REVIEW_DECISION"]),
        "related_refs": sorted({decision_id, f"company:{security_code}"}),
        **_schedule_fields(review_checkpoint),
    }
    return EventRecord.from_mapping(payload)
