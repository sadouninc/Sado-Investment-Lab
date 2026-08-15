from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

TOKYO = ZoneInfo("Asia/Tokyo")
MARKER = "<!-- productivity-daily-dashboard -->"
API_ROOT = "https://api.github.com"


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("GitHub timestamp must be timezone-aware")
    return parsed


def jst_date(value: str | None) -> date | None:
    parsed = parse_timestamp(value)
    return parsed.astimezone(TOKYO).date() if parsed else None


def day_window(now: datetime, days: int) -> list[date]:
    if days <= 0:
        raise ValueError("days must be positive")
    local_now = now.astimezone(TOKYO)
    start = local_now.date() - timedelta(days=days - 1)
    return [start + timedelta(days=offset) for offset in range(days)]


def summarize(items: Iterable[dict[str, object]], *, now: datetime, days: int = 14) -> dict[str, object]:
    dates = day_window(now, days)
    allowed = set(dates)
    counts = {
        day: {"pr_created": 0, "issue_created": 0, "issue_closed": 0}
        for day in dates
    }

    for item in items:
        created = jst_date(str(item.get("created_at")) if item.get("created_at") else None)
        is_pr = "pull_request" in item
        if created in allowed:
            key = "pr_created" if is_pr else "issue_created"
            counts[created][key] += 1

        if not is_pr:
            closed = jst_date(str(item.get("closed_at")) if item.get("closed_at") else None)
            if closed in allowed:
                counts[closed]["issue_closed"] += 1

    rows = []
    for day in dates:
        row = {"date": day.isoformat(), **counts[day]}
        row["issue_net_change"] = row["issue_created"] - row["issue_closed"]
        rows.append(row)

    totals = {
        key: sum(int(row[key]) for row in rows)
        for key in ("pr_created", "issue_created", "issue_closed")
    }
    totals["issue_net_change"] = totals["issue_created"] - totals["issue_closed"]
    averages = {key: round(value / days, 2) for key, value in totals.items()}

    return {
        "schema_version": "1.0",
        "timezone": "Asia/Tokyo",
        "window_days": days,
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "rows": rows,
        "totals": totals,
        "averages": averages,
    }


def _chart(title: str, labels: list[str], values: list[int]) -> str:
    ymax = max(max(values, default=0), 1)
    label_json = json.dumps(labels, ensure_ascii=False)
    values_json = json.dumps(values)
    return (
        f"### {title}\n\n"
        "```mermaid\n"
        "xychart-beta\n"
        f"    x-axis {label_json}\n"
        f"    y-axis \"件数\" 0 --> {ymax}\n"
        f"    bar {values_json}\n"
        "```\n"
    )


def render_markdown(metrics: dict[str, object]) -> str:
    rows = list(metrics["rows"])
    totals = dict(metrics["totals"])
    averages = dict(metrics["averages"])
    labels = [str(row["date"])[5:].replace("-", "/") for row in rows]

    parts = [
        MARKER,
        "## 📈 Daily Throughput Dashboard",
        "",
        f"直近 **{metrics['window_days']}日 / JST** のGitHub activityを自動集計しています。",
        "これは活動量の観測レイヤであり、**Issue/PR件数の最大化自体を生産性の目的にはしません**。#479のproductive steps / durable outputs / lead timeと組み合わせて評価します。",
        "",
        "| 指標 | 期間合計 | 1日平均 |",
        "| --- | ---: | ---: |",
        f"| PR発行 | {totals['pr_created']} | {averages['pr_created']:.2f} |",
        f"| Issue発行 | {totals['issue_created']} | {averages['issue_created']:.2f} |",
        f"| Issue Close | {totals['issue_closed']} | {averages['issue_closed']:.2f} |",
        f"| Issue純増減 | {totals['issue_net_change']:+d} | {averages['issue_net_change']:+.2f} |",
        "",
        _chart("PR発行数 / 日", labels, [int(row["pr_created"]) for row in rows]),
        _chart("Issue発行数 / 日", labels, [int(row["issue_created"]) for row in rows]),
        _chart("Issue Close数 / 日", labels, [int(row["issue_closed"]) for row in rows]),
        "### 日次データ",
        "",
        "| JST日付 | PR発行 | Issue発行 | Issue Close | Issue純増減 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        parts.append(
            f"| {row['date']} | {row['pr_created']} | {row['issue_created']} | "
            f"{row['issue_closed']} | {int(row['issue_net_change']):+d} |"
        )
    parts.extend(
        [
            "",
            f"集計時刻: `{metrics['generated_at']}` / timezone: `{metrics['timezone']}`",
            "",
            "集計ルール: GitHub Issues APIをSSoTとし、PRはIssue API上のpull_request markerで判別してIssue発行/Closeから除外します。取得失敗時は0件へ丸めずworkflowを失敗させます。",
        ]
    )
    return "\n".join(parts).strip() + "\n"


def github_request(url: str, token: str, *, method: str = "GET", payload: dict[str, object] | None = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sado-investment-lab-productivity-dashboard",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {exc.code}: {detail}") from exc


def fetch_recent_items(repo: str, token: str, *, now: datetime, days: int) -> list[dict[str, object]]:
    local_start = day_window(now, days)[0]
    start_jst = datetime.combine(local_start, time.min, tzinfo=TOKYO)
    since = start_jst.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    items: list[dict[str, object]] = []
    page = 1
    while True:
        params = urlencode(
            {
                "state": "all",
                "sort": "updated",
                "direction": "desc",
                "since": since,
                "per_page": 100,
                "page": page,
            }
        )
        payload = github_request(f"{API_ROOT}/repos/{repo}/issues?{params}", token)
        if not isinstance(payload, list):
            raise RuntimeError("unexpected GitHub Issues API response")
        items.extend(payload)
        if len(payload) < 100:
            break
        page += 1
        if page > 50:
            raise RuntimeError("pagination safety limit exceeded")
    return items


def publish_comment(repo: str, issue_number: int, token: str, body: str) -> str:
    page = 1
    existing_id = None
    while True:
        comments = github_request(
            f"{API_ROOT}/repos/{repo}/issues/{issue_number}/comments?per_page=100&page={page}", token
        )
        if not isinstance(comments, list):
            raise RuntimeError("unexpected issue comments response")
        for comment in comments:
            if MARKER in str(comment.get("body", "")):
                existing_id = int(comment["id"])
                break
        if existing_id is not None or len(comments) < 100:
            break
        page += 1

    if existing_id is None:
        result = github_request(
            f"{API_ROOT}/repos/{repo}/issues/{issue_number}/comments",
            token,
            method="POST",
            payload={"body": body},
        )
        return str(result.get("html_url", "created"))

    result = github_request(
        f"{API_ROOT}/repos/{repo}/issues/comments/{existing_id}",
        token,
        method="PATCH",
        payload={"body": body},
    )
    return str(result.get("html_url", "updated"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--issue", type=int, default=479)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--output-json")
    parser.add_argument("--output-markdown")
    parser.add_argument("--publish-comment", action="store_true")
    args = parser.parse_args()

    if not args.repo:
        parser.error("--repo or GITHUB_REPOSITORY is required")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        parser.error("GITHUB_TOKEN is required")

    now = datetime.now(timezone.utc)
    items = fetch_recent_items(args.repo, token, now=now, days=args.days)
    metrics = summarize(items, now=now, days=args.days)
    markdown = render_markdown(metrics)

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as handle:
            json.dump(metrics, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    if args.output_markdown:
        with open(args.output_markdown, "w", encoding="utf-8") as handle:
            handle.write(markdown)
    if args.publish_comment:
        print(publish_comment(args.repo, args.issue, token, markdown))
    elif not args.output_markdown:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
