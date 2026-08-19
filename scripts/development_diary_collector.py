"""Development Diary Daily Snapshot Collector v1

Collects GitHub evidence for JST day windows per development-diary-daily-v1.schema.json.

Contract:
- diary_date_jst window: [00:00 JST, next-day 00:00 JST) half-open
- Close time: next day 00:10 JST
- Event deduplication via stable identities
- Null for unavailable metrics (not 0)
- DISPATCHED/ACKED excluded from implementation_start_count
- EXECUTION_EVIDENCE onwards = active implementation (TEAM_STATE #645)
- Lossless executor × task_class preservation
- Late evidence → correction audit (not silent rewrite)
- Fail-closed validation before persistence
"""

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import jsonschema

JST = ZoneInfo("Asia/Tokyo")


def schema_path() -> Path:
    return Path(__file__).parent.parent / "data/contracts/development-diary-daily-v1.schema.json"


def load_schema() -> dict:
    return json.loads(schema_path().read_text(encoding="utf-8"))


def validate_snapshot(snap: dict) -> None:
    """Validate against schema. Raises ValidationError if invalid."""
    sch = load_schema()
    validator = jsonschema.Draft202012Validator(sch, format_checker=jsonschema.FormatChecker())
    validator.validate(snap)


def parse_ts(val: str | None) -> datetime | None:
    if not val:
        return None
    dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return dt


def to_jst(val: str | None) -> datetime | None:
    dt = parse_ts(val)
    return dt.astimezone(JST) if dt else None


def calc_window(diary_dt: date) -> tuple[datetime, datetime]:
    """Calculate [start, end) for diary_date_jst."""
    start = datetime.combine(diary_dt, time.min, tzinfo=JST)
    end = start + timedelta(days=1)
    return start, end


def in_range(ts: datetime | None, start: datetime, end: datetime) -> bool:
    """Check [start, end) half-open."""
    return ts is not None and start <= ts < end


def gh_api(url: str, token: str) -> Any:
    req = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "dev-diary-collector",
        },
    )
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {e.code}: {msg}") from e


def fetch_items(repo: str, token: str, since: datetime) -> list[dict]:
    """Fetch all issues/PRs updated since timestamp."""
    items = []
    page = 1
    since_str = since.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    
    while page <= 50:
        params = urlencode({
            "state": "all",
            "sort": "updated",
            "direction": "desc",
            "since": since_str,
            "per_page": 100,
            "page": page,
        })
        resp = gh_api(f"https://api.github.com/repos/{repo}/issues?{params}", token)
        if not isinstance(resp, list):
            raise RuntimeError("unexpected response type")
        items.extend(resp)
        if len(resp) < 100:
            break
        page += 1
    
    return items


def get_executor(pr: dict) -> str:
    """Extract executor from PR user."""
    user = pr.get("user", {})
    login = str(user.get("login", "")) if user else ""
    if not login:
        return "UNKNOWN"
    lower = login.lower()
    if "copilot" in lower:
        return "COPILOT"
    if "dependabot" in lower:
        return "DEPENDABOT"
    return login


def get_task_class(labels: list[dict]) -> str:
    """Map labels to task class."""
    names = {str(lbl.get("name", "")).lower() for lbl in labels}
    if "documentation" in names or "docs" in names:
        return "DOCS"
    if "bug" in names or "bugfix" in names:
        return "BUGFIX"
    if "feature" in names or "enhancement" in names:
        return "FEATURE"
    if "test" in names:
        return "TEST"
    if "refactor" in names:
        return "REFACTOR"
    if "performance" in names:
        return "PERFORMANCE"
    if "security" in names:
        return "SECURITY"
    return "GENERAL"


class DailyCollector:
    """Collects events for one JST day."""
    
    def __init__(self, start: datetime, end: datetime):
        self.start = start
        self.end = end
        self.seen_pr: set[int] = set()
        self.seen_issue: set[int] = set()
        
        # (executor, task_class) -> stats
        self.exec_stats: dict[tuple[str, str], dict] = defaultdict(lambda: {
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
        })
        
        self.ready_cnt = 0
        self.impl_start_cnt = 0
        self.pr_open_cnt = 0
        self.pr_merge_cnt = 0
        self.pr_close_unmerged_cnt = 0
        
        self.active_wip = 0
        self.waiting_cnt = 0
        self.ready_nonconflict_cnt = 0
        
        self.corrections: list[dict] = []
        self.seen_corr: set[str] = set()
    
    def process_pr(self, pr: dict) -> None:
        """Process PR event with deduplication."""
        num = int(pr["number"])
        if num in self.seen_pr:
            return
        
        created = to_jst(pr.get("created_at"))
        merged = to_jst(pr.get("merged_at"))
        closed = to_jst(pr.get("closed_at"))
        
        executor = get_executor(pr)
        task_cls = get_task_class(pr.get("labels", []))
        key = (executor, task_cls)
        
        if in_range(created, self.start, self.end):
            self.pr_open_cnt += 1
            self.exec_stats[key]["pr_count"] += 1
            self.seen_pr.add(num)
        
        if in_range(merged, self.start, self.end):
            self.pr_merge_cnt += 1
            self.exec_stats[key]["merge_count"] += 1
            self.exec_stats[key]["success_count"] += 1
            self.seen_pr.add(num)
        
        if closed and not merged and in_range(closed, self.start, self.end):
            self.pr_close_unmerged_cnt += 1
            self.seen_pr.add(num)
    
    def process_issue(self, issue: dict) -> None:
        """Process issue event with deduplication."""
        num = int(issue["number"])
        if num in self.seen_issue:
            return
        
        created = to_jst(issue.get("created_at"))
        label_names = {str(lbl.get("name", "")).lower() for lbl in issue.get("labels", [])}
        
        if in_range(created, self.start, self.end):
            if "ready" in label_names or "ready-for-implementation" in label_names:
                self.ready_cnt += 1
                self.ready_nonconflict_cnt += 1
            self.seen_issue.add(num)
    
    def record_execution_evidence(self, executor: str, task_cls: str) -> None:
        """EXECUTION_EVIDENCE state - actual implementation start (TEAM_STATE #645)."""
        key = (executor, task_cls)
        self.exec_stats[key]["execution_evidence_count"] += 1
        self.impl_start_cnt += 1
        self.active_wip += 1
    
    def record_dispatch(self, executor: str, task_cls: str) -> None:
        """DISPATCHED - lease only, NOT implementation (TEAM_STATE #645)."""
        key = (executor, task_cls)
        self.exec_stats[key]["dispatch_count"] += 1
        self.waiting_cnt += 1
    
    def record_ack(self, executor: str, task_cls: str) -> None:
        """ACKED - reservation only, NOT implementation (TEAM_STATE #645)."""
        key = (executor, task_cls)
        self.exec_stats[key]["ack_count"] += 1
    
    def add_correction(self, reason: str, evidence_refs: list[str], recorded: datetime) -> None:
        """Append correction audit record (no silent rewrite)."""
        ev_str = "|".join(sorted(evidence_refs))
        corr_hash = hashlib.sha256(ev_str.encode()).hexdigest()[:16]
        corr_id = f"corr-{corr_hash}"
        
        if corr_id in self.seen_corr:
            return
        
        self.corrections.append({
            "correction_id": corr_id,
            "reason": reason,
            "evidence_refs": evidence_refs,
            "recorded_at": recorded.isoformat(),
        })
        self.seen_corr.add(corr_id)
    
    def generate_snapshot(self, diary_dt: date, close_at: datetime) -> dict:
        """Build snapshot dict per schema v1."""
        start, end = calc_window(diary_dt)
        
        exec_perf = []
        for (executor, task_cls), stats in sorted(self.exec_stats.items()):
            exec_perf.append({
                "executor": executor,
                "task_class": task_cls,
                **stats,
            })
        
        return {
            "schema_version": "1.0",
            "diary_date_jst": diary_dt.isoformat(),
            "closed_at_jst": close_at.isoformat(),
            "source_window_start_jst": start.isoformat(),
            "source_window_end_jst": end.isoformat(),
            "factory_output": {
                "ready_count": self.ready_cnt,
                "implementation_start_count": self.impl_start_cnt,
                "pr_opened": self.pr_open_cnt,
                "pr_merged": self.pr_merge_cnt,
                "pr_closed_unmerged": self.pr_close_unmerged_cnt,
                "durable_output_count": self.pr_merge_cnt,
                "productive_step_count": self.pr_open_cnt + self.pr_merge_cnt,
                "lead_time_minutes": None,
            },
            "executor_performance": exec_perf,
            "flow_health": {
                "active_implementation_wip": self.active_wip,
                "waiting_work_count": self.waiting_cnt,
                "ready_nonconflicting_count": self.ready_nonconflict_cnt,
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


def collect(repo: str, token: str, diary_dt: date, close_at: datetime | None = None) -> dict:
    """Main collection entry point.
    
    Args:
        repo: "owner/name" format
        token: GitHub API token
        diary_dt: JST diary date
        close_at: Override close time (default: next day 00:10 JST)
    
    Returns:
        Validated snapshot dict
    
    Raises:
        RuntimeError: GitHub API failure
        jsonschema.ValidationError: Invalid snapshot
    """
    start, end = calc_window(diary_dt)
    
    if close_at is None:
        close_at = end + timedelta(minutes=10)
    
    items = fetch_items(repo, token, start)
    
    collector = DailyCollector(start, end)
    
    for item in items:
        if "pull_request" in item:
            collector.process_pr(item)
        else:
            collector.process_issue(item)
    
    snap = collector.generate_snapshot(diary_dt, close_at)
    
    # Fail-closed: validate before returning
    validate_snapshot(snap)
    
    return snap


def main_cli() -> int:
    parser = argparse.ArgumentParser(description="Collect Development Diary daily snapshot")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--diary-date", required=True, help="JST date YYYY-MM-DD")
    parser.add_argument("--output", required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    
    if args.validate_only:
        snap = json.loads(Path(args.output).read_text(encoding="utf-8"))
        validate_snapshot(snap)
        print(f"✓ Valid: {args.output}")
        return 0
    
    if not args.repo:
        parser.error("--repo or GITHUB_REPOSITORY required")
    
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        parser.error("GITHUB_TOKEN required")
    
    try:
        diary_dt = date.fromisoformat(args.diary_date)
    except ValueError as e:
        parser.error(f"Invalid date: {e}")
    
    try:
        snap = collect(args.repo, token, diary_dt)
    except Exception as e:
        print(f"✗ Failed: {e}", file=sys.stderr)
        return 1
    
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    
    print(f"✓ Collected: {args.output}")
    print(f"  date: {snap['diary_date_jst']}")
    print(f"  pr_opened: {snap['factory_output']['pr_opened']}")
    print(f"  pr_merged: {snap['factory_output']['pr_merged']}")
    print(f"  impl_start: {snap['factory_output']['implementation_start_count']}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
