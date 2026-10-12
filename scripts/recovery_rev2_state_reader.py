"""Read-only Rev.2 state projection. No GitHub writes or execution authority.

Only independently attested, canonical events are accepted. Legacy event formats
remain UNKNOWN until an explicit migration adapter has verified provenance.
"""
from __future__ import annotations
from collections.abc import Mapping, Sequence

TERMINAL = {"DONE", "MERGED"}
IN_PROGRESS = {"PR_OPEN", "RUNNING", "ACKED", "DISPATCHED"}
KNOWN = {"READY", "DISPATCHED", "ACKED", "RUNNING", "PR_OPEN", "MERGED", "DONE", "BLOCKED", "EXPIRED"}
RANK = {"READY": 0, "DISPATCHED": 1, "ACKED": 2, "RUNNING": 3, "PR_OPEN": 4, "MERGED": 5, "DONE": 6}

def project_state(*, work_id: str, events: Sequence[Mapping], evidence_verified: bool) -> dict:
    """Return fail-closed state; never infer an ACK or merge from expiry alone.

    Events MUST be ordered and independently authenticated upstream. This function
    does not authenticate comments, run IDs, PR IDs, or merge SHAs.
    """
    if work_id == "issue:79":
        return {"status": "BLOCKED", "reason": "PROTECTED_ISSUE_79", "dispatch_allowed": False}
    if not isinstance(work_id, str) or not work_id.startswith("issue:") or not work_id[6:].isdigit() or int(work_id[6:]) <= 0:
        return {"status": "UNKNOWN", "reason": "INVALID_WORK_ID", "dispatch_allowed": False}
    if evidence_verified is not True or not isinstance(events, (list, tuple)):
        return {"status": "UNKNOWN", "reason": "PROVENANCE_UNVERIFIED", "dispatch_allowed": False}
    if not events:
        return {"status": "READY", "dispatch_allowed": False, "reason": "PREFLIGHT_REQUIRED"}
    seen = set()
    previous_rank = -1
    attempts = set()
    last = None
    for event in events:
        if not isinstance(event, Mapping) or event.get("work_id") != work_id:
            return {"status": "UNKNOWN", "reason": "IDENTITY_MISMATCH", "dispatch_allowed": False}
        status = event.get("status")
        if status not in KNOWN or status == "READY":
            return {"status": "UNKNOWN", "reason": "UNKNOWN_EVENT", "dispatch_allowed": False}
        comment_id = event.get("comment_id")
        if type(comment_id) is not int or comment_id <= 0 or comment_id in seen:
            return {"status": "UNKNOWN", "reason": "INVALID_COMMENT_ID", "dispatch_allowed": False}
        seen.add(comment_id)
        attempt = event.get("attempt")
        if type(attempt) is not int or not 1 <= attempt <= 4:
            return {"status": "UNKNOWN", "reason": "INVALID_ATTEMPT", "dispatch_allowed": False}
        attempts.add(attempt)
        if status in {"DISPATCHED", "ACKED", "RUNNING", "PR_OPEN", "MERGED", "DONE"}:
            if not isinstance(event.get("lease_id"), str) or not event["lease_id"].startswith("lease-"):
                return {"status": "UNKNOWN", "reason": "MISSING_LEASE", "dispatch_allowed": False}
        if status == "PR_OPEN" and (type(event.get("pr_number")) is not int or event["pr_number"] <= 0):
            return {"status": "UNKNOWN", "reason": "MISSING_PR", "dispatch_allowed": False}
        if status == "MERGED" and (type(event.get("pr_number")) is not int or not isinstance(event.get("merge_sha"), str) or len(event["merge_sha"]) != 40):
            return {"status": "UNKNOWN", "reason": "MISSING_MERGE_EVIDENCE", "dispatch_allowed": False}
        if status == "DONE" and event.get("dod_verified") is not True:
            return {"status": "UNKNOWN", "reason": "DOD_UNVERIFIED", "dispatch_allowed": False}
        if status in RANK:
            rank = RANK[status]
            if rank < previous_rank:
                return {"status": "UNKNOWN", "reason": "STATE_REGRESSION", "dispatch_allowed": False}
            previous_rank = rank
        elif last in TERMINAL or last in {"ACKED", "RUNNING", "PR_OPEN"}:
            return {"status": "UNKNOWN", "reason": "CONTRADICTORY_RECOVERY", "dispatch_allowed": False}
        last = status
    if max(attempts) > len(attempts) or sorted(attempts) != list(range(1, max(attempts) + 1)):
        return {"status": "UNKNOWN", "reason": "ATTEMPT_GAP", "dispatch_allowed": False}
    if last == "EXPIRED" and max(attempts) == 4:
        return {"status": "BLOCKED", "reason": "RETRY_LIMIT", "dispatch_allowed": False}
    return {"status": last, "dispatch_allowed": False, "reason": "RECOVERY_AUTHORITY_REQUIRED" if last in {"EXPIRED", "BLOCKED"} else "STATE_OBSERVED"}
