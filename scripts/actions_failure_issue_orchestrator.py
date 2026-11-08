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


def _positive_unique_numbers(items, *, label):
    """Return canonical positive identifiers or fail closed on ambiguity."""
    from scripts.actions_failure_collector import IncompleteInventory

    numbers = []
    for item in items:
        value = item.get("number") if isinstance(item, dict) else None
        if type(value) is not int or value <= 0:
            raise IncompleteInventory(f"invalid {label} identifier")
        numbers.append(value)
    if len(numbers) != len(set(numbers)):
        raise IncompleteInventory(f"duplicate {label} identifier")
    return numbers


def _revalidate_before_post(
    client,
    first_calls,
    result,
    *,
    as_of=None,
    max_age_hours=24,
    monotonic_clock=None,
    max_revalidation_seconds=120,
):
    """Recheck the four logical GET boundaries; never infer missing bindings."""
    from copy import deepcopy
    from scripts.actions_failure_collector import IncompleteInventory
    from scripts.actions_failure_analyzer import build_issue_draft, decide_issue_action
    from scripts.actions_failure_selection import select_open_pr_failure
    from time import monotonic

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
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    if as_of.tzinfo is None or not 1 <= max_age_hours <= 168:
        raise IncompleteInventory("invalid revalidation clock")
    if type(max_revalidation_seconds) not in (int, float) or not 0 < max_revalidation_seconds <= 120:
        raise IncompleteInventory("invalid revalidation duration bound")
    clock = monotonic_clock or monotonic
    started = clock()
    if isinstance(started, bool) or not isinstance(started, (int, float)):
        raise IncompleteInventory("invalid monotonic clock")
    # Fresh order: issues, pulls, runs, jobs. All GETs must succeed.
    fresh = {}
    for index in (3, 0, 1, 2):
        endpoint, key, params, previous = first_calls[index]
        current = client.all_pages(endpoint, key, deepcopy(params))
        if current != previous:
            raise IncompleteInventory("pre-POST source changed")
        fresh[index] = current
    _positive_unique_numbers(fresh[0], label="pull request")
    _positive_unique_numbers(fresh[3], label="issue")
    run_ids = [item.get("id") if isinstance(item, dict) else None for item in fresh[1]]
    job_ids = [item.get("id") if isinstance(item, dict) else None for item in fresh[2]]
    if any(type(value) is not int or value <= 0 for value in run_ids + job_ids):
        raise IncompleteInventory("invalid run or job identifier")
    if len(run_ids) != len(set(run_ids)) or len(job_ids) != len(set(job_ids)):
        raise IncompleteInventory("duplicate run or job identifier")

    bound_runs = [item for item in fresh[1] if item.get("id") == run_id]
    if len(bound_runs) != 1:
        raise IncompleteInventory("source run binding ambiguous")
    bound_run = bound_runs[0]
    linked = bound_run.get("pull_requests")
    if not isinstance(linked, list) or len(linked) != 1:
        raise IncompleteInventory("source PR binding ambiguous")
    pr_number = linked[0].get("number") if isinstance(linked[0], dict) else None
    if type(pr_number) is not int or pr_number <= 0:
        raise IncompleteInventory("source PR binding invalid")
    bound_prs = [item for item in fresh[0] if item.get("number") == pr_number]
    if len(bound_prs) != 1:
        raise IncompleteInventory("source PR binding unavailable")
    head = bound_prs[0].get("head") if isinstance(bound_prs[0], dict) else None
    if not isinstance(head, dict):
        raise IncompleteInventory("source PR head binding unavailable")
    head_sha, head_ref = head.get("sha"), head.get("ref")
    if (
        not isinstance(head_sha, str)
        or not re.fullmatch(r"[0-9a-f]{40}", head_sha)
        or not isinstance(head_ref, str)
        or not head_ref
        or bound_run.get("head_sha") != head_sha
        or bound_run.get("head_branch") != head_ref
    ):
        raise IncompleteInventory("source PR head binding changed")
    for field in ("workflow_id", "run_attempt"):
        value = bound_run.get(field)
        if type(value) is not int or value <= 0:
            raise IncompleteInventory(f"source {field} binding invalid")

    fresh_result = select_open_pr_failure(
        client.repository,
        fresh[1],
        fresh[0],
        {run_id: fresh[2]},
        as_of=as_of,
        runs_inventory_complete=True,
        prs_inventory_complete=True,
        jobs_inventory_complete={run_id: True},
        max_age_hours=max_age_hours,
    )
    if fresh_result.get("decision") != "ISSUE_DRAFT_ELIGIBLE":
        raise IncompleteInventory("fresh semantic selection no longer eligible")
    if decide_issue_action(fresh_result["analysis"], fresh[3], inventory_complete=True) != "ISSUE_DRAFT_ELIGIBLE":
        raise IncompleteInventory("duplicate or proposal no longer eligible")
    fresh_draft = build_issue_draft(fresh_result["analysis"])
    if fresh_result["analysis"] != result["analysis"] or fresh_draft != result["issue_draft"]:
        raise IncompleteInventory("fresh proposal semantic identity changed")
    finished = clock()
    if isinstance(finished, bool) or not isinstance(finished, (int, float)):
        raise IncompleteInventory("invalid monotonic clock")
    elapsed = finished - started
    if elapsed < 0 or elapsed > max_revalidation_seconds:
        raise IncompleteInventory("pre-POST revalidation duration invalid")
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
        issues = _revalidate_before_post(
            client.client,
            deepcopy(client.calls),
            result,
            as_of=datetime.now(timezone.utc),
            max_age_hours=args.max_age_hours,
        )
        created = post_validated_issue(repo, token, result, issues, inventory_complete=True, enable_post=True)
        print(json.dumps({"decision": "ISSUE_CREATED", "issue_number": created.get("number"), "request_id": result["analysis"]["request_id"]}, sort_keys=True))
        return 0
    except Exception as exc:
        # Do not print API payloads or tokens; never automatically retry an uncertain POST.
        print(json.dumps({"decision": "HOLD_ERROR", "error_type": type(exc).__name__, "issue_post": "SKIPPED" if scheduled else "UNVERIFIED"}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())

