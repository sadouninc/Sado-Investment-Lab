"""Build read-only Rev.2 observations from independently linked legacy dispatches.

Only trust linkages already validated against run-owned Actions artifacts.
Missing, conflicting, or non-dispatch events are never silently discarded.
This migration does not authorize a retry or prove executor termination.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from scripts.recovery_rev2_state_reader import project_state


def project_linked_dispatch_history(*, work_id: str,
                                    linked_dispatches: Sequence[Mapping],
                                    complete_history: bool) -> dict:
    def unknown(reason: str) -> dict:
        return {"status": "UNKNOWN", "reason": reason, "dispatch_allowed": False}

    if work_id == "issue:79":
        return {"status": "BLOCKED", "reason": "PROTECTED_ISSUE_79", "dispatch_allowed": False}
    if complete_history is not True or not isinstance(linked_dispatches, (list, tuple)):
        return unknown("INCOMPLETE_LINKED_HISTORY")
    if not linked_dispatches:
        return project_state(work_id=work_id, events=[], evidence_verified=True)
    # Legacy dispatches do not include canonical EXPIRED or ACK events.
    # A second dispatch without independently proven expiry is ambiguous.
    if len(linked_dispatches) != 1:
        return unknown("LEGACY_RETRY_TRANSITIONS_UNVERIFIED")
    item = linked_dispatches[0]
    if not isinstance(item, Mapping) or item.get("status") != "ATTESTED_LINKAGE":
        return unknown("DISPATCH_LINKAGE_UNVERIFIED")
    if item.get("work_id") != work_id or item.get("dispatch_allowed") is not False:
        return unknown("DISPATCH_LINKAGE_IDENTITY_MISMATCH")
    cid, lease = item.get("comment_id"), item.get("lease_id")
    if type(cid) is not int or cid <= 0:
        return unknown("INVALID_LINKED_COMMENT_ID")
    if not isinstance(lease, str):
        return unknown("INVALID_LINKED_LEASE")
    event = {"work_id": work_id, "status": "DISPATCHED",
             "comment_id": cid, "attempt": 1, "lease_id": lease}
    return project_state(work_id=work_id, events=[event], evidence_verified=True)
