"""#859 read-only SORA recovery lease discovery candidate.

No GitHub writes, no claim/ACK, no mutation authority. A caller MUST independently
attest the referenced workflow run and recheck fresh lease/authority before use.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import re
from typing import Any, Iterable, Mapping

_MARKER = re.compile(
    r"<!-- AUTO_ROUTER_DISPATCH lease_id=(lease-[0-9a-f]{32}) "
    r"executor=SORA target_issue=([1-9][0-9]*) -->"
)
_ALLOWED_SOURCES = {"workflow_dispatch", "scheduled_pull"}
_TRUSTED_AUTHOR = "github-actions[bot]"


def _utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be explicit UTC")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be UTC")
    return parsed


def _result(status: str, **kwargs: Any) -> dict[str, Any]:
    return {"status": status, "write_performed": False, **kwargs}


def discover_sora_pickup(
    *, issue_number: int, comments: Iterable[Mapping[str, Any]], now: datetime
) -> dict[str, Any]:
    """Return a read-only pickup *candidate*, never an execution authorization.

    The candidate remains untrusted until the caller independently fetches and
    validates `writer_run_id` against GitHub Actions, and refreshes issue state.
    """
    if not isinstance(issue_number, int) or isinstance(issue_number, bool) or issue_number <= 0:
        raise ValueError("issue_number must be positive")
    if issue_number == 79:
        return _result("PROTECTED_ISSUE")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    active: list[dict[str, Any]] = []
    expired: list[dict[str, Any]] = []
    invalid = 0
    for comment in comments:
        body = comment.get("body")
        if not isinstance(body, str):
            continue
        lines = body.splitlines()
        if not lines:
            continue
        # Only a first-line exact canonical marker is actionable. Quoted text
        # and historical explanations are not lease events.
        match = _MARKER.fullmatch(lines[0])
        if match is None:
            continue
        lease_id, marker_issue = match.groups()
        if int(marker_issue) != issue_number:
            continue
        try:
            author = (comment.get("user") or {}).get("login")
            comment_id = comment.get("id")
            if author != _TRUSTED_AUTHOR or type(comment_id) is not int or comment_id <= 0:
                raise ValueError("untrusted GitHub comment provenance")
            if len(lines) < 2:
                raise ValueError("missing event")
            event = json.loads(lines[1])
            if not isinstance(event, dict):
                raise ValueError("event must be an object")
            expected = {
                "work_ref": f"issue:{issue_number}",
                "owner_slice": f"issue-{issue_number}",
                "executor": "SORA",
                "canonical_lease_id": lease_id,
                "status": "DISPATCHED",
            }
            if any(event.get(k) != v for k, v in expected.items()):
                raise ValueError("lease/event identity mismatch")
            if event.get("source") not in _ALLOWED_SOURCES:
                raise ValueError("invalid source")
            run_id = event.get("writer_run_id")
            if type(run_id) is not int or run_id <= 0:
                raise ValueError("missing writer run attribution")
            assigned = _utc(event.get("assigned_at"))
            expiry = _utc(event.get("lease_expires_at"))
            # Writer computes assigned/expires in separate date calls; allow small clock skew.
            if assigned > now or expiry <= assigned or expiry - assigned > timedelta(minutes=92):
                raise ValueError("invalid lease window")
            candidate = {
                "lease_id": lease_id,
                "target_issue": issue_number,
                "comment_id": comment_id,
                "writer_run_id": run_id,
                "assigned_at": assigned.isoformat(),
                "lease_expires_at": expiry.isoformat(),
                "source": event["source"],
            }
            (active if expiry > now else expired).append(candidate)
        except (ValueError, TypeError, json.JSONDecodeError, AttributeError):
            invalid += 1
    if invalid:
        return _result("EVIDENCE_UNVERIFIED", invalid_count=invalid)
    if len(active) > 1:
        return _result("AMBIGUOUS_ACTIVE_LEASE", active_count=len(active))
    if active:
        return _result(
            "PICKUP_CANDIDATE", candidate=active[0],
            required_next_gate="VERIFY_WRITER_RUN_AND_FRESH_AUTHORITY",
        )
    if expired:
        return _result("LEASE_EXPIRED", last_expiry=max(x["lease_expires_at"] for x in expired))
    return _result("NO_LEASE")


def verify_sora_pickup_provenance(
    *, candidate: Mapping[str, Any], writer_run: Mapping[str, Any],
    issue: Mapping[str, Any], repository_full_name: str, now: datetime,
) -> dict[str, Any]:
    """Read-only metadata consistency check; NEVER grants mutation authority.

    Caller must fetch `writer_run` and `issue` independently from GitHub.
    Run metadata alone cannot prove the run created the comment. Independently
    attest comment-to-run binding and recheck all gates before execution.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    if candidate.get("target_issue") == 79:
        return _result("PROTECTED_ISSUE", execution_authorized=False)
    try:
        issue_number = candidate["target_issue"]
        if type(issue_number) is not int or issue_number <= 0:
            raise ValueError("invalid issue")
        lease_id = candidate["lease_id"]
        if not isinstance(lease_id, str) or not re.fullmatch(r"lease-[0-9a-f]{32}", lease_id):
            raise ValueError("invalid lease")
        run_id = candidate["writer_run_id"]
        if type(run_id) is not int or run_id <= 0 or writer_run.get("id") != run_id:
            raise ValueError("writer run mismatch")
        if type(candidate.get("comment_id")) is not int or candidate["comment_id"] <= 0:
            raise ValueError("comment id missing")
        source = candidate.get("source")
        event = {"scheduled_pull": "schedule", "workflow_dispatch": "workflow_dispatch"}.get(source)
        if not event or writer_run.get("event") != event:
            raise ValueError("event mismatch")
        if (writer_run.get("status") != "completed" or
                writer_run.get("conclusion") != "success" or
                writer_run.get("head_branch") != "main"):
            raise ValueError("writer run not successful on main")
        if writer_run.get("path") != ".github/workflows/sora-recovery-control-plane.yml@main":
            raise ValueError("wrong workflow")
        if (writer_run.get("repository") or {}).get("full_name") != repository_full_name:
            raise ValueError("wrong repository")
        assigned = datetime.fromisoformat(candidate["assigned_at"])
        expires = datetime.fromisoformat(candidate["lease_expires_at"])
        created = _utc(writer_run.get("created_at"))
        if (assigned.tzinfo is None or expires.tzinfo is None or
                assigned.utcoffset() != timedelta(0) or
                expires.utcoffset() != timedelta(0) or
                not created <= assigned <= now or
                expires <= assigned or
                expires - assigned > timedelta(minutes=92)):
            raise ValueError("invalid time window")
        if expires <= now:
            return _result("LEASE_EXPIRED", execution_authorized=False)
        if (issue.get("number") != issue_number or issue.get("state") != "open" or
                issue.get("pull_request") is not None):
            raise ValueError("target issue not open")
        body = issue.get("body")
        if not isinstance(body, str) or not all(re.search(pattern, body, re.M) for pattern in (
            r"^## Recovery Work Contract[^\n]*$",
            r"^\*\*Priority:\*\* P[01]\b",
            r"^\*\*Flow Authority:\*\* .*ナギ",
            r"^\*\*Recovery Engineer:\*\* .*ソラ",
        )):
            raise ValueError("recovery contract mismatch")
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return _result("EVIDENCE_UNVERIFIED", execution_authorized=False)
    return _result(
        "RUN_METADATA_CONSISTENT_READ_ONLY", execution_authorized=False,
        lease_id=lease_id, writer_run_id=run_id,
        required_next_gate="ATTEST_COMMENT_RUN_BINDING_AND_FRESH_AUTHORITY",
    )
