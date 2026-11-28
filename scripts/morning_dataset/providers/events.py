from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
import re
from typing import Any

from .base import ProviderResult


EVENT_KEYS = ("earnings", "economic", "policy", "market_calendar", "company")
WHEN_KEYS = ("date", "scheduled_at", "timestamp")
ISO_DATE_PREFIX_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

# Event calendars never need integer literals longer than this. Rejecting longer
# literals explicitly makes the result identical on every runtime instead of
# depending on the interpreter's int-string conversion limit.
_MAX_INT_DIGITS = 64


@dataclass
class EventsProvider:
    """Load the canonical repository event calendar without inventing events.

    The provider deliberately does not scrape or infer events. Upstream collectors or
    human-reviewed repository updates own event discovery; this provider normalizes
    the canonical calendar into the Morning Dataset and makes freshness explicit.
    """

    path: Path = Path("data/events/calendar.json")
    max_age_days: int = 1
    today: date | None = None
    name: str = "events"

    def collect(self) -> ProviderResult:
        if not self.path.is_file():
            return ProviderResult.unavailable(
                self.name,
                reason="canonical repository event calendar not found",
                source_reference=str(self.path),
            )

        try:
            raw = json.loads(
                self.path.read_text(encoding="utf-8"),
                parse_int=_bounded_int,
                parse_constant=_reject_constant,
            )
        except (OSError, UnicodeDecodeError, ValueError, RecursionError) as exc:
            # json.JSONDecodeError is a ValueError subclass; ValueError also covers
            # oversized integer literals and non-standard NaN/Infinity constants.
            return ProviderResult.unavailable(
                self.name,
                reason=f"failed to read canonical event calendar: {exc}",
                source_reference=str(self.path),
            )

        if not isinstance(raw, dict):
            return ProviderResult.unavailable(
                self.name,
                reason="canonical event calendar must be a JSON object",
                source_reference=str(self.path),
            )

        if "events" in raw and not isinstance(raw.get("events"), dict):
            # An explicit but wrongly-typed container must not silently fall back to
            # reading categories from the top level of the document.
            return ProviderResult.unavailable(
                self.name,
                reason="canonical event calendar 'events' must be a JSON object",
                source_reference=str(self.path),
            )

        as_of, as_of_problem = self._resolve_as_of(raw)
        payload, missing_categories, invalid_items = self._normalize(raw)
        event_count = sum(len(payload[key]) for key in EVENT_KEYS)
        coverage_complete = self._coverage_complete(raw)

        coverage = raw.get("coverage") if isinstance(raw.get("coverage"), dict) else {}
        source = raw.get("source")
        payload["coverage"] = coverage
        if source is not None:
            payload["source"] = source

        if event_count == 0:
            empty_problems = self._verified_empty_problems(
                raw, missing_categories, invalid_items, coverage_complete
            )
            if as_of is None:
                empty_problems.append(as_of_problem or "calendar as_of is missing or invalid")
            if empty_problems:
                return ProviderResult.unavailable(
                    self.name,
                    status="MISSING",
                    as_of=as_of,
                    source_reference=str(self.path),
                    reason=(
                        "event calendar contains no valid events and is not a verified empty day: "
                        + "; ".join(empty_problems)
                    ),
                )

        if as_of is None:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                source_reference=str(self.path),
                reason=f"event data is usable but {as_of_problem or 'calendar as_of is missing or invalid'}",
                data=payload,
            )

        age_days = ((self.today or date.today()) - date.fromisoformat(as_of)).days
        if age_days < 0:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=as_of,
                source_reference=str(self.path),
                reason="event calendar as_of date is in the future",
                data=payload,
            )
        if age_days > self.max_age_days:
            return ProviderResult.unavailable(
                self.name,
                status="STALE",
                as_of=as_of,
                source_reference=str(self.path),
                reason=f"event calendar is {age_days} days old (freshness limit {self.max_age_days})",
                data=payload,
            )

        if missing_categories or invalid_items or not coverage_complete:
            details = []
            if missing_categories:
                details.append("missing categories: " + ", ".join(missing_categories))
            if invalid_items:
                details.append(f"ignored {invalid_items} malformed event item(s)")
            if not coverage_complete:
                details.append("coverage is not explicitly complete")
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=as_of,
                source_reference=str(self.path),
                reason="; ".join(details),
                data=payload,
            )

        return ProviderResult.ok(
            self.name,
            payload,
            as_of=as_of,
            source_reference=str(self.path),
        )

    @staticmethod
    def _normalize(raw: dict[str, Any]) -> tuple[dict[str, Any], list[str], int]:
        # Legacy flat calendars (categories at the top level) remain readable; an
        # explicit non-object "events" container is rejected before this point.
        container = raw["events"] if isinstance(raw.get("events"), dict) else raw
        payload: dict[str, Any] = {}
        missing: list[str] = []
        invalid = 0
        for key in EVENT_KEYS:
            value = container.get(key)
            if value is None:
                missing.append(key)
                payload[key] = []
                continue
            if not isinstance(value, list):
                missing.append(key)
                payload[key] = []
                invalid += 1
                continue
            normalized: list[dict[str, Any]] = []
            for item in value:
                if not _is_valid_event(item):
                    invalid += 1
                    continue
                normalized.append(dict(item))
            payload[key] = normalized
        return payload, missing, invalid

    @staticmethod
    def _coverage_complete(raw: dict[str, Any]) -> bool:
        coverage = raw.get("coverage")
        if not isinstance(coverage, dict):
            return False
        return all(coverage.get(key) is True for key in EVENT_KEYS)

    @staticmethod
    def _verified_empty_problems(
        raw: dict[str, Any],
        missing_categories: list[str],
        invalid_items: int,
        coverage_complete: bool,
    ) -> list[str]:
        """Reasons why a calendar with zero valid events is not a verified empty day.

        A verified empty day needs all five categories as explicit empty arrays,
        complete coverage, ``empty_confirmed: true`` and no malformed content.
        """

        problems: list[str] = []
        if raw.get("empty_confirmed") is not True:
            problems.append("empty_confirmed is not true")
        if not coverage_complete:
            problems.append("coverage is not explicitly complete")
        if missing_categories:
            problems.append("missing categories: " + ", ".join(missing_categories))
        if invalid_items:
            problems.append(f"ignored {invalid_items} malformed event item(s)")
        return problems

    @staticmethod
    def _resolve_as_of(raw: dict[str, Any]) -> tuple[str | None, str | None]:
        """Return the calendar date and, when it is unusable, why.

        An explicit ``as_of`` is authoritative: when it is present but invalid, the
        generation timestamp must not rescue it. ``generated_at`` is only used when
        ``as_of`` is absent.
        """

        if raw.get("as_of") is not None:
            parsed = _parse_iso_date(raw["as_of"])
            if parsed is None:
                return None, "explicit calendar as_of is invalid"
            return parsed, None
        if raw.get("generated_at") is not None:
            parsed = _parse_iso_date(raw["generated_at"])
            if parsed is None:
                return None, "calendar as_of is missing and generated_at is invalid"
            return parsed, None
        return None, "calendar as_of is missing"


def _parse_iso_date(value: object) -> str | None:
    """Return YYYY-MM-DD for a strict ISO date or ISO date-time string.

    Accepts ``YYYY-MM-DD`` or a full ISO 8601 date-time whose 11th character is
    ``T`` or a space. Arbitrary suffixes ("2026-08-08garbage") and impossible
    dates are rejected instead of being truncated to the first 10 characters.
    """

    if not isinstance(value, str):
        return None
    text = value.strip()
    if text != value or not ISO_DATE_PREFIX_RE.match(text):
        return None
    if len(text) > 10 and text[10] not in "T ":
        return None
    try:
        if len(text) == 10:
            return date.fromisoformat(text).isoformat()
        return datetime.fromisoformat(text).date().isoformat()
    except ValueError:
        return None


def _is_valid_event(item: object) -> bool:
    # A title/name and a valid date/timestamp are the minimum facts needed to
    # distinguish a real scheduled event from unsupported prose.
    if not isinstance(item, dict):
        return False
    title = item.get("title") or item.get("name")
    if not isinstance(title, str) or not title.strip():
        return False
    when_values = [item[key] for key in WHEN_KEYS if item.get(key) is not None]
    if not when_values:
        return False
    # Every supplied date field must be valid; a malformed "date" is not rescued
    # by a different field.
    return all(_parse_iso_date(value) is not None for value in when_values)


def _bounded_int(text: str) -> int:
    if len(text.lstrip("+-")) > _MAX_INT_DIGITS:
        raise ValueError(f"integer literal longer than {_MAX_INT_DIGITS} digits")
    return int(text)


def _reject_constant(name: str) -> Any:
    raise ValueError(f"non-standard JSON constant {name} is not allowed")
