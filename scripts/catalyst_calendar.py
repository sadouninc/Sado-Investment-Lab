from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from typing import Any, Mapping

EVENT_TYPES = {
    "EARNINGS",
    "IR",
    "POLICY",
    "TENDER",
    "PRODUCT",
    "KPI",
    "HYPOTHESIS_CHECKPOINT",
    "VALUATION_REVIEW",
    "DECISION_REVIEW",
    "OTHER",
}
ENTITY_TYPES = {"COMPANY", "THEME", "HYPOTHESIS", "DECISION", "POLICY"}
DATE_PRECISIONS = {"DATETIME", "DATE", "MONTH", "WINDOW", "UNKNOWN"}
AUTHORITIES = {"PRIMARY", "SECONDARY", "INTERNAL"}
EVENT_STATUSES = {
    "DISCOVERED",
    "SCHEDULED",
    "OCCURRED",
    "HANDLED",
    "DELAYED",
    "CANCELLED",
    "UNKNOWN",
}
EXPECTED_REVIEWS = {
    "REFRESH_RESEARCH",
    "REVIEW_THESIS",
    "UPDATE_VALUATION",
    "REVIEW_DECISION",
    "REVIEW_POLICY_TRANSMISSION",
}


class CalendarValidationError(ValueError):
    """Raised when an event violates the canonical calendar contract."""


def _text(value: Any, field: str, *, required: bool = True) -> str | None:
    if value is None:
        if required:
            raise CalendarValidationError(f"{field} is required")
        return None
    text = str(value).strip()
    if required and not text:
        raise CalendarValidationError(f"{field} is required")
    return text or None


def _enum(value: Any, field: str, allowed: set[str]) -> str:
    text = _text(value, field)
    assert text is not None
    normalized = text.upper()
    if normalized not in allowed:
        raise CalendarValidationError(
            f"unsupported {field}: {normalized}; allowed={sorted(allowed)}"
        )
    return normalized


def _iso_datetime(value: Any, field: str) -> str:
    text = _text(value, field)
    assert text is not None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CalendarValidationError(f"{field} must be ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        raise CalendarValidationError(f"{field} must include timezone information")
    return text


def _iso_date(value: Any, field: str) -> str:
    text = _text(value, field)
    assert text is not None
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise CalendarValidationError(f"{field} must be YYYY-MM-DD") from exc
    return text


def _month(value: Any, field: str) -> str:
    text = _text(value, field)
    assert text is not None
    try:
        datetime.strptime(text, "%Y-%m")
    except ValueError as exc:
        raise CalendarValidationError(f"{field} must be YYYY-MM") from exc
    return text


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest[:24]}"


def deterministic_event_id(
    *, entity_type: str, entity_id: str, event_type: str, event_key: str
) -> str:
    """Identity intentionally excludes schedule fields so reschedules retain one event."""

    payload = {
        "entity_type": _enum(entity_type, "entity_type", ENTITY_TYPES),
        "entity_id": _text(entity_id, "entity_id"),
        "event_type": _enum(event_type, "event_type", EVENT_TYPES),
        "event_key": _text(event_key, "event_key"),
    }
    return _stable_id("event", payload)


@dataclass(frozen=True)
class ScheduleRevision:
    date_precision: str
    scheduled_at: str | None = None
    scheduled_date: str | None = None
    scheduled_month: str | None = None
    window_start: str | None = None
    window_end: str | None = None
    status: str = "SCHEDULED"
    changed_at: str | None = None
    reason: str | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "ScheduleRevision":
        precision = _enum(raw.get("date_precision"), "date_precision", DATE_PRECISIONS)
        status = _enum(raw.get("status", "SCHEDULED"), "status", EVENT_STATUSES)
        values = _validate_schedule_fields(raw, precision)
        changed_at = raw.get("changed_at")
        return cls(
            date_precision=precision,
            status=status,
            changed_at=_iso_datetime(changed_at, "changed_at") if changed_at else None,
            reason=_text(raw.get("reason"), "reason", required=False),
            **values,
        )


@dataclass(frozen=True)
class EventRecord:
    event_id: str
    event_key: str
    event_type: str
    entity_type: str
    entity_id: str
    title: str
    date_precision: str
    scheduled_at: str | None
    scheduled_date: str | None
    scheduled_month: str | None
    window_start: str | None
    window_end: str | None
    source_ref: str | None
    authority: str
    status: str
    expected_review: tuple[str, ...]
    related_refs: tuple[str, ...]
    schedule_history: tuple[ScheduleRevision, ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "EventRecord":
        allowed = {
            "event_id", "event_key", "event_type", "entity_type", "entity_id", "title",
            "date_precision", "scheduled_at", "scheduled_date", "scheduled_month",
            "window_start", "window_end", "source_ref", "authority", "status",
            "expected_review", "related_refs", "schedule_history",
        }
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise CalendarValidationError(f"EventRecord contains unsupported fields: {', '.join(unknown)}")

        event_type = _enum(raw.get("event_type"), "event_type", EVENT_TYPES)
        entity_type = _enum(raw.get("entity_type"), "entity_type", ENTITY_TYPES)
        entity_id = _text(raw.get("entity_id"), "entity_id")
        event_key = _text(raw.get("event_key"), "event_key")
        assert entity_id is not None and event_key is not None
        expected_id = deterministic_event_id(
            entity_type=entity_type,
            entity_id=entity_id,
            event_type=event_type,
            event_key=event_key,
        )
        supplied = _text(raw.get("event_id"), "event_id", required=False)
        if supplied is not None and supplied != expected_id:
            raise CalendarValidationError("event_id does not match deterministic identity")

        precision = _enum(raw.get("date_precision"), "date_precision", DATE_PRECISIONS)
        schedule = _validate_schedule_fields(raw, precision)
        expected_review = tuple(_validate_reviews(raw.get("expected_review", [])))
        related_refs = tuple(sorted({_text(x, "related_ref") for x in raw.get("related_refs", [])}))
        history = tuple(
            ScheduleRevision.from_mapping(item) for item in raw.get("schedule_history", [])
        )

        return cls(
            event_id=expected_id,
            event_key=event_key,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            title=_text(raw.get("title"), "title") or "",
            source_ref=_text(raw.get("source_ref"), "source_ref", required=False),
            authority=_enum(raw.get("authority"), "authority", AUTHORITIES),
            status=_enum(raw.get("status"), "status", EVENT_STATUSES),
            expected_review=expected_review,
            related_refs=related_refs,
            schedule_history=history,
            date_precision=precision,
            **schedule,
        )

    def current_schedule(self) -> ScheduleRevision:
        return ScheduleRevision(
            date_precision=self.date_precision,
            scheduled_at=self.scheduled_at,
            scheduled_date=self.scheduled_date,
            scheduled_month=self.scheduled_month,
            window_start=self.window_start,
            window_end=self.window_end,
            status=self.status,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["expected_review"] = list(self.expected_review)
        payload["related_refs"] = list(self.related_refs)
        payload["schedule_history"] = [asdict(x) for x in self.schedule_history]
        return payload


def _validate_reviews(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple)):
        raise CalendarValidationError("expected_review must be an array")
    normalized = []
    for value in values:
        item = _enum(value, "expected_review", EXPECTED_REVIEWS)
        if item not in normalized:
            normalized.append(item)
    return sorted(normalized)


def _validate_schedule_fields(raw: Mapping[str, Any], precision: str) -> dict[str, str | None]:
    scheduled_at = raw.get("scheduled_at")
    scheduled_date = raw.get("scheduled_date")
    scheduled_month = raw.get("scheduled_month")
    window_start = raw.get("window_start")
    window_end = raw.get("window_end")

    result = {
        "scheduled_at": None,
        "scheduled_date": None,
        "scheduled_month": None,
        "window_start": None,
        "window_end": None,
    }
    supplied = [x for x in (scheduled_at, scheduled_date, scheduled_month, window_start, window_end) if x]

    if precision == "DATETIME":
        if len(supplied) != 1 or not scheduled_at:
            raise CalendarValidationError("DATETIME requires only scheduled_at")
        result["scheduled_at"] = _iso_datetime(scheduled_at, "scheduled_at")
    elif precision == "DATE":
        if len(supplied) != 1 or not scheduled_date:
            raise CalendarValidationError("DATE requires only scheduled_date")
        result["scheduled_date"] = _iso_date(scheduled_date, "scheduled_date")
    elif precision == "MONTH":
        if len(supplied) != 1 or not scheduled_month:
            raise CalendarValidationError("MONTH requires only scheduled_month")
        result["scheduled_month"] = _month(scheduled_month, "scheduled_month")
    elif precision == "WINDOW":
        if len(supplied) != 2 or not window_start or not window_end:
            raise CalendarValidationError("WINDOW requires window_start and window_end only")
        start = _iso_date(window_start, "window_start")
        end = _iso_date(window_end, "window_end")
        if end < start:
            raise CalendarValidationError("window_end must not precede window_start")
        result["window_start"] = start
        result["window_end"] = end
    elif precision == "UNKNOWN":
        if supplied:
            raise CalendarValidationError("UNKNOWN must not fabricate schedule fields")
    return result


def reschedule_event(
    event: EventRecord,
    new_schedule: Mapping[str, Any],
    *,
    changed_at: str,
    reason: str | None = None,
) -> EventRecord:
    """Reschedule a currently SCHEDULED event while preserving old schedule history.

    Rescheduling is intentionally fail-closed for every other lifecycle state.
    OCCURRED/HANDLED/CANCELLED events must never be implicitly reopened. A
    DISCOVERED or UNKNOWN event needs an explicit scheduling transition, while
    DELAYED is represented as a historical schedule revision created by this
    operation before the current event returns to SCHEDULED with the new date.
    """

    if event.status != "SCHEDULED":
        raise CalendarValidationError(
            f"cannot reschedule {event.status} event; only SCHEDULED events may be rescheduled"
        )

    changed_at = _iso_datetime(changed_at, "changed_at")
    old = replace(event.current_schedule(), changed_at=changed_at, reason=reason, status="DELAYED")
    precision = _enum(new_schedule.get("date_precision"), "date_precision", DATE_PRECISIONS)
    schedule = _validate_schedule_fields(new_schedule, precision)
    return replace(
        event,
        date_precision=precision,
        status="SCHEDULED",
        schedule_history=event.schedule_history + (old,),
        **schedule,
    )


def mark_occurred(event: EventRecord) -> EventRecord:
    if event.status not in {"SCHEDULED", "DISCOVERED", "UNKNOWN"}:
        raise CalendarValidationError(f"cannot mark {event.status} event as OCCURRED")
    return replace(event, status="OCCURRED")


def mark_handled(event: EventRecord) -> EventRecord:
    if event.status != "OCCURRED":
        raise CalendarValidationError("event must be OCCURRED before HANDLED")
    return replace(event, status="HANDLED")
