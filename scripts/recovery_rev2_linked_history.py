"""Build read-only Rev.2 observations from independently linked legacy dispatches.

Only trust linkages already validated against run-owned Actions artifacts.
Missing, conflicting, or non-dispatch events are never silently discarded.
This migration does not authorize a retry or prove executor termination.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
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
    run_id = item.get("writer_run_id")
    if type(cid) is not int or cid <= 0:
        return unknown("INVALID_LINKED_COMMENT_ID")
    # Correlation to a specific, independently authenticated Actions run is
    # mandatory. Do not promote a comment-only dispatch to canonical history.
    if type(run_id) is not int or run_id <= 0:
        return unknown("MISSING_LINKED_WRITER_RUN")
    if not isinstance(lease, str) or re.fullmatch(r"lease-[0-9a-f]{32}", lease) is None:
        return unknown("INVALID_LINKED_LEASE")
    event = {"work_id": work_id, "status": "DISPATCHED",
             "comment_id": cid, "attempt": 1, "lease_id": lease}
    return project_state(work_id=work_id, events=[event], evidence_verified=True)


def matches_complete_dispatch_evidence(*, observed: Sequence[Mapping],
                                       authenticated: Sequence[Mapping],
                                       complete: bool) -> bool:
    """Stop reconciliation must use the exact run-owned artifact inventory."""
    if complete is not True or not isinstance(observed, (list, tuple)) or not isinstance(authenticated, (list, tuple)):
        return False
    if not observed or len(observed) != len(authenticated) or len(observed) > 4:
        return False
    def identity(item, trusted):
        if not isinstance(item, Mapping):
            return None
        lease, run = item.get("lease_id"), item.get("writer_run_id")
        if (not isinstance(lease, str) or re.fullmatch(r"lease-[0-9a-f]{32}", lease) is None
                or type(run) is not int or run <= 0
                or trusted and (item.get("status") != "ATTESTED_LINKAGE"
                                or item.get("dispatch_allowed") is not False)):
            return None
        return lease, run
    seen = [identity(i, False) for i in observed]
    verified = [identity(i, True) for i in authenticated]
    return (all(item is not None for item in seen + verified)
            and len(set(seen)) == len(seen)
            and len(set(verified)) == len(verified)
            and set(seen) == set(verified))


def project_authenticated_artifact_inventory(*, work_id: str,
                                              observed: Sequence[Mapping],
                                              authenticated: Sequence[Mapping],
                                              complete: bool) -> dict:
    """Bridge independently fetched inventory to the read-only Reader.

    The caller must independently authenticate each run-owned artifact via
    GitHub Actions API and supply verify_run_owned_dispatch_linkage results.
    A missing or partially matched inventory is UNKNOWN, never READY.
    No event is upgraded to verified by this function.
    """
    def unknown(reason: str) -> dict:
        return {"status": "UNKNOWN", "reason": reason, "dispatch_allowed": False}

    if work_id == "issue:79":
        return {"status": "BLOCKED", "reason": "PROTECTED_ISSUE_79",
                "dispatch_allowed": False}
    if complete is not True or not isinstance(observed, (list, tuple)) or not isinstance(authenticated, (list, tuple)):
        return unknown("INCOMPLETE_ARTIFACT_INVENTORY")
    if not observed or not authenticated:
        # An empty artifact list is not proof that no dispatch occurred.
        return unknown("NO_ATTESTED_ARTIFACT_INVENTORY")
    if not matches_complete_dispatch_evidence(
            observed=observed, authenticated=authenticated, complete=True):
        return unknown("ARTIFACT_INVENTORY_MISMATCH")
    # Bind each observed comment to its run-owned artifact, not just lease/run.
    observed_ids = [item.get("comment_id") for item in observed]
    authenticated_ids = [item.get("comment_id") for item in authenticated]
    if (any(type(cid) is not int or cid <= 0 for cid in observed_ids + authenticated_ids)
            or len(set(observed_ids)) != len(observed_ids)
            or set(observed_ids) != set(authenticated_ids)):
        return unknown("ARTIFACT_COMMENT_ID_MISMATCH")
    if {(item["comment_id"], item["lease_id"], item["writer_run_id"]) for item in observed} != {
            (item["comment_id"], item["lease_id"], item["writer_run_id"]) for item in authenticated}:
        return unknown("ARTIFACT_COMMENT_LINKAGE_MISMATCH")
    # Each writer run is allowed to substantiate one dispatch only. A single
    # run reused across multiple leases is ambiguous even with distinct IDs.
    if len({item["writer_run_id"] for item in authenticated}) != len(authenticated):
        return unknown("REUSED_WRITER_RUN_ID")
    if len({item["lease_id"] for item in authenticated}) != len(authenticated):
        return unknown("REUSED_LEASE_ID")
    if any(item.get("work_id") != work_id for item in authenticated):
        return unknown("ARTIFACT_WORK_ID_MISMATCH")
    return project_linked_dispatch_history(
        work_id=work_id, linked_dispatches=authenticated,
        complete_history=True)
