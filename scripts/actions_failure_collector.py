"""Read-only GitHub Actions failure discovery for Issue #873.

No issue mutations, no workflow dispatch, no READY promotion. Network I/O is
GET-only and scoped to the selected repository. Fail closed on partial pages.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from scripts.actions_failure_analyzer import build_issue_draft, decide_issue_action
from scripts.actions_failure_selection import select_open_pr_failure

_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class IncompleteInventory(RuntimeError):
    """API or pagination uncertainty; no issue should be generated."""


class GitHubReadOnlyClient:
    def __init__(self, repository: str, token: str, *, max_pages: int = 10):
        if not _REPO.fullmatch(repository):
            raise ValueError("invalid repository")
        if not token:
            raise IncompleteInventory("missing read token")
        if not 1 <= max_pages <= 100:
            raise ValueError("invalid page bound")
        self.repository = repository
        self.token = token
        self.max_pages = max_pages

    def get_json(self, endpoint: str, params: dict[str, str | int]):
        """Allow only fixed read-only resource families, no caller-supplied URLs."""
        allowed = (
            endpoint == "pulls"
            or endpoint == "issues"
            or endpoint == "actions/runs"
            or re.fullmatch(r"actions/runs/[1-9][0-9]*/jobs", endpoint)
        )
        if not allowed:
            raise ValueError("endpoint not allowlisted")
        url = f"https://api.github.com/repos/{self.repository}/{endpoint}?{urlencode(params)}"
        req = Request(url, headers={
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sado-issue873-readonly",
        }, method="GET")
        try:
            with urlopen(req, timeout=15) as response:
                if response.status != 200:
                    raise IncompleteInventory(f"unexpected HTTP status {response.status}")
                data = response.read(5_000_001)
                if len(data) > 5_000_000:
                    raise IncompleteInventory("oversized API response")
                return json.loads(data)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise IncompleteInventory(f"read failed ({type(exc).__name__})") from None

    def all_pages(self, endpoint: str, key: str | None, params: dict[str, str | int]):
        result = []
        counted = endpoint == "actions/runs" or re.fullmatch(r"actions/runs/[1-9][0-9]*/jobs", endpoint)
        expected_count = None
        seen_ids = set()
        for page in range(1, self.max_pages + 1):
            raw = self.get_json(endpoint, {**params, "per_page": 100, "page": page})
            if key is not None:
                if not isinstance(raw, dict) or not isinstance(raw.get(key), list):
                    raise IncompleteInventory("invalid API inventory shape")
                items = raw[key]
            else:
                if not isinstance(raw, list):
                    raise IncompleteInventory("invalid API inventory shape")
                items = raw
            if len(items) > 100:
                raise IncompleteInventory("oversized API page")
            if counted:
                count = raw.get("total_count") if isinstance(raw, dict) else None
                if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                    raise IncompleteInventory("invalid or missing inventory count")
                if expected_count is not None and count != expected_count:
                    raise IncompleteInventory("inventory count changed between pages")
                expected_count = count
                for item in items:
                    identifier = item.get("id") if isinstance(item, dict) else None
                    if isinstance(identifier, bool) or not isinstance(identifier, int) or identifier < 1:
                        raise IncompleteInventory("invalid inventory identifier")
                    if identifier in seen_ids:
                        raise IncompleteInventory("duplicate inventory identifier")
                    seen_ids.add(identifier)
            result.extend(items)
            if counted and len(result) > expected_count:
                raise IncompleteInventory("inventory exceeds declared count")
            if len(items) < 100:
                if counted and len(result) != expected_count:
                    raise IncompleteInventory("incomplete declared inventory")
                return result
        raise IncompleteInventory("pagination bound reached")


def collect_current_failure(client: GitHubReadOnlyClient, *, as_of: datetime, max_age_hours: int = 24):
    if as_of.tzinfo is None or not 1 <= max_age_hours <= 168:
        raise ValueError("invalid lookback")
    since = (as_of.astimezone(timezone.utc) - timedelta(hours=max_age_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    prs = client.all_pages("pulls", None, {"state": "open"})
    runs = client.all_pages("actions/runs", "workflow_runs", {"created": f">={since}", "event": "pull_request"})
    preliminary = select_open_pr_failure(
        client.repository, runs, prs, {}, as_of=as_of,
        runs_inventory_complete=True, prs_inventory_complete=True,
        jobs_inventory_complete={}, max_age_hours=max_age_hours,
    )
    if preliminary["decision"] != "HOLD_INCOMPLETE_JOB_INVENTORY":
        return preliminary
    run_id = preliminary["source_run_id"]
    jobs = client.all_pages(f"actions/runs/{run_id}/jobs", "jobs", {})
    final = select_open_pr_failure(
        client.repository, runs, prs, {run_id: jobs}, as_of=as_of,
        runs_inventory_complete=True, prs_inventory_complete=True,
        jobs_inventory_complete={run_id: True}, max_age_hours=max_age_hours,
    )
    if final["decision"] == "ISSUE_DRAFT_ELIGIBLE":
        issues = client.all_pages("issues", None, {"state": "all"})
        final["decision"] = decide_issue_action(
            final["analysis"], issues, inventory_complete=True,
        )
        if final["decision"] == "ISSUE_DRAFT_ELIGIBLE":
            final["issue_draft"] = build_issue_draft(final["analysis"])
        final["write_performed"] = False
        final["ready_promoted"] = False
    return final


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only current PR CI failure discovery")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--max-age-hours", type=int, default=24)
    args = parser.parse_args(argv)
    try:
        client = GitHubReadOnlyClient(args.repository, os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", ""))
        result = collect_current_failure(client, as_of=datetime.now(timezone.utc), max_age_hours=args.max_age_hours)
    except (IncompleteInventory, ValueError) as exc:
        result = {"decision": "HOLD_INCOMPLETE_INVENTORY", "reason": str(exc)}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["decision"] in {"NO_CURRENT_OPEN_PR_FAILURE", "ISSUE_DRAFT_ELIGIBLE"} else 2


if __name__ == "__main__":
    sys.exit(main())
