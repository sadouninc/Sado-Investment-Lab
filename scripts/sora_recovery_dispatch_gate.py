"""Final, fail-closed decision for SORA recovery dispatch.

This is a pure decision function, not an authorization source. Owner approval
and evidence completeness must be independently verified by the caller.
"""
from __future__ import annotations

from collections.abc import Mapping


def decide_dispatch(*, issue_number: int, candidate: Mapping,
                    projection: Mapping, owner_gate: Mapping,
                    evidence_complete: bool) -> dict:
    def hold(reason: str) -> dict:
        return {"status": "HOLD", "reason": reason, "post_authorized": False}

    if type(issue_number) is not int or issue_number <= 0 or issue_number == 79:
        return hold("INVALID_OR_PROTECTED_ISSUE")
    if not all(isinstance(x, Mapping) for x in (candidate, projection, owner_gate)):
        return hold("INVALID_GATE_INPUT")
    if evidence_complete is not True:
        return hold("INCOMPLETE_EVIDENCE")
    if (candidate.get("status") != "ALLOW_PRELIMINARY"
            or candidate.get("issue_number") != issue_number):
        return hold("CANDIDATE_NOT_ELIGIBLE")
    # The canonical Reader is deliberately read-only: it NEVER emits
    # dispatch_allowed=True. The final gate must assess observed state
    # independently rather than requesting impossible Reader authorization.
    prior = projection.get("prior_dispatch_count")
    attempt = projection.get("attempt")
    status = projection.get("status")
    if (projection.get("dispatch_allowed") is not False
            or projection.get("work_id") != f"issue:{issue_number}"
            or type(prior) is not int or not 0 <= prior <= 4
            or type(attempt) is not int or attempt != prior):
        return hold("INVALID_READER_PROJECTION")
    if prior == 0:
        if status != "READY":
            return hold("READER_NOT_READY")
    else:
        if status != "EXPIRED" or prior >= 4:
            return hold("PRIOR_DISPATCH_NOT_RETRYABLE")
    # Expiry never proves an executor stopped: independently verified stop
    # attestation covering ALL prior attempts is mandatory for any retry.
    if prior:
        stop = projection.get("stop_attestation")
        if (not isinstance(stop, Mapping)
                or stop.get("verified") is not True
                or stop.get("work_id") != f"issue:{issue_number}"
                or stop.get("prior_dispatch_count") != prior
                or stop.get("all_prior_executors_stopped") is not True):
            return hold("PRIOR_DISPATCH_REQUIRES_STOP_ATTESTATION")
    if (owner_gate.get("status") != "APPROVED"
            or owner_gate.get("issue_number") != issue_number
            or owner_gate.get("scope") != "sora_recovery_dispatch"
            or owner_gate.get("verified") is not True
            or not isinstance(owner_gate.get("owner_comment_id"), int)
            or owner_gate["owner_comment_id"] <= 0
            or owner_gate.get("lease_id") != projection.get("next_lease_id")):
        return hold("OWNER_APPROVAL_NOT_VERIFIED")
    return {"status": "ELIGIBLE", "reason": "ALL_INDEPENDENT_GATES_PASSED",
            "post_authorized": True}
