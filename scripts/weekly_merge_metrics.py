"""Reproducible JST weekly merged-PR counts (#689, #1003).

Pure helper intended as an extension candidate for the existing productivity
collector (``scripts/productivity_daily_dashboard.py`` aggregates per JST
*day*; this module adds per JST *week*).  It does not fetch, publish, or
persist anything.

Weeks start on Monday 00:00 JST (UTC+9, no DST) and are labelled by that
Monday's date.  A week is ``VERIFIED`` only when the caller states the source
fetch was complete over a range that covers the whole week *and* no merged
record could not be placed.  Otherwise the week is ``UNKNOWN`` and its count
is only an observed lower bound (``count`` is still reported, never inflated
or guessed).

Input records are GitHub PR-like objects: ``number`` (int), ``merged_at``
(ISO-8601 with timezone, or null) and optionally ``merged`` (bool).
Duplicates of the same PR with the same ``merged_at`` are counted once;
contradictory duplicates are not placed and make the affected range UNKNOWN.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

JST = timezone(timedelta(hours=9), "JST")

STATUS_VERIFIED = "VERIFIED"
STATUS_UNKNOWN = "UNKNOWN"

EVIDENCE_LIMITS = (
    "counts derive only from the supplied records; nothing was fetched",
    "source completeness is the caller's claim (coverage.complete) and is not independently verified",
    "UNKNOWN week counts are observed lower bounds, not totals",
)


def parse_timestamp(value: Any) -> datetime | None:
    """Parse an aware ISO-8601 timestamp; naive or malformed values return None."""

    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def week_start(moment: datetime) -> date:
    """Monday (JST) of the week containing ``moment``."""

    local = moment.astimezone(JST).date()
    return local - timedelta(days=local.weekday())


def _week_bounds(monday: date) -> tuple[datetime, datetime]:
    start = datetime(monday.year, monday.month, monday.day, tzinfo=JST)
    return start, start + timedelta(days=7)


def _is_pr(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def summarize_weeks(
    records: Iterable[Any],
    *,
    first_week: date,
    weeks: int,
    coverage: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic weekly report. Never raises on bad record content."""

    if weeks < 1:
        raise ValueError("weeks must be >= 1")
    if first_week.weekday() != 0:
        raise ValueError("first_week must be a Monday (JST week start)")

    records = list(records)
    anomalies: list[dict[str, Any]] = []
    record_counts: dict[int, int] = {}
    by_number: dict[int, set[datetime]] = {}
    unplaced: set[Any] = set()

    for pos, rec in enumerate(records):
        if not isinstance(rec, Mapping) or not _is_pr(rec.get("number")):
            anomalies.append({"code": "MALFORMED_RECORD", "index": pos})
            unplaced.add(f"index:{pos}")
            continue
        num = rec["number"]
        merged_flag = rec.get("merged")
        raw = rec.get("merged_at")
        if raw is None:
            if merged_flag is True:
                anomalies.append({"code": "MERGED_WITHOUT_TIMESTAMP", "pr": num})
                unplaced.add(num)
            continue  # not merged: not counted, not an anomaly
        ts = parse_timestamp(raw)
        if ts is None:
            anomalies.append({"code": "MALFORMED_MERGED_AT", "pr": num})
            unplaced.add(num)
            continue
        if merged_flag is False:
            anomalies.append({"code": "CONTRADICTORY_MERGE_FLAG", "pr": num})
            unplaced.add(num)
            continue
        by_number.setdefault(num, set()).add(ts)
        record_counts[num] = record_counts.get(num, 0) + 1

    placed: dict[int, datetime] = {}
    for num, stamps in by_number.items():
        if len(stamps) > 1:
            anomalies.append({"code": "CONFLICTING_DUPLICATE", "pr": num})
            unplaced.add(num)
            continue
        placed[num] = next(iter(stamps))
    duplicates = sum(record_counts[n] - 1 for n in placed)

    cov = coverage or {}
    cov_complete = cov.get("complete") is True
    cov_since = parse_timestamp(cov.get("since"))
    cov_until = parse_timestamp(cov.get("until"))
    bad_since = cov.get("since") is not None and cov_since is None
    bad_until = cov.get("until") is not None and cov_until is None
    if bad_since or bad_until:
        anomalies.append({"code": "MALFORMED_COVERAGE"})
        cov_complete = False

    rows: list[dict[str, Any]] = []
    for i in range(weeks):
        monday = first_week + timedelta(days=7 * i)
        start, end = _week_bounds(monday)
        prs = sorted(n for n, ts in placed.items() if start <= ts < end)
        reasons: list[str] = []
        if not cov_complete:
            reasons.append("source fetch not declared complete")
        if cov_since is None or cov_since > start:
            reasons.append("coverage does not reach week start")
        if cov_until is None or cov_until < end:
            reasons.append("coverage does not reach week end")
        if unplaced:
            reasons.append(f"{len(unplaced)} merged record(s) could not be placed")
        rows.append(
            {
                "week_start_jst": monday.isoformat(),
                "count": len(prs),
                "prs": prs,
                "status": STATUS_UNKNOWN if reasons else STATUS_VERIFIED,
                "unknown_reasons": reasons,
            }
        )

    window_start = _week_bounds(first_week)[0]
    window_end = _week_bounds(first_week + timedelta(days=7 * (weeks - 1)))[1]
    outside = sorted(n for n, ts in placed.items() if not (window_start <= ts < window_end))
    anomalies.sort(key=lambda a: (a["code"], str(a.get("pr", a.get("index", "")))))
    return {
        "schema": "weekly_merge_metrics_v1",
        "timezone": "Asia/Tokyo (UTC+9)",
        "week_starts_on": "Monday",
        "weeks": rows,
        "total_in_window": sum(r["count"] for r in rows),
        "all_weeks_verified": all(r["status"] == STATUS_VERIFIED for r in rows),
        "deduplicated_records": duplicates,
        "outside_window_prs": outside,
        "anomalies": anomalies,
        "coverage": {
            "complete": cov_complete,
            "since": cov_since.isoformat() if cov_since else None,
            "until": cov_until.isoformat() if cov_until else None,
        },
        "evidence_limits": list(EVIDENCE_LIMITS),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, required=True,
                        help='JSON: {"records": [...], "coverage": {"complete": bool, "since": iso, "until": iso}}')
    parser.add_argument("--first-week", required=True, help="Monday JST date, YYYY-MM-DD")
    parser.add_argument("--weeks", type=int, default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        doc = json.loads(args.input.read_text(encoding="utf-8"))
        first = date.fromisoformat(args.first_week)
    except (OSError, ValueError, RecursionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not isinstance(doc, dict) or not isinstance(doc.get("records"), list):
        print("error: input must be an object with a records list", file=sys.stderr)
        return 2
    coverage = doc.get("coverage")
    try:
        report = summarize_weeks(
            doc["records"], first_week=first, weeks=args.weeks,
            coverage=coverage if isinstance(coverage, dict) else None,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(text)
    if args.output is not None:
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0 if report["all_weeks_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
