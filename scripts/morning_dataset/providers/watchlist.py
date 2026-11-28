from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import re

from .base import ProviderResult

SECTION_AS_OF_RE = re.compile(r"^>\s*as_of:\s*(20\d{2}-\d{2}-\d{2})\s*$", re.IGNORECASE)
SECTION_AS_OF_PREFIX_RE = re.compile(r"^>\s*as_of:\s*(.*?)\s*$", re.IGNORECASE)
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
BULLET_RE = re.compile(r"^[-*]\s+(.+?)\s*$")


@dataclass
class WatchlistProvider:
    path: Path = Path("Current_Status.md")
    max_age_days: int = 3
    today: date | None = None
    name: str = "watchlist"

    def collect(self) -> ProviderResult:
        try:
            exists = self.path.is_file()
        except OSError:
            exists = False
        if not exists:
            return ProviderResult.unavailable(self.name, reason="canonical watchlist source not found", source_reference=str(self.path))
        try:
            text = self.path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return ProviderResult.unavailable(
                self.name,
                status="MISSING",
                source_reference=str(self.path),
                reason="canonical watchlist source could not be read as UTF-8",
            )
        lines = self._section_lines(text, "current focus")
        as_of_lines = [m.group(1) for line in lines if (m := SECTION_AS_OF_PREFIX_RE.match(line))]
        section_date = as_of_lines[0] if len(as_of_lines) == 1 else None
        date_reason = None
        if len(as_of_lines) > 1:
            date_reason = "Current Focus section has duplicate or conflicting as_of dates"
        elif len(as_of_lines) == 1 and not SECTION_AS_OF_RE.match(f"> as_of: {section_date}"):
            date_reason = "Current Focus section has an invalid as_of date"
        elif section_date is not None:
            try:
                datetime.strptime(section_date, "%Y-%m-%d")
            except ValueError:
                date_reason = "Current Focus section has an invalid as_of calendar date"
                section_date = None
        as_of = section_date
        if not lines:
            return ProviderResult.unavailable(self.name, status="MISSING", as_of=as_of, source_reference=str(self.path), reason="Current Focus section contains no active watch items")

        items = []
        malformed = 0
        for line in lines:
            if not line.strip() or line.startswith(">"):
                continue
            match = BULLET_RE.match(line)
            if not match:
                malformed += 1
                continue
            value = match.group(1).strip()
            if value:
                items.append({"text": value, "security_code": None, "name": None, "theme": None, "reason": value, "priority": None})
        if not items:
            return ProviderResult.unavailable(self.name, status="MISSING", as_of=as_of, source_reference=str(self.path), reason="Current Focus section could not be parsed into watch items")
        payload = {"items": items}
        if date_reason is not None:
            return ProviderResult.unavailable(self.name, status="PARTIAL", source_reference=str(self.path), reason=date_reason, data=payload)
        if as_of is None:
            return ProviderResult.unavailable(self.name, status="PARTIAL", source_reference=str(self.path), reason="watchlist parsed but section has no freshness date", data=payload)
        age = (self.today or date.today()) - datetime.strptime(as_of, "%Y-%m-%d").date()
        if age.days < 0:
            return ProviderResult.unavailable(self.name, status="PARTIAL", as_of=as_of, source_reference=str(self.path), reason="watchlist as_of date is in the future", data=payload)
        if malformed:
            return ProviderResult.unavailable(self.name, status="PARTIAL", as_of=as_of, source_reference=str(self.path), reason=f"{malformed} Current Focus line(s) were not parseable", data=payload)
        if age.days > self.max_age_days:
            return ProviderResult.unavailable(self.name, status="STALE", as_of=as_of, source_reference=str(self.path), reason=f"watchlist snapshot is {age.days} days old (freshness limit {self.max_age_days})", data=payload)
        return ProviderResult.ok(self.name, payload, as_of=as_of, source_reference=str(self.path))

    @staticmethod
    def _section_lines(text: str, target: str) -> list[str]:
        in_section = False
        found = False
        result = []
        for line in text.splitlines():
            heading = HEADING_RE.match(line)
            if heading:
                if in_section:
                    break
                in_section = heading.group(1).strip().lower() == target
                found = found or in_section
                continue
            if in_section:
                result.append(line)
        return result if found else []

