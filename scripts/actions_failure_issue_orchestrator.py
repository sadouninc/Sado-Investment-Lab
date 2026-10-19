"""Issue #873: opt-in orchestration with fresh issue inventory before one POST."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from scripts.actions_failure_collector import GitHubReadOnlyClient, collect_current_failure
from scripts.actions_failure_issue_writer import post_validated_issue


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--enable-post", action="store_true")
    parser.add_argument("--max-age-hours", type=int, default=24)
    args = parser.parse_args(argv)
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GH_TOKEN", "")
    # Never POST from a non-main ref, PR, schedule, or without exact opt-in.
    enabled = (
        args.enable_post
        and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        and os.environ.get("GITHUB_REF") == "refs/heads/main"
        and os.environ.get("ISSUE_POST_CONFIRM") == "ISSUE873_CREATE_ONE"
    )
    try:
        client = GitHubReadOnlyClient(repo, token)
        result = collect_current_failure(client, as_of=datetime.now(timezone.utc), max_age_hours=args.max_age_hours)
        decision = result.get("decision")
        if decision != "ISSUE_DRAFT_ELIGIBLE":
            print(json.dumps({"decision": decision, "issue_post": "SKIPPED"}, sort_keys=True))
            return 0 if decision in {"NO_CURRENT_OPEN_PR_FAILURE", "DUPLICATE_SUPPRESSED"} else 2
        if not enabled:
            print(json.dumps({"decision": decision, "issue_post": "DISABLED"}, sort_keys=True))
            return 0
        # Fresh all-state inventory after proposal creation, immediately before POST.
        issues = client.all_pages("issues", None, {"state": "all"})
        created = post_validated_issue(repo, token, result, issues, inventory_complete=True, enable_post=True)
        print(json.dumps({"decision": "ISSUE_CREATED", "issue_number": created["number"], "request_id": created["request_id"]}, sort_keys=True))
        return 0
    except Exception as exc:
        # Do not print API payloads or tokens; never automatically retry an uncertain POST.
        print(json.dumps({"decision": "HOLD_ERROR", "error_type": type(exc).__name__, "issue_post": "UNVERIFIED"}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
