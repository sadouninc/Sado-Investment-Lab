from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Iterable, Mapping

from scripts.catalyst_calendar import CalendarValidationError, EventRecord, mark_occurred


@dataclass(frozen=True)
class EventReviewCandidate:
    event_ref: str
    security_code: str
    reason: str
    expected_review: tuple[str, ...]
    related_refs: tuple[str, ...]
    event_status: str = "OCCURRED"


def _parse_as_of(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise CalendarValidationError("as_of must be ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        raise CalendarValidationError("as_of must include timezone information")
    return parsed


def build_company_event(raw: Mapping[str, Any]) -> EventRecord:
    """Adapt an explicit company earnings/catalyst payload into #151 EventRecord.

    The adapter deliberately does not infer dates, source authority, event identity,
    or review semantics. Callers must provide those fields explicitly from their
    owning SSoT (#113 Company Research, #43 Earnings Event, or another reviewed
    company-event source).
    """

    allowed = {
        "security_code",
        "event_key",
        "event_type",
        "title",
        "date_precision",
        "scheduled_at",
        "scheduled_date",
        "scheduled_month",
        "window_start",
        "window_end",
        "source_ref",
        "authority",
        "status",
        "expected_review",
        "related_refs",
    }
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise CalendarValidationError(
            "company event contains unsupported fields: " + ", ".join(unknown)
        )

    security_code = str(raw.get("security_code") or "").strip()
    if not security_code:
        raise CalendarValidationError("security_code is required")

    payload = {
        "event_key": raw.get("event_key"),
        "event_type": raw.get("event_type"),
        "entity_type": "COMPANY",
        "entity_id": security_code,
        "title": raw.get("title"),
        "date_precision": raw.get("date_precision"),
        "source_ref": raw.get("source_ref"),
        "authority": raw.get("authority"),
        "status": raw.get("status", "SCHEDULED"),
        "expected_review": raw.get("expected_review", []),
        "related_refs": raw.get("related_refs", []),
    }
    for key in (
        "scheduled_at",
        "scheduled_date",
        "scheduled_month",
        "window_start",
        "window_end",
    ):
        if key in raw:
            payload[key] = raw[key]
    return EventRecord.from_mapping(payload)


def merge_same_event(events: Iterable[EventRecord]) -> EventRecord:
    """Merge multiple explicit consumers onto one canonical event identity.

    #43 and #113 may independently refer to the same earnings event. The event is
    not duplicated when identity and schedule agree; related refs and expected
    reviews are unioned. Conflicting canonical fields fail closed.
    """

    items = list(events)
    if not items:
        raise CalendarValidationError("at least one event is required")
    first = items[0]
    reviews = set(first.expected_review)
    refs = set(first.related_refs)
    for item in items[1:]:
        comparable = (
            item.event_id,
            item.event_type,
            item.entity_type,
            item.entity_id,
            item.date_precision,
            item.scheduled_at,
            item.scheduled_date,
            item.scheduled_month,
            item.window_start,
            item.window_end,
            item.status,
        )
        baseline = (
            first.event_id,
            first.event_type,
            first.entity_type,
            first.entity_id,
            first.date_precision,
            first.scheduled_at,
            first.scheduled_date,
            first.scheduled_month,
            first.window_start,
            first.window_end,
            first.status,
        )
        if comparable != baseline:
            raise CalendarValidationError("same event identity has conflicting canonical fields")
        reviews.update(item.expected_review)
        refs.update(item.related_refs)
    return replace(
        first,
        expected_review=tuple(sorted(reviews)),
        related_refs=tuple(sorted(refs)),
    )


def event_has_certainly_passed(event: EventRecord, *, as_of: str) -> bool:
    """Return True only when schedule precision proves that an event has passed."""

    now = _parse_as_of(as_of)
    if event.date_precision == "DATETIME":
        assert event.scheduled_at is not None
        scheduled = _parse_as_of(event.scheduled_at)
        return now >= scheduled
    if event.date_precision == "DATE":
        assert event.scheduled_date is not None
        return now.date().isoformat() > event.scheduled_date
    if event.date_precision == "MONTH":
        assert event.scheduled_month is not None
        return now.strftime("%Y-%m") > event.scheduled_month
    if event.date_precision == "WINDOW":
        assert event.window_end is not None
        return now.date().isoformat() > event.window_end
    if event.date_precision == "UNKNOWN":
        return False
    raise CalendarValidationError(f"unsupported date precision: {event.date_precision}")


def project_event_passage(event: EventRecord, *, as_of: str) -> EventRecord:
    """Project SCHEDULED to OCCURRED only when passage is provable.

    This function never marks an event HANDLED; downstream review remains a
    separate workflow as required by #151.
    """

    _parse_as_of(as_of)
    if event.status != "SCHEDULED":
        return event
    if not event_has_certainly_passed(event, as_of=as_of):
        return event
    return mark_occurred(event)


def build_review_candidate(event: EventRecord) -> EventReviewCandidate:
    if event.entity_type != "COMPANY":
        raise CalendarValidationError("company review candidate requires COMPANY event")
    if event.status != "OCCURRED":
        raise CalendarValidationError("event must be OCCURRED before creating review candidate")
    if not event.expected_review:
        raise CalendarValidationError("event has no expected_review")
    return EventReviewCandidate(
        event_ref=event.event_id,
        security_code=event.entity_id,
        reason=f"{event.event_type}_EVENT_OCCURRED",
        expected_review=tuple(sorted(event.expected_review)),
        related_refs=tuple(sorted(event.related_refs)),
    )


def project_company_event(raw: Mapping[str, Any], *, as_of: str) -> tuple[EventRecord, EventReviewCandidate | None]:
    event = project_event_passage(build_company_event(raw), as_of=as_of)
    candidate = build_review_candidate(event) if event.status == "OCCURRED" and event.expected_review else None
    return event, candidate
