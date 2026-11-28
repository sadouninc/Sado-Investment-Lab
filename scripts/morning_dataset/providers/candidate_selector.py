from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
import math
import re
from pathlib import Path
from typing import Any

from .base import ProviderResult


@dataclass
class CandidateSelectorProvider:
    """Read the existing #108 Candidate Selector output for Morning Dataset.

    This provider is read-only. It does not rank, infer, or invent candidates;
    those responsibilities remain with the Candidate Selector pipeline.
    """

    path: Path = Path("data/generated/public/candidate-selector.json")
    limit: int = 10
    max_age_days: int = 3
    today: date | None = None
    name: str = "candidates"

    def collect(self) -> ProviderResult:
        if not self.path.is_file():
            return ProviderResult.unavailable(
                self.name,
                reason="canonical Candidate Selector snapshot not found",
                source_reference=str(self.path),
            )
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError, RecursionError) as exc:
            # ValueError covers json.JSONDecodeError and oversized integer
            # literals; none of these may stop Morning Dataset generation.
            return ProviderResult.unavailable(
                self.name,
                reason=f"failed to read Candidate Selector snapshot: {exc}",
                source_reference=str(self.path),
            )
        if not isinstance(raw, dict):
            return ProviderResult.unavailable(
                self.name,
                reason="Candidate Selector snapshot must be a JSON object",
                source_reference=str(self.path),
            )

        as_of = self._as_of(raw.get("as_of"))
        ranked = raw.get("ranked_candidates")
        if not isinstance(ranked, list):
            ranked = raw.get("candidates")
        if not isinstance(ranked, list):
            return ProviderResult.unavailable(
                self.name,
                reason="Candidate Selector snapshot has no candidate list",
                source_reference=str(self.path),
            )

        eligible: list[dict[str, Any]] = []
        anomalies: dict[str, int] = {}
        unresolved = 0
        scored_count = 0
        for row in ranked:
            if not isinstance(row, dict):
                _count(anomalies, "non-object candidate row")
                continue
            code = row.get("security_code")
            name = row.get("company_name")
            if not isinstance(code, str) or not code.strip() or not isinstance(name, str) or not name.strip():
                unresolved += 1
                continue
            priority = self._priority(row.get("total_priority"))
            if priority is _MALFORMED:
                _count(anomalies, "malformed total_priority")
                priority = None
            scored = priority is not None
            if scored:
                scored_count += 1
            sources = self._sources(row.get("candidate_sources"))
            if sources is None:
                _count(anomalies, "malformed candidate_sources")
                sources = []
            status = row.get("research_status")
            if status is not None and not isinstance(status, str):
                _count(anomalies, "malformed research_status")
                status = None
            selection_reason = self._optional_text(row.get("selection_reason"), anomalies, "selection_reason")
            last_researched_at = self._optional_text(row.get("last_researched_at"), anomalies, "last_researched_at")
            eligible.append(
                {
                    "security_code": code.strip(),
                    "company_name": name.strip(),
                    "rank": scored_count if scored else None,
                    "status": status or "UNKNOWN",
                    "total_priority": priority,
                    "owner_pick": bool(row.get("owner_pick")),
                    "candidate_sources": sources,
                    "selection_reason": selection_reason,
                    "last_researched_at": last_researched_at,
                }
            )
            if len(eligible) >= self.limit:
                break
        anomaly_note = _anomaly_note(anomalies)

        if not eligible:
            return ProviderResult.unavailable(
                self.name,
                status="MISSING",
                as_of=as_of,
                source_reference=str(self.path),
                reason="Candidate Selector has no security-code-resolved candidates for Morning" + anomaly_note,
            )
        if as_of is None:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                source_reference=str(self.path),
                reason="Candidate Selector candidates are usable but snapshot as_of is missing or invalid" + anomaly_note,
                data=eligible,
            )

        age_days = ((self.today or date.today()) - date.fromisoformat(as_of)).days
        if age_days < 0:
            # A snapshot dated after the run date cannot be proven current; keep
            # its declared as_of for audit but never report it as healthy.
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=as_of,
                source_reference=str(self.path),
                reason=(
                    f"Candidate Selector snapshot as_of {as_of} is {-age_days} days in the future "
                    "relative to the run date; freshness cannot be verified" + anomaly_note
                ),
                data=eligible,
            )
        if age_days > self.max_age_days:
            return ProviderResult.unavailable(
                self.name,
                status="STALE",
                as_of=as_of,
                source_reference=str(self.path),
                reason=f"Candidate Selector snapshot is {age_days} days old (freshness limit {self.max_age_days})" + anomaly_note,
                data=eligible,
            )

        # A freshly generated candidate file can still contain only unscored
        # historical research. Do not promote it as a verified ranked shortlist.
        if not any(item["rank"] is not None for item in eligible):
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=as_of,
                source_reference=str(self.path),
                reason="Candidate Selector snapshot has no scored priorities; candidate order is not a verified ranking" + anomaly_note,
                data=eligible,
            )

        if anomalies:
            # Malformed fields are not guessed or repaired upstream here. The
            # well-formed rows stay visible, but the feed is not reported OK.
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=as_of,
                source_reference=str(self.path),
                reason="Candidate Selector snapshot contains malformed candidate fields" + anomaly_note,
                data=eligible,
            )

        # Unresolved Candidate Selector records are deliberately excluded from the
        # Morning security shortlist rather than assigned guessed codes. Their
        # existence is not a freshness/completeness defect in the eligible feed.
        return ProviderResult.ok(
            self.name,
            eligible,
            as_of=as_of,
            source_reference=str(self.path),
        )

    @staticmethod
    def _as_of(value: object) -> str | None:
        """Return the snapshot date only when the whole value is a valid ISO date/datetime."""
        if not isinstance(value, str):
            return None
        text = value.strip()
        # Require the extended YYYY-MM-DD form; fromisoformat alone would also
        # accept compact forms such as "20261128" or week dates.
        if not _ISO_DATE_PREFIX.match(text) or (len(text) > 10 and text[10] not in "T "):
            return None
        try:
            if len(text) == 10:
                return date.fromisoformat(text).isoformat()
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        # Keep the producer's declared calendar date; do not shift time zones.
        return parsed.date().isoformat()

    @staticmethod
    def _priority(value: object) -> float | int | None | object:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return _MALFORMED
        try:
            finite = math.isfinite(value)
        except OverflowError:
            return _MALFORMED
        return value if finite else _MALFORMED

    @staticmethod
    def _sources(value: object) -> list[str] | None:
        if value is None:
            return []
        if not isinstance(value, list):
            return None
        if not all(isinstance(item, str) and item.strip() for item in value):
            return None
        return [item.strip() for item in value]

    @staticmethod
    def _optional_text(value: object, anomalies: dict[str, int], field: str) -> str | None:
        if value is None or isinstance(value, str):
            return value
        _count(anomalies, f"malformed {field}")
        return None


_MALFORMED = object()
_ISO_DATE_PREFIX = re.compile(r"\d{4}-\d{2}-\d{2}")


def _count(anomalies: dict[str, int], key: str) -> None:
    anomalies[key] = anomalies.get(key, 0) + 1


def _anomaly_note(anomalies: dict[str, int]) -> str:
    if not anomalies:
        return ""
    detail = ", ".join(f"{key}={count}" for key, count in sorted(anomalies.items()))
    return f"; malformed input ignored without guessing ({detail})"
