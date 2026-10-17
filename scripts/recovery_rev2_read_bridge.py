"""Read-only Rev.2 bridge from attested comments to state projection.

Attestation MUST be established independently by caller against GitHub API and
Actions run metadata. This module cannot authorize dispatch or merge.
"""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from scripts.recovery_rev2_evidence_adapter import canonical_event
from scripts.recovery_rev2_state_reader import project_state

def project_attested_comments(*, work_id: str, comments: Sequence[Mapping],
                              trusted_comment_ids: set[int],
                              provenance_verified: bool) -> dict:
    if work_id == "issue:79":
        return {"status": "BLOCKED", "reason": "PROTECTED_ISSUE_79", "dispatch_allowed": False}
    if provenance_verified is not True or not isinstance(comments, (list, tuple)):
        return {"status": "UNKNOWN", "reason": "PROVENANCE_UNVERIFIED", "dispatch_allowed": False}
    if not isinstance(trusted_comment_ids, set) or len(comments) != len(trusted_comment_ids):
        return {"status": "UNKNOWN", "reason": "ATTESTATION_SET_MISMATCH", "dispatch_allowed": False}
    # The caller must provide a complete, unique, ordered set of real
    # GitHub comment IDs. A trusted-ID set alone does not prove that the
    # supplied comments form a valid ordered event history.
    ids = [comment.get("id") if isinstance(comment, Mapping) else None
           for comment in comments]
    if (any(type(cid) is not int or cid <= 0 for cid in ids)
            or ids != sorted(ids) or len(ids) != len(set(ids))
            or set(ids) != trusted_comment_ids):
        return {"status": "UNKNOWN", "reason": "INVALID_ATTESTED_COMMENT_INVENTORY",
                "dispatch_allowed": False}
    events = []
    for comment in comments:
        event = canonical_event(comment, work_id=work_id,
                                trusted_comment_ids=trusted_comment_ids)
        if event.get("status") in {"UNKNOWN", "BLOCKED"}:
            return {"status": "UNKNOWN", "reason": event.get("reason", "INVALID_EVENT"),
                    "dispatch_allowed": False}
        events.append(event)
    return project_state(work_id=work_id, events=events, evidence_verified=True)
