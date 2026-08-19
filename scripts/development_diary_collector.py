"""Deterministic Development Diary daily collector for Issue #730."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import jsonschema

JST = ZoneInfo("Asia/Tokyo")


def schema_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data/contracts/development-diary-daily-v1.schema.json"


def load_schema() -> dict[str, Any]:
    return json.loads(schema_path().read_text(encoding="utf-8"))


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    jsonschema.Draft202012Validator(
        load_schema(), format_checker=jsonschema.FormatChecker()
    ).validate(snapshot)


def calc_window(diary_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(diary_date, time.min, tzinfo=JST)
    return start, start + timedelta(days=1)


def in_range(value: datetime | None, start: datetime, end: datetime) -> bool:
    return value is not None and start <= value < end


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(JST)


def stable_event_id(event: dict[str, Any]) -> str:
    explicit = event.get("event_id")
    if explicit:
        return str(explicit)
    kind = str(event.get("kind", "UNKNOWN"))
    ref = event.get("ref") or event.get("number")
    occurred = (
        event.get("occurred_at")
        or event.get("created_at")
        or event.get("merged_at")
        or event.get("closed_at")
    )
    if ref is None or occurred is None:
        raise ValueError("durable event requires event_id or kind+ref+timestamp")
    return f"{kind}:{ref}:{occurred}"


def _blank_executor_stats() -> dict[str, Any]:
    return {
        "dispatch_count": 0,
        "ack_count": 0,
        "execution_evidence_count": 0,
        "pr_count": 0,
        "merge_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "terminal_noop_count": 0,
        "elapsed_minutes": None,
        "lead_time_minutes": None,
        "rework_count": 0,
        "duplicate_conflict_waste_count": 0,
    }


class DailyCollector:
    def __init__(self, diary_date: date):
        self.diary_date = diary_date
        self.start, self.end = calc_window(diary_date)
        self.seen_events: set[str] = set()
        self.exec_stats: dict[tuple[str, str], dict[str, Any]] = defaultdict(
            _blank_executor_stats
        )
        self.ready_count = 0
        self.implementation_start_count = 0
        self.pr_opened = 0
        self.pr_merged = 0
        self.pr_closed_unmerged = 0
        self.active_wip = 0
        self.waiting_count = 0
        self.ready_nonconflicting_count = 0
        self.corrections: list[dict[str, Any]] = []
        self._correction_ids: set[str] = set()

    def record(self, event: dict[str, Any]) -> None:
        event_id = stable_event_id(event)
        if event_id in self.seen_events:
            return
        occurred = parse_ts(event.get("occurred_at"))
        if not in_range(occurred, self.start, self.end):
            return
        self.seen_events.add(event_id)

        kind = str(event.get("kind", "UNKNOWN"))
        executor = str(event.get("executor") or "UNKNOWN")
        task_class = str(event.get("task_class") or "UNKNOWN")
        stats = self.exec_stats[(executor, task_class)]

        if kind == "READY":
            self.ready_count += 1
            if event.get("nonconflicting") is True:
                self.ready_nonconflicting_count += 1
        elif kind == "DISPATCHED":
            stats["dispatch_count"] += 1
            self.waiting_count += 1
        elif kind == "ACKED":
            stats["ack_count"] += 1
        elif kind == "EXECUTION_EVIDENCE":
            stats["execution_evidence_count"] += 1
            self.implementation_start_count += 1
            self.waiting_count = max(0, self.waiting_count - 1)
            self.active_wip += 1
        elif kind == "PR_OPEN":
            stats["pr_count"] += 1
            self.pr_opened += 1
            # TEAM_STATE: PR_OPEN releases implementation capacity.
            self.active_wip = max(0, self.active_wip - 1)
        elif kind == "MERGED":
            stats["merge_count"] += 1
            stats["success_count"] += 1
            self.pr_merged += 1
        elif kind == "PR_CLOSED_UNMERGED":
            self.pr_closed_unmerged += 1
            # Fail-safe for streams missing the prior PR_OPEN event.
            self.active_wip = max(0, self.active_wip - 1)
        elif kind == "FAILURE":
            stats["failure_count"] += 1
        elif kind == "TERMINAL_NOOP":
            stats["terminal_noop_count"] += 1

    def add_correction(
        self, late_event: dict[str, Any], reason: str, recorded_at: datetime
    ) -> None:
        event_id = stable_event_id(late_event)
        correction_id = "corr-" + hashlib.sha256(event_id.encode()).hexdigest()[:24]
        if correction_id in self._correction_ids:
            return
        refs = late_event.get("evidence_refs") or [
            str(late_event.get("ref") or event_id)
        ]
        self.corrections.append(
            {
                "correction_id": correction_id,
                "reason": reason,
                "evidence_refs": list(refs),
                "recorded_at": recorded_at.isoformat(),
            }
        )
        self._correction_ids.add(correction_id)

    def snapshot(self, closed_at: datetime | None = None) -> dict[str, Any]:
        closed_at = closed_at or self.end + timedelta(minutes=10)
        executor_performance = [
            {"executor": executor, "task_class": task_class, **stats}
            for (executor, task_class), stats in sorted(self.exec_stats.items())
        ]
        snapshot = {
            "schema_version": "1.0",
            "diary_date_jst": self.diary_date.isoformat(),
            "closed_at_jst": closed_at.isoformat(),
            "source_window_start_jst": self.start.isoformat(),
            "source_window_end_jst": self.end.isoformat(),
            "factory_output": {
                "ready_count": self.ready_count,
                "implementation_start_count": self.implementation_start_count,
                "pr_opened": self.pr_opened,
                "pr_merged": self.pr_merged,
                "pr_closed_unmerged": self.pr_closed_unmerged,
                "durable_output_count": self.pr_opened + self.pr_merged,
                "productive_step_count": self.pr_opened + self.pr_merged,
                "lead_time_minutes": None,
            },
            "executor_performance": executor_performance,
            "flow_health": {
                "active_implementation_wip": self.active_wip,
                "waiting_work_count": self.waiting_count,
                "ready_nonconflicting_count": self.ready_nonconflicting_count,
                "queue_replenish_latency_minutes": None,
                "path_owner_conflict_count": 0,
                "ci_stall_count": 0,
                "starvation_state": "UNKNOWN",
                "blocked_escape_count": 0,
                "human_intervention_count": 0,
                "durable_output_interval_minutes": None,
            },
            "economics": {
                "free_executor_ratio": None,
                "paid_fallback_count": 0,
                "copilot_usage_count": None,
                "copilot_credits": None,
                "ai_cost_per_accepted_unit": None,
                "ai_cost_per_merge": None,
            },
            "factory_capability_changes": [],
            "corrections": self.corrections,
        }
        validate_snapshot(snapshot)
        return snapshot


def persist_snapshot(snapshot: dict[str, Any], target: Path) -> None:
    """Validate first, then atomically replace target."""
    validate_snapshot(snapshot)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=target.name + ".", dir=target.parent, text=True
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def collect_events(
    events: Iterable[dict[str, Any]],
    diary_date: date,
    closed_at: datetime | None = None,
) -> dict[str, Any]:
    collector = DailyCollector(diary_date)
    for event in events:
        collector.record(event)
    return collector.snapshot(closed_at)


def _github_items(repo: str, token: str, start: datetime) -> list[dict[str, Any]]:
    params = urlencode(
        {"state": "all", "since": start.isoformat(), "per_page": 100}
    )
    req = Request(
        f"https://api.github.com/repos/{repo}/issues?{params}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "sado-development-diary",
        },
    )
    try:
        with urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"GitHub evidence fetch failed: {exc}") from exc
    if not isinstance(data, list):
        raise RuntimeError("unexpected GitHub response")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--diary-date", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--events-json",
        help="deterministic normalized event input; production adapters may generate this",
    )
    args = parser.parse_args()
    diary_date = date.fromisoformat(args.diary_date)

    if args.events_json:
        events = json.loads(Path(args.events_json).read_text(encoding="utf-8"))
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not args.repo or not token:
            parser.error(
                "--events-json or both --repo/GITHUB_REPOSITORY and GITHUB_TOKEN are required"
            )
        raw = _github_items(args.repo, token, calc_window(diary_date)[0])
        events = []
        for item in raw:
            if item.get("pull_request") and item.get("created_at"):
                events.append(
                    {
                        "kind": "PR_OPEN",
                        "ref": f"pr:{item['number']}",
                        "occurred_at": item["created_at"],
                        "executor": (item.get("user") or {}).get("login")
                        or "UNKNOWN",
                        "task_class": "UNKNOWN",
                    }
                )

    snapshot = collect_events(events, diary_date)
    persist_snapshot(snapshot, Path(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
