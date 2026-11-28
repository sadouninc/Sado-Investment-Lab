from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import math
from pathlib import Path
import re
import sqlite3
from typing import Any

from .base import ProviderResult

ISO_DATE_PREFIX_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

# SQLite column affinity is not a type guarantee: REAL/INTEGER columns keep
# unconvertible text, blobs and +/-inf, and TEXT columns keep blobs. Every value
# copied into the payload is therefore checked against its expected kind.
CANDIDATE_TEXT = ("security_code", "horizon", "universe_state", "status", "model_name", "model_version")
CANDIDATE_NUMERIC = (
    "long_score",
    "today_score",
    "risk_score",
    "personal_fit",
    "capital_feasibility",
    "rotation_score",
    "confidence",
)
FACTOR_TEXT = ("factor_type", "factor_key", "value_text", "polarity", "source_reference")
FACTOR_NUMERIC = ("value_numeric", "contribution")


class _UndecodableText:
    """Marker for a TEXT value that is not valid UTF-8.

    The default text factory raises UnicodeDecodeError, which is not a
    sqlite3.Error and would abort the whole Morning generation. The marker lets
    the affected column be nulled and reported while other rows are kept.
    """

    __slots__ = ()


_UNDECODABLE = _UndecodableText()


def _decode_text(raw: bytes) -> str | _UndecodableText:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return _UNDECODABLE


@dataclass
class CandidatesProvider:
    path: Path = Path("data/database/history.db")
    limit: int = 10
    max_age_days: int = 3
    today: date | None = None
    name: str = "candidates"

    def collect(self) -> ProviderResult:
        if not self.path.is_file():
            return ProviderResult.unavailable(
                self.name,
                reason="canonical candidate history database not found",
                source_reference=str(self.path),
            )
        invalid: list[str] = []
        try:
            conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            conn.text_factory = _decode_text
            try:
                if not self._table_exists(conn, "candidates"):
                    return ProviderResult.unavailable(
                        self.name,
                        reason="candidates table not found in canonical history database",
                        source_reference=str(self.path),
                    )
                latest = conn.execute("SELECT MAX(generated_at) AS generated_at FROM candidates").fetchone()
                generated_at = latest["generated_at"] if latest else None
                if generated_at is None or generated_at == "":
                    return ProviderResult.unavailable(
                        self.name,
                        reason="canonical candidate history contains no candidate snapshots",
                        source_reference=str(self.path),
                    )
                if not isinstance(generated_at, str):
                    # A blob or undecodable value sorts above every text value in
                    # SQLite, so it would hide the real latest snapshot. Fail closed.
                    return ProviderResult.unavailable(
                        self.name,
                        reason="latest candidate snapshot key generated_at is not valid text",
                        source_reference=str(self.path),
                    )
                rows = conn.execute(
                    """
                    SELECT id, generated_at, security_code, horizon, universe_state,
                           long_score, today_score, risk_score, personal_fit,
                           capital_feasibility, rotation_score, rank, status,
                           confidence, model_name, model_version
                      FROM candidates
                     WHERE generated_at = ?
                  ORDER BY CASE WHEN rank IS NULL THEN 1 ELSE 0 END, rank ASC, today_score DESC, id ASC
                     LIMIT ?
                    """,
                    (generated_at, self.limit),
                ).fetchall()
                has_factors = self._table_exists(conn, "candidate_factors")
                payload = [
                    self._serialize_candidate(conn, row, has_factors, position, invalid)
                    for position, row in enumerate(rows, start=1)
                ]
            finally:
                conn.close()
        except sqlite3.Error as exc:
            return ProviderResult.unavailable(
                self.name,
                reason=f"failed to read canonical candidate database: {exc}",
                source_reference=str(self.path),
            )

        if not payload:
            return ProviderResult.unavailable(
                self.name,
                reason="latest candidate snapshot contains no candidates",
                source_reference=str(self.path),
            )

        invalid_detail = (
            "invalid candidate values set to null: " + ", ".join(invalid) if invalid else None
        )

        def with_invalid(reason: str) -> str:
            return f"{reason}; {invalid_detail}" if invalid_detail else reason

        as_of = self._as_of(generated_at)
        if as_of is None:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                source_reference=str(self.path),
                reason=with_invalid(
                    "candidate rows exist but generated_at cannot be interpreted as a strict ISO date or date-time"
                ),
                data=payload,
            )

        age = (self.today or date.today()) - date.fromisoformat(as_of)
        if age.days < 0:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=as_of,
                source_reference=str(self.path),
                reason=with_invalid("candidate snapshot date is in the future"),
                data=payload,
            )
        if age.days > self.max_age_days:
            return ProviderResult.unavailable(
                self.name,
                status="STALE",
                as_of=as_of,
                source_reference=str(self.path),
                reason=with_invalid(
                    f"candidate snapshot is {age.days} days old (freshness limit {self.max_age_days})"
                ),
                data=payload,
            )

        incomplete = any(not row.get("security_code") or not row.get("status") for row in payload)
        if incomplete:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=as_of,
                source_reference=str(self.path),
                reason=with_invalid(
                    "candidate snapshot is fresh but one or more rows lack required identity/status fields"
                ),
                data=payload,
            )

        if invalid_detail:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=as_of,
                source_reference=str(self.path),
                reason=f"candidate snapshot is fresh but {invalid_detail}",
                data=payload,
            )

        return ProviderResult.ok(
            self.name,
            payload,
            as_of=as_of,
            source_reference=str(self.path),
        )

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone() is not None

    @staticmethod
    def _serialize_candidate(
        conn: sqlite3.Connection,
        row: sqlite3.Row,
        has_factors: bool,
        position: int,
        invalid: list[str],
    ) -> dict:
        # Diagnostics name the row position and column only, never the raw value.
        label = f"candidate[{position}]"
        reasons: list[dict] = []
        if has_factors:
            factors = conn.execute(
                """
                SELECT factor_type, factor_key, value_numeric, value_text,
                       contribution, polarity, source_reference
                  FROM candidate_factors
                 WHERE candidate_id = ?
              ORDER BY id ASC
                """,
                (row["id"],),
            ).fetchall()
            for index, factor in enumerate(factors, start=1):
                factor_label = f"{label}.reasons[{index}]"
                reason: dict[str, Any] = {}
                for column in ("factor_type", "factor_key"):
                    reason[column] = _text(factor[column], f"{factor_label}.{column}", invalid)
                reason["value_numeric"] = _finite(factor["value_numeric"], f"{factor_label}.value_numeric", invalid)
                reason["value_text"] = _text(factor["value_text"], f"{factor_label}.value_text", invalid)
                reason["contribution"] = _finite(factor["contribution"], f"{factor_label}.contribution", invalid)
                for column in ("polarity", "source_reference"):
                    reason[column] = _text(factor[column], f"{factor_label}.{column}", invalid)
                reasons.append(reason)

        text = {column: _text(row[column], f"{label}.{column}", invalid) for column in CANDIDATE_TEXT}
        numeric = {column: _finite(row[column], f"{label}.{column}", invalid) for column in CANDIDATE_NUMERIC}
        return {
            "security_code": text["security_code"],
            "rank": _rank(row["rank"], f"{label}.rank", invalid),
            "horizon": text["horizon"],
            "universe_state": text["universe_state"],
            "long_score": numeric["long_score"],
            "today_score": numeric["today_score"],
            "risk_score": numeric["risk_score"],
            "personal_fit": numeric["personal_fit"],
            "capital_feasibility": numeric["capital_feasibility"],
            "rotation_score": numeric["rotation_score"],
            "status": text["status"],
            "confidence": numeric["confidence"],
            "model_name": text["model_name"],
            "model_version": text["model_version"],
            "reasons": reasons,
        }

    @staticmethod
    def _as_of(value: object) -> str | None:
        """Return YYYY-MM-DD for a strict ISO date or ISO date-time string.

        Arbitrary suffixes ("2026-08-08garbage"), surrounding whitespace and
        impossible dates are rejected instead of being truncated to 10 characters.
        """

        if not isinstance(value, str):
            return None
        if value.strip() != value or not ISO_DATE_PREFIX_RE.fullmatch(value[:10]):
            return None
        if len(value) > 10 and value[10] not in "T ":
            return None
        try:
            if len(value) == 10:
                return date.fromisoformat(value).isoformat()
            return datetime.fromisoformat(value).date().isoformat()
        except ValueError:
            return None


def _text(value: Any, label: str, invalid: list[str]) -> str | None:
    """``None`` is a missing fact; anything other than decodable text is invalid."""

    if value is None or isinstance(value, str):
        return value
    invalid.append(label)
    return None


def _finite(value: Any, label: str, invalid: list[str]) -> float | int | None:
    """``None`` is missing and a true zero is kept; bool, text, blobs and
    +/-inf/NaN are invalid and become null."""

    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        invalid.append(label)
        return None
    if isinstance(value, float) and not math.isfinite(value):
        invalid.append(label)
        return None
    return value


def _rank(value: Any, label: str, invalid: list[str]) -> int | None:
    """A rank, when present, must be a positive integer."""

    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        invalid.append(label)
        return None
    return value
