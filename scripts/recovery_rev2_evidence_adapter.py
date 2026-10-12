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
