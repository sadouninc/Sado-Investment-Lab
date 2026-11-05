"""Issue #873: opt-in orchestration with fresh issue inventory before one POST."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

from scripts.actions_failure_collector import GitHubReadOnlyClient, collect_current_failure
from scripts.actions_failure_issue_writer import post_validated_issue


def _observable_result(result: dict, *, issue_post: str) -> dict:
    """Return only bounded identifiers needed to audit a dry-run decision."""
    decision = result.get("decision")
    if not isinstance(decision, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", decision):
        decision = "HOLD_INVALID_DECISION"
    output = {"decision": decision, "issue_post": issue_post}
    # Selection can identify a verified run before complete job analysis exists.
    source_run_id = result.get("source_run_id")
    if isinstance(source_run_id, int) and not isinstance(source_run_id, bool) and source_run_id > 0:
        output["source_run_id"] = source_run_id
    analysis = result.get("analysis")
    if not isinstance(analysis, dict):
        return output
    for key in ("source_run_id", "job_id"):
        value = analysis.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            output[key] = value
    error_class = analysis.get("error_class")
    if isinstance(error_class, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", error_class):
        output["error_class"] = error_class
    request_id = analysis.get("request_id")
    if isinstance(request_id, str) and re.fullmatch(r"actions-failure-[0-9a-f]{20}", request_id):
        output["request_id"] = request_id
    return output



class _RecordingClient:
    """Preserve the exact first-pass GET inputs for a fail-closed recheck."""
    def __init__(self, client):
        self.client = client
        # collect_current_failure relies on the read-only client's repository
        # identity when binding runs back to the current open PR inventory.
        self.repository = client.repository
        self.calls = []

    def all_pages(self, endpoint, key, params):
        from copy import deepcopy
        value = self.client.all_pages(endpoint, key, params)
        self.calls.append((endpoint, key, deepcopy(params), deepcopy(value)))
        return value


def _revalidate_before_post(client, first_calls, result):
    """Recheck the four logical GET boundaries; never infer missing bindings."""
    from copy import deepcopy
    from scripts.actions_failure_collector import IncompleteInventory
    from scripts.actions_failure_analyzer import decide_issue_action

    if len(first_calls) != 4:
        raise IncompleteInventory("initial GET boundaries incomplete")
    expected = ("pulls", "actions/runs", None, "issues")
    if tuple(x[0] if i != 2 else None for i, x in enumerate(first_calls)) != expected:
        raise IncompleteInventory("unexpected initial GET order")
    run_id = result.get("analysis", {}).get("source_run_id")
    if type(run_id) is not int or run_id <= 0 or first_calls[2][0] != f"actions/runs/{run_id}/jobs":
        raise IncompleteInventory("source run binding unverified")
    if not isinstance(result.get("analysis"), dict) or not isinstance(result.get("issue_draft"), dict):
        raise IncompleteInventory("proposal binding unavailable")
    # Fresh order: issues, pulls, runs, jobs. All GETs must succeed.
    fresh = {}
    for index in (3, 0, 1, 2):
        endpoint, key, params, previous = first_calls[index]
        current = client.all_pages(endpoint, key, deepcopy(params))
        if current != previous:
            raise IncompleteInventory("pre-POST source changed")
        fresh[index] = current
    if decide_issue_action(result["analysis"], fresh[3], inventory_complete=True) != "ISSUE_DRAFT_ELIGIBLE":
        raise IncompleteInventory("duplicate or proposal no longer eligible")
    return fresh[3]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--enable-post", action="store_true")
    parser.add_argument("--max-age-hours", type=int, default=24)
    args = parser.parse_args(argv)
    scheduled = os.environ.get("GITHUB_EVENT_NAME") == "schedule"
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GH_TOKEN", "")
    # Never POST from a non-main ref, PR, schedule, or without exact opt-in.
    enabled = (
        args.enable_post
        and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        and os.environ.get("GITHUB_REF") == "refs/heads/main"
        and os.environ.get("ISSUE_POST_CONFIRM") == "ISSUE873_CREATE_ONE"
    )
    if not repo or not token:
        print(json.dumps({"decision": "HOLD_MISSING_ENV", "issue_post": "SKIPPED" if scheduled else "DISABLED"}, sort_keys=True))
        return 2
    try:
        client = _RecordingClient(GitHubReadOnlyClient(repo, token))
        result = collect_current_failure(client, as_of=datetime.now(timezone.utc), max_age_hours=args.max_age_hours)
        decision = result.get("decision")
        if decision != "ISSUE_DRAFT_ELIGIBLE":
            print(json.dumps(_observable_result(result, issue_post="SKIPPED"), sort_keys=True))
            return 0 if decision in {"NO_CURRENT_OPEN_PR_FAILURE", "DUPLICATE_SUPPRESSED"} else 2
        if not enabled:
            post_state = "SKIPPED" if os.environ.get("GITHUB_EVENT_NAME") == "schedule" else "DISABLED"
            print(json.dumps(_observable_result(result, issue_post=post_state), sort_keys=True))
            return 0
        # Fresh all-state inventory after proposal creation, immediately before POST.
        # Revalidation must not mutate the first-pass evidence log. Use the
        # underlying GET-only client and an immutable snapshot of recorded calls.
        from copy import deepcopy
        issues = _revalidate_before_post(client.client, deepcopy(client.calls), result)
        created = post_validated_issue(repo, token, result, issues, inventory_complete=True, enable_post=True)
        print(json.dumps({"decision": "ISSUE_CREATED", "issue_number": created.get("number"), "request_id": result["analysis"]["request_id"]}, sort_keys=True))
        return 0
    except Exception as exc:
        # Do not print API payloads or tokens; never automatically retry an uncertain POST.
        print(json.dumps({"decision": "HOLD_ERROR", "error_type": type(exc).__name__, "issue_post": "SKIPPED" if scheduled else "UNVERIFIED"}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())

