"""Read-only owner approval inspection. No automatic dispatch authority.

The caller must independently obtain the GitHub comment and determine the
authorized human owner's login from a trusted, owner-controlled source.
Repository collaborators and bot authors are NOT implicitly owners.
"""
from __future__ import annotations

import re
from collections.abc import Mapping

_MARKER = re.compile(
    r"\A<!-- SORA_RECOVERY_OWNER_APPROVAL "
    r"issue=(?P<issue>[1-9][0-9]*) "
    r"lease=(?P<lease>lease-[0-9a-f]{32}) "
    r"scope=sora_recovery_dispatch decision=APPROVED -->\Z"
)


def inspect_owner_approval(*, comment: Mapping, issue_number: int,
                           lease_id: str, expected_owner_login: str,
                           independently_verified_author: bool) -> dict:
    def hold(reason: str) -> dict:
        return {"status": "UNKNOWN", "reason": reason, "verified": False}
    if type(issue_number) is not int or issue_number <= 0 or issue_number == 79:
        return hold("INVALID_OR_PROTECTED_ISSUE")
    if not isinstance(comment, Mapping) or not isinstance(expected_owner_login, str):
        return hold("INVALID_APPROVAL_INPUT")
    if (not expected_owner_login or expected_owner_login.endswith("[bot]")
            or independently_verified_author is not True):
        return hold("OWNER_IDENTITY_NOT_ATTESTED")
    author = comment.get("user")
    if (not isinstance(author, Mapping)
            or author.get("login") != expected_owner_login
            or type(comment.get("id")) is not int or comment["id"] <= 0):
        return hold("OWNER_AUTHOR_MISMATCH")
    issue_url = comment.get("issue_url")
    if (not isinstance(issue_url, str)
            or not issue_url.endswith(f"/issues/{issue_number}")):
        return hold("OWNER_APPROVAL_ISSUE_MISMATCH")
    body = comment.get("body")
    marker = _MARKER.fullmatch(body.strip()) if isinstance(body, str) else None
    if (marker is None or marker["issue"] != str(issue_number)
            or marker["lease"] != lease_id):
        return hold("OWNER_APPROVAL_SCOPE_OR_LEASE_MISMATCH")
    return {"status": "APPROVED", "issue_number": issue_number,
            "scope": "sora_recovery_dispatch", "lease_id": lease_id,
            "owner_comment_id": comment["id"], "verified": True}
