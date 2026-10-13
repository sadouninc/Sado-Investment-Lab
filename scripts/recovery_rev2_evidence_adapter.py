"""Read-only Rev.2 event adapter; authentication is the caller's responsibility."""
from __future__ import annotations
import json
from collections.abc import Mapping

def canonical_event(comment: Mapping, *, work_id: str, trusted_comment_ids: set[int]) -> dict:
    """Only parse canonical JSON from independently attested comment IDs."""
    if work_id == "issue:79":
        return {"status": "BLOCKED", "reason": "PROTECTED_ISSUE_79"}
    if not isinstance(comment, Mapping) or not isinstance(trusted_comment_ids, set):
        return {"status": "UNKNOWN", "reason": "INVALID_INPUT"}
    cid = comment.get("id")
    if type(cid) is not int or cid <= 0 or cid not in trusted_comment_ids:
        return {"status": "UNKNOWN", "reason": "COMMENT_NOT_ATTESTED"}
    body = comment.get("body")
    if not isinstance(body, str):
        return {"status": "UNKNOWN", "reason": "INVALID_BODY"}
    try:
        event = json.loads(body)
    except (ValueError, TypeError):
        return {"status": "UNKNOWN", "reason": "LEGACY_OR_INVALID_JSON"}
    if not isinstance(event, dict) or event.get("schema_version") != 2 or event.get("work_id") != work_id:
        return {"status": "UNKNOWN", "reason": "SCHEMA_OR_WORK_MISMATCH"}
    if "comment_id" in event and event["comment_id"] != cid:
        return {"status": "UNKNOWN", "reason": "COMMENT_ID_CONFLICT"}
    return {**event, "comment_id": cid}


def inspect_legacy_sora_lease(comment: Mapping, *, work_id: str) -> dict:
    """Inspect a legacy marker + JSON comment; NEVER attest it or authorize dispatch.

    Legacy lease events do not carry the Rev.2 schema/ACK provenance. A caller
    must independently verify GitHub comment author, Actions run, issue identity
    and lease lineage before any trusted migration or state projection.
    """
    import re
    if work_id == "issue:79":
        return {"status": "BLOCKED", "reason": "PROTECTED_ISSUE_79", "dispatch_allowed": False}
    if not isinstance(comment, Mapping) or not re.fullmatch(r"issue:[1-9][0-9]*", work_id):
        return {"status": "UNKNOWN", "reason": "INVALID_INPUT", "dispatch_allowed": False}
    body = comment.get("body")
    cid = comment.get("id")
    if not isinstance(body, str) or type(cid) is not int or cid <= 0:
        return {"status": "UNKNOWN", "reason": "INVALID_COMMENT", "dispatch_allowed": False}
    lines = body.splitlines()
    markers = [line for line in lines if "AUTO_ROUTER_DISPATCH" in line]
    if len(markers) != 1:
        return {"status": "UNKNOWN", "reason": "MISSING_OR_AMBIGUOUS_MARKER", "dispatch_allowed": False}
    marker = re.fullmatch(
        r"<!-- AUTO_ROUTER_DISPATCH lease_id=(lease-[0-9a-f]{32}) executor=SORA target_issue=([1-9][0-9]*) -->",
        markers[0],
    )
    if not marker or "issue:" + marker.group(2) != work_id:
        return {"status": "UNKNOWN", "reason": "MARKER_OR_WORK_MISMATCH", "dispatch_allowed": False}
    objects = []
    for line in lines:
        if line.lstrip().startswith("{"):
            try:
                objects.append(json.loads(line))
            except ValueError:
                return {"status": "UNKNOWN", "reason": "INVALID_JSON", "dispatch_allowed": False}
    if len(objects) != 1 or not isinstance(objects[0], dict):
        return {"status": "UNKNOWN", "reason": "AMBIGUOUS_EVENT", "dispatch_allowed": False}
    event = objects[0]
    if (event.get("work_ref") != work_id or
        event.get("canonical_lease_id") != marker.group(1) or
        event.get("executor") != "SORA" or
        event.get("status") != "DISPATCHED" or
        type(event.get("writer_run_id")) is not int or event["writer_run_id"] <= 0):
        return {"status": "UNKNOWN", "reason": "EVENT_IDENTITY_MISMATCH", "dispatch_allowed": False}
    return {"status": "UNVERIFIED", "reason": "LEGACY_REQUIRES_EXTERNAL_ATTESTATION",
            "dispatch_allowed": False, "comment_id": cid,
            "writer_run_id": event["writer_run_id"],
            "lease_id": marker.group(1), "work_id": work_id}
