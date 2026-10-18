"""Fail-closed selection of *current* pull-request CI failures.

Pure functions only: no network, no GitHub mutations, no secrets, no READY promotion.
GitHub read-only collection will provide runs, open PR heads and complete jobs.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from scripts.actions_failure_analyzer import analyze_completed_failure


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("missing timestamp")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timezone required")
    return result.astimezone(timezone.utc)


def select_open_pr_failure(
    repository: str,
    workflow_runs: Iterable[Mapping[str, Any]],
    open_pull_requests: Iterable[Mapping[str, Any]],
    jobs_by_run_id: Mapping[int, Iterable[Mapping[str, Any]]],
    *,
    as_of: datetime,
    runs_inventory_complete: bool,
    prs_inventory_complete: bool,
    jobs_inventory_complete: Mapping[int, bool],
    max_age_hours: int = 24,
) -> dict[str, Any]:
    """Select at most one real, unresolved failure on the exact current PR head.

    Returns a decision and optional analysis. All inventories must be complete.
    A failure on an already merged/closed PR or superseded head is ignored.
    A newer successful run of the same workflow/head supersedes a failed run.
    """
    if as_of.tzinfo is None or max_age_hours < 1 or max_age_hours > 168:
        raise ValueError("invalid clock or lookback")
    now = as_of.astimezone(timezone.utc)
    if not runs_inventory_complete or not prs_inventory_complete:
        return {"decision": "HOLD_INCOMPLETE_INVENTORY", "analysis": None}

    heads: dict[tuple[int, str], str] = {}
    for pr in open_pull_requests:
        number = pr.get("number")
        head = pr.get("head") or {}
        if not isinstance(number, int) or number < 1 or not isinstance(head, Mapping):
            return {"decision": "HOLD_INVALID_PR_INVENTORY", "analysis": None}
        sha, ref = head.get("sha"), head.get("ref")
        if not isinstance(sha, str) or len(sha) != 40 or not isinstance(ref, str):
            return {"decision": "HOLD_INVALID_PR_INVENTORY", "analysis": None}
        heads[(number, ref)] = sha

    # One latest run per (workflow, PR, exact head), including pending runs.
    # A newer queued/in-progress run must suppress stale failure reporting.
    latest: dict[tuple[str, int, str], Mapping[str, Any]] = {}
    unverified_pr_association = False
    for run in workflow_runs:
        if run.get("event") != "pull_request":
            continue
        status = run.get("status")
        if status not in {"completed", "requested", "waiting", "pending", "queued", "in_progress"}:
            return {"decision": "HOLD_INVALID_RUN_INVENTORY", "analysis": None}
        run_id = run.get("id")
        sha, ref = run.get("head_sha"), run.get("head_branch")
        workflow = run.get("workflow_id") or run.get("name")
        if not isinstance(run_id, int) or run_id < 1 or not isinstance(sha, str) or not isinstance(ref, str):
            return {"decision": "HOLD_INVALID_RUN_INVENTORY", "analysis": None}
        try:
            created = _timestamp(run.get("created_at"))
        except (ValueError, TypeError):
            return {"decision": "HOLD_INVALID_RUN_INVENTORY", "analysis": None}
        if created > now or created < now - timedelta(hours=max_age_hours):
            continue
        # GitHub may return pull_requests=[] even for genuine pull_request runs.
        # An unassociated current-head failure/pending run must not be silently
        # counted as "no current PR failure". Do not guess the PR identity.
        linked_prs = run.get("pull_requests") or []
        if not linked_prs and any((pr_ref, pr_sha) == (ref, sha)
                                   for (_, pr_ref), pr_sha in heads.items()):
            if status != "completed" or run.get("conclusion") == "failure":
                unverified_pr_association = True
        for p in linked_prs:
            pr_number = p.get("number")
            if not isinstance(pr_number, int) or heads.get((pr_number, ref)) != sha:
                continue
            key = (str(workflow), pr_number, sha)
            old = latest.get(key)
            if old is None or (_timestamp(old["created_at"]), int(old.get("run_attempt") or 1), old["id"]) < (created, int(run.get("run_attempt") or 1), run_id):
                latest[key] = run

    if unverified_pr_association:
        return {"decision": "HOLD_UNVERIFIED_PR_ASSOCIATION", "analysis": None}

    # Only completed failures are eligible. Pending runs for the same
    # workflow/head are never silently ignored.
    failed = sorted(
        (r for r in latest.values() if r.get("status") == "completed" and r.get("conclusion") == "failure"),
        key=lambda r: (_timestamp(r["created_at"]), r["id"]), reverse=True,
    )
    if not failed:
        if any(r.get("status") != "completed" for r in latest.values()):
            return {"decision": "HOLD_PENDING_CURRENT_HEAD_RUN", "analysis": None}
        return {"decision": "NO_CURRENT_OPEN_PR_FAILURE", "analysis": None}

    candidate = failed[0]
    run_id = candidate["id"]
    if not jobs_inventory_complete.get(run_id, False) or run_id not in jobs_by_run_id:
        return {"decision": "HOLD_INCOMPLETE_JOB_INVENTORY", "analysis": None, "source_run_id": run_id}
    analysis = analyze_completed_failure(repository, candidate, jobs_by_run_id[run_id])
    if analysis is None:
        return {"decision": "HOLD_NO_VERIFIED_FAILED_JOB", "analysis": None, "source_run_id": run_id}
    return {"decision": "ISSUE_DRAFT_ELIGIBLE", "analysis": analysis}
