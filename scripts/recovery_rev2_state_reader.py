"""Read-only Rev.2 state projection. No GitHub writes or execution authority.

Inputs must be independently attested, complete and sorted by comment ID.
Unknown or conflicting lease histories remain fail-closed.
"""
from __future__ import annotations
import re
from collections.abc import Mapping, Sequence

TERMINAL = {"DONE", "MERGED"}
KNOWN = {"DISPATCHED", "ACKED", "RUNNING", "PR_OPEN", "MERGED", "DONE", "BLOCKED", "EXPIRED"}
RANK = {"DISPATCHED": 1, "ACKED": 2, "RUNNING": 3, "PR_OPEN": 4, "MERGED": 5, "DONE": 6}
LEASE = re.compile(r"lease-[0-9a-f]{32}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")


def _unknown(reason: str) -> dict:
    return {"status": "UNKNOWN", "reason": reason, "dispatch_allowed": False}


def project_state(*, work_id: str, events: Sequence[Mapping], evidence_verified: bool) -> dict:
    """Project attested history without granting any dispatch/merge authority.

    A new attempt is valid only after a prior DISPATCHED -> EXPIRED sequence.
    Expiry is a state observation, not proof that an executor stopped.
    A caller must separately authenticate events and recheck owner/path/PR state.
    """
    if work_id == "issue:79":
        return {"status": "BLOCKED", "reason": "PROTECTED_ISSUE_79", "dispatch_allowed": False}
    if (not isinstance(work_id, str) or not re.fullmatch(r"issue:[1-9][0-9]*", work_id)):
        return _unknown("INVALID_WORK_ID")
    if evidence_verified is not True or not isinstance(events, (list, tuple)):
        return _unknown("PROVENANCE_UNVERIFIED")
    if not events:
        return {"status": "READY", "dispatch_allowed": False, "reason": "PREFLIGHT_REQUIRED"}

    last = None
    last_comment_id = 0
    attempt_number = 0
    current_lease = None
    used_leases: set[str] = set()
    previous_rank = 0
    for item in events:
        if not isinstance(item, Mapping) or item.get("work_id") != work_id:
            return _unknown("IDENTITY_MISMATCH")
        status = item.get("status")
        if status not in KNOWN:
            return _unknown("UNKNOWN_EVENT")
        cid = item.get("comment_id")
        if type(cid) is not int or cid <= last_comment_id:
            return _unknown("INVALID_OR_OUT_OF_ORDER_COMMENT_ID")
        last_comment_id = cid
        attempt = item.get("attempt")
        if type(attempt) is not int or not 1 <= attempt <= 4:
            return _unknown("INVALID_ATTEMPT")
        lease = item.get("lease_id")
        if not isinstance(lease, str) or not LEASE.fullmatch(lease):
            return _unknown("INVALID_LEASE_ID")
        if status == "PR_OPEN" and (type(item.get("pr_number")) is not int or item["pr_number"] <= 0):
            return _unknown("MISSING_PR")
        if status == "MERGED" and (type(item.get("pr_number")) is not int or item["pr_number"] <= 0 or
                                   not isinstance(item.get("merge_sha"), str) or
                                   not SHA.fullmatch(item["merge_sha"])):
            return _unknown("MISSING_MERGE_EVIDENCE")
        if status == "DONE" and item.get("dod_verified") is not True:
            return _unknown("DOD_UNVERIFIED")

        if attempt > attempt_number:
            if attempt_number == 0:
                if attempt != 1 or status not in {"DISPATCHED", "DONE", "BLOCKED"}:
                    return _unknown("MISSING_INITIAL_DISPATCH")
            elif attempt != attempt_number + 1 or last != "EXPIRED" or status != "DISPATCHED":
                return _unknown("RETRY_WITHOUT_ATTESTED_EXPIRY")
            if lease in used_leases:
                return _unknown("REUSED_LEASE_ID")
            used_leases.add(lease)
            current_lease = lease
            attempt_number = attempt
            previous_rank = 0
        elif attempt < attempt_number:
            return _unknown("ATTEMPT_REGRESSION")
        else:
            if lease != current_lease:
                return _unknown("LEASE_CHANGED_WITHIN_ATTEMPT")
            if status == "DISPATCHED":
                return _unknown("DUPLICATE_DISPATCH_WITHIN_ATTEMPT")
            if last in TERMINAL or last in {"EXPIRED", "BLOCKED"}:
                return _unknown("EVENT_AFTER_TERMINAL_OR_EXPIRY")
            if status == "EXPIRED" and last != "DISPATCHED":
                return _unknown("CONTRADICTORY_EXPIRY")

        if status in RANK:
            rank = RANK[status]
            if rank < previous_rank:
                return _unknown("STATE_REGRESSION")
            previous_rank = rank
        last = status

    if last == "EXPIRED" and attempt_number == 4:
        return {"status": "BLOCKED", "reason": "RETRY_LIMIT", "dispatch_allowed": False}
    return {"status": last, "dispatch_allowed": False,
            "reason": "RECOVERY_AUTHORITY_REQUIRED" if last in {"EXPIRED", "BLOCKED"} else "STATE_OBSERVED"}
