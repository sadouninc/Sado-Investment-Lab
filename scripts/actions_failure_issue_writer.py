"""Issue #873: narrowly scoped GitHub issue POST client, disabled unless explicitly invoked.

The caller must independently fetch a fresh, complete all-state issue inventory
and pass it to the pure validation gate. No workflow calls this client yet.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from scripts.actions_failure_issue_gate import validate_issue_proposal

_REPO = re.compile(r"\A[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


class IssueWriteError(RuntimeError):
    pass


def post_validated_issue(
    repository: str,
    token: str,
    result: Mapping[str, Any],
    existing_issues: list[Mapping[str, Any]],
    *,
    inventory_complete: bool,
    enable_post: bool = False,
) -> dict[str, Any]:
    """POST one issue only after caller-provided fresh inventory and explicit opt-in.

    No labels, assignees, milestone, READY promotion, or dispatch are supported.
    """
    if not enable_post:
        raise IssueWriteError("issue POST disabled by default")
    if not _REPO.fullmatch(repository):
        raise IssueWriteError("invalid repository")
    if not token:
        raise IssueWriteError("missing write token")
    payload = validate_issue_proposal(result, existing_issues, inventory_complete=inventory_complete)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        f"https://api.github.com/repos/{repository}/issues",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sado-issue873-gated-writer",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            if response.status != 201:
                raise IssueWriteError("unexpected issue creation response")
            raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise IssueWriteError("oversized issue response")
            created = json.loads(raw)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise IssueWriteError(f"issue POST failed or uncertain ({type(exc).__name__}); do not retry automatically") from None
    if not isinstance(created, dict) or not isinstance(created.get("number"), int) or created["number"] < 1:
        raise IssueWriteError("unverified issue POST response; do not retry automatically")
    if created["number"] == 79:
        raise IssueWriteError("protected issue number returned; investigate manually")
    return {"number": created["number"], "html_url": created.get("html_url"), "request_id": result["analysis"]["request_id"]}
