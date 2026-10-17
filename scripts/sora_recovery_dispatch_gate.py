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
    if (projection.get("status") != "READY"
            or projection.get("dispatch_allowed") is not True
            or projection.get("work_id") != f"issue:{issue_number}"):
        return hold("READER_NOT_AUTHORIZED")
    # A lease expiry or a terminal label alone is not proof that an
    # executor stopped. Never authorize another attempt from these states.
    prior = projection.get("prior_dispatch_count", 0)
    if type(prior) is not int or prior < 0:
        return hold("INVALID_DISPATCH_HISTORY")
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
            or owner_gate.get("verified") is not True):
        return hold("OWNER_APPROVAL_NOT_VERIFIED")
    return {"status": "ELIGIBLE", "reason": "ALL_INDEPENDENT_GATES_PASSED",
            "post_authorized": True}
