from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import math
from pathlib import Path
import re
import sqlite3
from typing import Any

from .base import ProviderResult


ISO_DATE_PREFIX_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
NUMERIC_FACTS = (
    "cash_buying_power",
    "margin_buying_power",
    "cash_ratio",
    "margin_exposure",
    "margin_ratio",
    "total_exposure",
    "reserve_amount",
)
METADATA_TEXT = ("source", "source_version")


@dataclass
class CapitalProvider:
    path: Path = Path("data/database/history.db")
    max_age_days: int = 3
    today: date | None = None
    name: str = "capital"

    def collect(self) -> ProviderResult:
        if not self.path.is_file():
            return ProviderResult.unavailable(
                self.name,
                reason="canonical capital history database not found",
                source_reference=str(self.path),
            )

        try:
            connection = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            try:
                table = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='capital_snapshots'"
                ).fetchone()
                if table is None:
                    return ProviderResult.unavailable(
                        self.name,
                        reason="capital_snapshots table not found in canonical history database",
                        source_reference=str(self.path),
                    )

                row = connection.execute(
                    """
                    SELECT snapshot_at,
                           cash_buying_power,
                           margin_buying_power,
                           cash_ratio,
                           margin_exposure,
                           margin_ratio,
                           total_exposure,
                           reserve_amount,
                           source,
                           source_version
                      FROM capital_snapshots
                  ORDER BY snapshot_at DESC, id DESC
                     LIMIT 1
                    """
                ).fetchone()
            finally:
                connection.close()
        except sqlite3.Error as exc:
            return ProviderResult.unavailable(
                self.name,
                reason=f"failed to read canonical capital database: {exc}",
                source_reference=str(self.path),
            )

        if row is None:
            return ProviderResult.unavailable(
                self.name,
                reason="canonical capital history contains no snapshots",
                source_reference=str(self.path),
            )

        as_of = self._as_of(row["snapshot_at"])
        # SQLite REAL affinity keeps unconvertible text, blobs and +/-inf as-is, so a
        # non-null column is not proof of a usable number. Invalid values become
        # null in the payload and are reported; a true zero is a valid fact.
        facts: dict[str, float | int | None] = {}
        invalid_facts: list[str] = []
        for column in NUMERIC_FACTS:
            value, valid = _finite_number(row[column])
            facts[column] = value
            if not valid:
                invalid_facts.append(column)

        # TEXT affinity still admits BLOBs. Metadata is copied only when it is
        # null or text; anything else is nulled and reported, never re-encoded.
        metadata: dict[str, str | None] = {}
        invalid_metadata: list[str] = []
        for column in METADATA_TEXT:
            value = row[column]
            if value is None or isinstance(value, str):
                metadata[column] = value
            else:
                metadata[column] = None
                invalid_metadata.append(column)

        payload = {
            # capital_snapshots stores buying power, not a brokerage cash balance.
            # Do not relabel buying power as cash available.
            "cash_available": None,
            "buying_power": {
                "cash": facts["cash_buying_power"],
                "margin": facts["margin_buying_power"],
            },
            "margin_usage": {
                "exposure": facts["margin_exposure"],
                "ratio": facts["margin_ratio"],
            },
            "target_reserve": facts["reserve_amount"],
            "capital_state": {
                "cash_ratio": facts["cash_ratio"],
                "total_exposure": facts["total_exposure"],
                "source": metadata["source"],
                "source_version": metadata["source_version"],
            },
        }
        invalid_parts = []
        if invalid_facts:
            invalid_parts.append(
                "invalid non-finite or non-numeric capital facts set to null: " + ", ".join(invalid_facts)
            )
        if invalid_metadata:
            invalid_parts.append("invalid non-text capital metadata set to null: " + ", ".join(invalid_metadata))
        invalid_detail = "; ".join(invalid_parts) or None

        def with_invalid(reason: str) -> str:
            return f"{reason}; {invalid_detail}" if invalid_detail else reason

        if all(value is None for value in facts.values()):
            return ProviderResult.unavailable(
                self.name,
                status="MISSING",
                as_of=as_of,
                source_reference=str(self.path),
                reason=with_invalid("latest capital snapshot contains no usable capital facts"),
            )

        if as_of is None:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                source_reference=str(self.path),
                reason=with_invalid("capital facts exist but snapshot_at cannot be interpreted as a strict ISO date or date-time"),
                data=payload,
            )

        age = (self.today or date.today()) - date.fromisoformat(as_of)
        if age.days < 0:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=as_of,
                source_reference=str(self.path),
                reason=with_invalid("capital snapshot date is in the future"),
                data=payload,
            )
        if age.days > self.max_age_days:
            return ProviderResult.unavailable(
                self.name,
                status="STALE",
                as_of=as_of,
                source_reference=str(self.path),
                reason=with_invalid(f"capital snapshot is {age.days} days old (freshness limit {self.max_age_days})"),
                data=payload,
            )

        # A fresh snapshot can still be partial when both forms of buying power are
        # unknown. Preserve the remaining facts without inventing brokerage values.
        if facts["cash_buying_power"] is None and facts["margin_buying_power"] is None:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=as_of,
                source_reference=str(self.path),
                reason=with_invalid("capital snapshot is fresh but buying-power values are unavailable"),
                data=payload,
            )

        if invalid_detail:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=as_of,
                source_reference=str(self.path),
                reason=f"capital snapshot is fresh but {invalid_detail}",
                data=payload,
            )

        return ProviderResult.ok(
            self.name,
            payload,
            as_of=as_of,
            source_reference=str(self.path),
        )

    @staticmethod
    def _as_of(value: object) -> str | None:
        """Return YYYY-MM-DD for a strict ISO date or ISO date-time string.

        Arbitrary suffixes ("2026-08-08garbage") and impossible dates are rejected
        instead of being truncated to the first 10 characters.
        """

        if not isinstance(value, str):
            return None
        text = value
        if text.strip() != text or not ISO_DATE_PREFIX_RE.fullmatch(text[:10]):
            return None
        if len(text) > 10 and text[10] not in "T ":
            return None
        try:
            if len(text) == 10:
                return date.fromisoformat(text).isoformat()
            return datetime.fromisoformat(text).date().isoformat()
        except ValueError:
            return None


def _finite_number(value: Any) -> tuple[float | int | None, bool]:
    """Return (value, valid). ``None`` is missing (valid); anything else must be a
    finite int/float. bool, text, blobs and +/-inf/NaN are invalid and become null."""

    if value is None:
        return None, True
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, False
    if isinstance(value, float) and not math.isfinite(value):
        return None, False
    return value, True
