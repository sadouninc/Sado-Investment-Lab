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


def attest_legacy_sora_lease(comment: Mapping, *, work_id: str,
                             actions_run: Mapping, expected_repository: str) -> dict:
    """Correlate legacy evidence with independently fetched GitHub metadata.

    This is evidence attestation only, NOT Rev.2 event migration or permission
    to dispatch. Callers must still verify PR/ACK/terminal and owner state.
    """
    inspection = inspect_legacy_sora_lease(comment, work_id=work_id)
    if inspection.get("status") != "UNVERIFIED":
        return inspection
    if not isinstance(actions_run, Mapping) or not isinstance(expected_repository, str):
        return {"status": "UNKNOWN", "reason": "RUN_METADATA_MISSING", "dispatch_allowed": False}
    author = comment.get("user")
    if not isinstance(author, Mapping) or author.get("login") != "github-actions[bot]":
        return {"status": "UNKNOWN", "reason": "UNTRUSTED_COMMENT_AUTHOR", "dispatch_allowed": False}
    repo = actions_run.get("repository")
    if not isinstance(repo, Mapping) or repo.get("full_name") != expected_repository:
        return {"status": "UNKNOWN", "reason": "REPOSITORY_MISMATCH", "dispatch_allowed": False}
    if (actions_run.get("id") != inspection["writer_run_id"] or
        actions_run.get("event") not in {"schedule", "workflow_dispatch"} or
        actions_run.get("status") != "completed" or
        actions_run.get("conclusion") != "success" or
        actions_run.get("name") != "Sora Recovery Control Plane"):
        return {"status": "UNKNOWN", "reason": "RUN_ATTESTATION_MISMATCH", "dispatch_allowed": False}
    # GitHub timestamp consistency is necessary but not sufficient.
    # The comment cannot precede the run or appear after its completion.
    from datetime import datetime, timezone

    def timestamp(value):
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
        except ValueError:
            return None

    created = timestamp(comment.get("created_at"))
    started = timestamp(actions_run.get("run_started_at"))
    updated = timestamp(actions_run.get("updated_at"))
    if created is None or started is None or updated is None or not (started <= created <= updated):
        return {"status": "UNKNOWN", "reason": "COMMENT_RUN_TIME_MISMATCH", "dispatch_allowed": False}
    # A successful workflow run alone does not prove that its specific comment
    # was written by that run. Preserve the distinction in durable evidence.
    return {"status": "REPORTED_UNVERIFIED", "reason": "COMMENT_TO_RUN_LINK_NOT_PROVEN",
            "dispatch_allowed": False, "comment_id": inspection["comment_id"],
            "writer_run_id": inspection["writer_run_id"], "work_id": work_id}
