from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re

JOURNAL_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)


@dataclass(frozen=True)
class CoverageResult:
    status: str
    missing_dates: tuple[date, ...] = ()


def discover_journal_dates(transactions_dir: Path) -> set[date]:
    dates: set[date] = set()
    for source in sorted(transactions_dir.glob("*.md")):
        text = source.read_text(encoding="utf-8")
        for match in JOURNAL_HEADING.finditer(text):
            dates.add(date.fromisoformat(match.group(1)))
    return dates


def evaluate_trade_journal_coverage(
    confirmed_execution_dates: set[date] | None,
    journal_dates: set[date],
) -> CoverageResult:
    """Compare confirmed execution dates with Trade Journal dates.

    `confirmed_execution_dates=None` means the transaction authority is unavailable,
    which must never be treated as PASS.
    """
    if confirmed_execution_dates is None:
        return CoverageResult(status="UNKNOWN")

    missing = tuple(sorted(confirmed_execution_dates - journal_dates))
    if missing:
        return CoverageResult(
            status="MISSING_TRADE_JOURNAL_DATE",
            missing_dates=missing,
        )
    return CoverageResult(status="PASS")
