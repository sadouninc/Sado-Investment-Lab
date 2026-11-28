from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import json
import re

from .base import ProviderResult

LAST_UPDATED_RE = re.compile(r"最終更新:\s*(20\d{2}-\d{2}-\d{2})")
SECTION_AS_OF_RE = re.compile(r"^>\s*as_of\s*:\s*(?P<value>.*?)\s*$", re.IGNORECASE)
ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
BULLET_RE = re.compile(r"^[-*]\s+(.+?)\s*$")
DETAIL_RE = re.compile(r"^(?P<name>.+?)（(?P<details>.+)）$")


@dataclass
class PortfolioProvider:
    path: Path = Path("Current_Status.md")
    max_age_days: int = 3
    today: date | None = None
    name: str = "portfolio"

    def collect(self) -> ProviderResult:
        if not self.path.is_file():
            return ProviderResult.unavailable(self.name, reason="canonical portfolio source not found", source_reference=str(self.path))

        if self.path.suffix.lower() == ".json":
            return self._collect_canonical_json()

        try:
            text = self.path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return ProviderResult.unavailable(
                self.name, status="MISSING", source_reference=str(self.path),
                reason=f"failed to read portfolio source: {exc}",
            )
        lines = self._portfolio_lines(text)
        # Only an explicit date inside the Portfolio section can establish
        # portfolio freshness. The file-wide "最終更新" may describe edits to
        # other sections, so it is never used as a fallback.
        declared = [m.group("value") for line in lines if (m := SECTION_AS_OF_RE.match(line))]
        as_of: str | None = None
        date_problem: str | None = None
        if not declared:
            date_problem = "Portfolio section has no explicit as_of date"
            if LAST_UPDATED_RE.search(text):
                date_problem += " (file-wide 最終更新 is not used as portfolio freshness)"
        elif len(declared) > 1:
            date_problem = f"Portfolio section declares {len(declared)} as_of dates; freshness is ambiguous"
        else:
            as_of = _iso_date(declared[0])
            if as_of is None:
                date_problem = f"Portfolio section as_of is not a valid YYYY-MM-DD date: {declared[0][:40]!r}"
        if not lines:
            return ProviderResult.unavailable(self.name, status="MISSING", as_of=as_of, source_reference=str(self.path), reason="Portfolio section contains no holding lines; this is not evidence of zero holdings")

        positions = []
        malformed = 0
        for line in lines:
            if not line.strip() or line.startswith(">"):
                continue
            bullet = BULLET_RE.match(line)
            if not bullet:
                malformed += 1
                continue
            raw = bullet.group(1).strip()
            detail = DETAIL_RE.match(raw)
            positions.append({"name": detail.group("name").strip(), "details": detail.group("details").strip()} if detail else {"name": raw, "details": None})

        if not positions:
            return ProviderResult.unavailable(self.name, status="MISSING", as_of=as_of, source_reference=str(self.path), reason="Portfolio section could not be parsed into holdings; this is not evidence of zero holdings")
        payload = {"positions": positions, "exposure": None, "pnl": None}
        if date_problem is not None or as_of is None:
            return ProviderResult.unavailable(self.name, status="PARTIAL", source_reference=str(self.path), reason=f"portfolio holdings parsed but freshness is unverified: {date_problem}", data=payload)
        age = (self.today or date.today()) - date.fromisoformat(as_of)
        if age.days < 0:
            return ProviderResult.unavailable(self.name, status="PARTIAL", as_of=as_of, source_reference=str(self.path), reason="portfolio as_of date is in the future", data=payload)
        if malformed:
            return ProviderResult.unavailable(self.name, status="PARTIAL", as_of=as_of, source_reference=str(self.path), reason=f"{malformed} Portfolio line(s) were not parseable", data=payload)
        if age.days > self.max_age_days:
            return ProviderResult.unavailable(self.name, status="STALE", as_of=as_of, source_reference=str(self.path), reason=f"portfolio snapshot is {age.days} days old (freshness limit {self.max_age_days})", data=payload)
        return ProviderResult.ok(self.name, payload, as_of=as_of, source_reference=str(self.path))

    def _collect_canonical_json(self) -> ProviderResult:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"), parse_int=_bounded_int)
        except (OSError, UnicodeDecodeError, ValueError, RecursionError) as exc:
            # ValueError covers json.JSONDecodeError and oversized integer literals.
            return ProviderResult.unavailable(
                self.name,
                status="MISSING",
                source_reference=str(self.path),
                reason=f"canonical portfolio JSON is invalid: {exc}",
            )
        if not isinstance(payload, dict):
            return ProviderResult.unavailable(
                self.name, status="MISSING", source_reference=str(self.path),
                reason="canonical portfolio JSON must be an object",
            )
        raw_positions = payload.get("positions")
        raw_as_of = payload.get("verification_as_of") or payload.get("as_of")
        # Report a declared as_of only when it is text; other types are not
        # silently converted into a freshness date.
        as_of = raw_as_of if isinstance(raw_as_of, str) else None
        status = payload.get("verification_status")
        if not isinstance(raw_positions, list) or not raw_positions:
            return ProviderResult.unavailable(
                self.name, status="MISSING", as_of=as_of, source_reference=str(self.path),
                reason="Canonical Portfolio State has no position list; this is not evidence of zero holdings",
            )
        positions = [row for row in raw_positions if isinstance(row, dict)]
        problems: list[str] = []
        if len(positions) != len(raw_positions):
            problems.append(f"{len(raw_positions) - len(positions)} position entr(y/ies) are not objects")
        diff = payload.get("verification_diff")
        if diff is None:
            diff = []
        elif not isinstance(diff, list):
            problems.append("verification_diff is not a list")
            diff = []
        data = {
            "positions": positions,
            "exposure": None,
            "pnl": None,
            "verification_status": status if isinstance(status, str) else None,
            "base_snapshot": payload.get("base_snapshot"),
            "verification_diff": diff,
        }
        if not positions:
            return ProviderResult.unavailable(
                self.name, status="MISSING", as_of=as_of, source_reference=str(self.path),
                reason="Canonical Portfolio State has no well-formed positions; this is not evidence of zero holdings",
            )
        if not isinstance(status, str):
            return ProviderResult.unavailable(
                self.name, status="PARTIAL", as_of=as_of, source_reference=str(self.path),
                reason=f"portfolio verification status is not text: {type(status).__name__}", data=data,
            )
        if status == "MISMATCH":
            return ProviderResult.unavailable(
                self.name, status="PARTIAL", as_of=as_of, source_reference=str(self.path),
                reason="Canonical Portfolio State does not match the latest verification",
                data=data,
            )
        if status not in {"VERIFIED", "PROVISIONAL"}:
            return ProviderResult.unavailable(
                self.name, status="PARTIAL", as_of=as_of, source_reference=str(self.path),
                reason=f"unknown portfolio verification status: {status!r}", data=data,
            )
        if as_of is None:
            return ProviderResult.unavailable(
                self.name, status="PARTIAL", source_reference=str(self.path),
                reason="canonical portfolio has no as_of date", data=data,
            )
        parsed = _iso_date(as_of)
        if parsed is None:
            return ProviderResult.unavailable(
                self.name, status="PARTIAL", as_of=as_of, source_reference=str(self.path),
                reason="canonical portfolio as_of is not YYYY-MM-DD", data=data,
            )
        age = (self.today or date.today()) - date.fromisoformat(parsed)
        if age.days < 0:
            return ProviderResult.unavailable(
                self.name, status="PARTIAL", as_of=as_of, source_reference=str(self.path),
                reason="canonical portfolio as_of date is in the future", data=data,
            )
        if problems:
            return ProviderResult.unavailable(
                self.name, status="PARTIAL", as_of=as_of, source_reference=str(self.path),
                reason="canonical portfolio JSON has malformed fields: " + "; ".join(problems), data=data,
            )
        if age.days > self.max_age_days:
            return ProviderResult.unavailable(
                self.name, status="STALE", as_of=as_of, source_reference=str(self.path),
                reason=f"portfolio snapshot is {age.days} days old (freshness limit {self.max_age_days})", data=data,
            )
        return ProviderResult.ok(self.name, data, as_of=as_of, source_reference=str(self.path))

    @staticmethod
    def _portfolio_lines(text: str) -> list[str]:
        in_portfolio = False
        found = False
        result = []
        for line in text.splitlines():
            heading = HEADING_RE.match(line)
            if heading:
                if in_portfolio:
                    break
                in_portfolio = heading.group(1).strip().lower() == "portfolio"
                found = found or in_portfolio
                continue
            if in_portfolio:
                result.append(line)
        return result if found else []


def _iso_date(value: str) -> str | None:
    """Return YYYY-MM-DD when ``value`` is a full ISO date or ISO datetime."""
    text = value.strip()
    if not ISO_DATE_RE.match(text) or (len(text) > 10 and text[10] not in "T "):
        return None
    try:
        if len(text) == 10:
            return date.fromisoformat(text).isoformat()
        return datetime.fromisoformat(text).date().isoformat()
    except ValueError:
        return None


# Portfolio quantities and prices never need more digits than this. Rejecting
# longer literals explicitly makes the result identical on every runtime,
# instead of depending on the interpreter's int-string conversion limit.
_MAX_INT_DIGITS = 64


def _bounded_int(text: str) -> int:
    if len(text.lstrip("+-")) > _MAX_INT_DIGITS:
        raise ValueError(f"integer literal longer than {_MAX_INT_DIGITS} digits")
    return int(text)
