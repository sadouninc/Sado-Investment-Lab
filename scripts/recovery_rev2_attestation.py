"""Read-only cross-check of Actions and issue-comment metadata.

Inputs must be independently fetched. Matching metadata is never proof of
provenance and cannot authorize dispatch or merge.
"""
from __future__ import annotations
from collections.abc import Mapping
from datetime import datetime
import re

_SHA = re.compile(r"[0-9a-f]{40}\Z")
_WORK = re.compile(r"issue:([1-9][0-9]*)\Z")

def _unknown(reason: str) -> dict:
    return {"status": "UNKNOWN", "reason": reason, "provenance_verified": False, "dispatch_allowed": False}

def _utc(value: object) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
        return True
    except (ValueError, OverflowError):
        return False

def attest_dispatch(*, work_id: str, comment: Mapping, run: Mapping,
                    expected_repository: str, expected_workflow: str) -> dict:
    """Validate consistency only; never elevate to trusted evidence."""
    if work_id == "issue:79":
        return _unknown("PROTECTED_ISSUE_79")
    match = _WORK.fullmatch(work_id) if isinstance(work_id, str) else None
    if not match or not all(isinstance(x, Mapping) for x in (comment, run)):
        return _unknown("INVALID_INPUT")
    if not isinstance(expected_repository, str) or not expected_repository or not isinstance(expected_workflow, str) or not expected_workflow:
        return _unknown("INVALID_EXPECTATIONS")
    body = comment.get("event")
    if not isinstance(body, Mapping):
        return _unknown("MISSING_CANONICAL_EVENT")
    if body.get("schema_version") != 2 or body.get("work_id") != work_id:
        return _unknown("WORK_MISMATCH")
    if type(comment.get("id")) is not int or comment["id"] <= 0:
        return _unknown("COMMENT_ID_MISSING")
    if type(body.get("dispatch_run_id")) is not int or type(run.get("id")) is not int or body["dispatch_run_id"] != run["id"]:
        return _unknown("RUN_ID_MISMATCH")
    if run.get("repository") != expected_repository or run.get("workflow") != expected_workflow:
        return _unknown("RUN_ORIGIN_MISMATCH")
    if run.get("event") not in {"schedule", "workflow_dispatch"} or run.get("conclusion") != "success":
        return _unknown("RUN_NOT_SUCCESSFUL")
    if not isinstance(run.get("head_sha"), str) or not _SHA.fullmatch(run["head_sha"]):
        return _unknown("INVALID_HEAD_SHA")
    if body.get("status") != "DISPATCHED" or type(body.get("attempt")) is not int or not 1 <= body["attempt"] <= 4:
        return _unknown("INVALID_DISPATCH")
    if not _utc(comment.get("created_at")) or not _utc(run.get("created_at")):
        return _unknown("INVALID_TIMESTAMPS")
    if datetime.fromisoformat(comment["created_at"][:-1] + "+00:00") < datetime.fromisoformat(run["created_at"][:-1] + "+00:00"):
        return _unknown("COMMENT_BEFORE_RUN")
    return {"status": "METADATA_CONSISTENT_UNVERIFIED", "provenance_verified": False,
            "dispatch_allowed": False, "comment_id": comment["id"], "run_id": run["id"]}
