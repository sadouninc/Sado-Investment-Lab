"""Issue #873: fail-closed issue payload gate; network mutations intentionally absent."""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from scripts.actions_failure_analyzer import decide_issue_action

_REQUEST_ID = re.compile(r"\Aactions-failure-[0-9a-f]{20}\Z")
_RUN_URL = re.compile(r"\Ahttps://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/[1-9][0-9]*/job/[1-9][0-9]*\Z")


class IssuePostRejected(ValueError):
    """No issue mutation is permitted with this input."""


def validate_issue_proposal(
    result: Mapping[str, Any],
    existing_issues: list[Mapping[str, Any]],
    *,
    inventory_complete: bool,
) -> dict[str, str]:
    """Return a validated payload only for an observed failure with no duplicates.

    Caller must retrieve a fresh, complete all-state issue inventory immediately
    before using this result. This function never calls GitHub.
    """
    if result.get("decision") != "ISSUE_DRAFT_ELIGIBLE":
        raise IssuePostRejected("collector did not authorize issue draft")
    analysis = result.get("analysis")
    draft = result.get("issue_draft")
    if not isinstance(analysis, Mapping) or not isinstance(draft, Mapping):
        raise IssuePostRejected("missing analysis or draft")
    request_id = analysis.get("request_id")
    if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
        raise IssuePostRejected("invalid request id")
    if analysis.get("evidence_status") != "OBSERVED_FAILURE_ROOT_CAUSE_UNVERIFIED":
        raise IssuePostRejected("unverified failure evidence")
    if not isinstance(analysis.get("reproduction_evidence"), str) or not _RUN_URL.fullmatch(analysis["reproduction_evidence"]):
        raise IssuePostRejected("invalid evidence URL")
    if decide_issue_action(analysis, existing_issues, inventory_complete=inventory_complete) != "ISSUE_DRAFT_ELIGIBLE":
        raise IssuePostRejected("duplicate or incomplete inventory")
    title, body = draft.get("title"), draft.get("body")
    if not isinstance(title, str) or not 1 <= len(title) <= 180:
        raise IssuePostRejected("invalid title")
    if not isinstance(body, str) or not 1 <= len(body) <= 12000:
        raise IssuePostRejected("invalid body")
    if body.count(f"<!-- {request_id} -->") != 1:
        raise IssuePostRejected("missing or duplicate request marker")
    if body.count("- 状態: TRIAGE_REQUIRED。READY_FOR_IMPLEMENTATIONには自動昇格しない。") != 1:
        raise IssuePostRejected("missing canonical triage guard")
    if re.search(r"(?m)^- 状態: (?!TRIAGE_REQUIRED。)", body):
        raise IssuePostRejected("conflicting state declaration")
    return {"title": title, "body": body}
