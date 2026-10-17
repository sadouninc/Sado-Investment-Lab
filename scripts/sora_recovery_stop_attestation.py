"""Fail-closed stop attestation for bounded SORA recovery retries.

This module does NOT prove an external executor stopped from lease expiry.
A trusted human owner must explicitly attest each previous lease after its
writer run completes. Callers must independently fetch immutable GitHub
comments and Actions runs and validate the owner's identity.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

_STOP = re.compile(
    r"\A<!-- SORA_RECOVERY_EXECUTOR_STOP "
    r"issue=(?P<issue>[1-9][0-9]*) "
    r"lease=(?P<lease>lease-[0-9a-f]{32}) "
    r"writer_run=(?P<run>[1-9][0-9]*) "
    r"decision=ALL_EXECUTORS_STOPPED -->\Z"
)


def verify_stop_attestation(*, issue_number: int, previous_leases: Sequence[Mapping],
                            owner_comments: Sequence[Mapping], actions_runs: Mapping,
                            expected_owner_login: str,
                            owner_identity_verified: bool) -> dict:
    def hold(reason: str) -> dict:
        return {"verified": False, "reason": reason, "all_prior_executors_stopped": False}

    if type(issue_number) is not int or issue_number <= 0 or issue_number == 79:
        return hold("INVALID_OR_PROTECTED_ISSUE")
    if (not isinstance(previous_leases, (list, tuple)) or not previous_leases
            or len(previous_leases) > 4 or not isinstance(owner_comments, (list, tuple))
            or not isinstance(actions_runs, Mapping)):
        return hold("INVALID_STOP_EVIDENCE")
    if (owner_identity_verified is not True or not isinstance(expected_owner_login, str)
            or not expected_owner_login or expected_owner_login.endswith("[bot]")):
        return hold("OWNER_NOT_AUTHENTICATED")
    comment_ids = [c.get("id") if isinstance(c, Mapping) else None
                   for c in owner_comments]
    if (any(type(cid) is not int or cid <= 0 for cid in comment_ids)
            or len(comment_ids) != len(set(comment_ids))):
        return hold("DUPLICATE_OR_INVALID_STOP_COMMENT_IDS")
    seen_leases = set()
    seen_runs = set()
    seen_comments = set()
    for prior in previous_leases:
        if not isinstance(prior, Mapping):
            return hold("INVALID_PRIOR_LEASE")
        lease, run_id = prior.get("lease_id"), prior.get("writer_run_id")
        if (not isinstance(lease, str) or re.fullmatch(r"lease-[0-9a-f]{32}", lease) is None
                or type(run_id) is not int or run_id <= 0
                or lease in seen_leases or run_id in seen_runs):
            return hold("INVALID_PRIOR_LEASE")
        seen_leases.add(lease)
        seen_runs.add(run_id)
        run = actions_runs.get(run_id)
        if (not isinstance(run, Mapping) or run.get("id") != run_id
                or run.get("status") != "completed"
                or run.get("conclusion") not in ("success", "failure", "cancelled")
                or run.get("path") != ".github/workflows/sora-recovery-control-plane.yml"):
            return hold("RUN_NOT_TERMINAL_OR_UNTRUSTED")
        matching = []
        for comment in owner_comments:
            if not isinstance(comment, Mapping):
                return hold("INVALID_STOP_COMMENT")
            cid = comment.get("id")
            if type(cid) is not int or cid <= 0:
                return hold("INVALID_STOP_COMMENT")
            body = comment.get("body")
            marker = _STOP.fullmatch(body.strip()) if isinstance(body, str) else None
            if not marker or marker["issue"] != str(issue_number):
                continue
            if marker["lease"] != lease or int(marker["run"]) != run_id:
                continue
            author = comment.get("user")
            if (not isinstance(author, Mapping) or author.get("login") != expected_owner_login):
                return hold("STOP_COMMENT_AUTHOR_MISMATCH")
            if not isinstance(comment.get("issue_url"), str) or not comment["issue_url"].endswith(f"/issues/{issue_number}"):
                return hold("STOP_COMMENT_ISSUE_MISMATCH")
            matching.append(comment)
        if len(matching) != 1:
            return hold("MISSING_OR_DUPLICATE_STOP_ATTESTATION")
        if matching[0]["id"] in seen_comments:
            return hold("REUSED_STOP_COMMENT")
        seen_comments.add(matching[0]["id"])
    return {"verified": True, "work_id": f"issue:{issue_number}",
            "prior_dispatch_count": len(previous_leases),
            "all_prior_executors_stopped": True,
            "stop_comment_ids": sorted(seen_comments)}
