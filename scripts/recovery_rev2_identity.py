"""Rev.2 pure lease identity / ACK schema validators; no GitHub mutations.

Legacy lease IDs are NOT interchangeable with Rev.2 IDs. Provenance, event
ordering and PR/merge binding must be independently verified by a common reader.
"""
from __future__ import annotations
from datetime import datetime
from hashlib import sha256
import re

def lease_id(work_id: str, dispatch_run_id: int, attempt: int) -> str:
    if not isinstance(work_id, str) or not re.fullmatch(r"issue:[1-9][0-9]*", work_id) or work_id == "issue:79":
        raise ValueError("invalid/protected work_id")
    if type(dispatch_run_id) is not int or dispatch_run_id <= 0:
        raise ValueError("invalid dispatch_run_id")
    if type(attempt) is not int or not 1 <= attempt <= 4:
        raise ValueError("attempt must be initial + at most 3 retries")
    return "lease-" + sha256(f"recovery-rev2|{work_id}|{dispatch_run_id}|{attempt}".encode()).hexdigest()[:32]

def ack_schema(ack: dict, *, work_id: str, lease: str, executor: str) -> dict:
    """Validate structure only, NEVER claim trusted ACK or authorize dispatch."""
    if not isinstance(ack, dict) or any(k not in ack for k in ("lease_id", "work_id", "executor", "run_id", "timestamp", "status")):
        return {"status": "UNKNOWN", "reason": "MISSING_FIELDS"}
    if work_id == "issue:79" or not re.fullmatch(r"lease-[0-9a-f]{32}", lease):
        return {"status": "UNKNOWN", "reason": "INVALID_IDENTITY"}
    if (ack["lease_id"], ack["work_id"], ack["executor"]) != (lease, work_id, executor):
        return {"status": "UNKNOWN", "reason": "IDENTITY_MISMATCH"}
    if type(ack["run_id"]) is not int or ack["run_id"] <= 0 or ack["status"] != "ACKNOWLEDGED":
        return {"status": "UNKNOWN", "reason": "INVALID_ACK"}
    try:
        stamp = ack["timestamp"]
        if not isinstance(stamp, str) or not stamp.endswith("Z"):
            raise ValueError("UTC Z required")
        parsed = datetime.fromisoformat(stamp[:-1] + "+00:00")
        if parsed.utcoffset().total_seconds() != 0:
            raise ValueError("UTC required")
    except (ValueError, TypeError, AttributeError, OverflowError):
        return {"status": "UNKNOWN", "reason": "INVALID_TIMESTAMP"}
    return {"status": "ACK_SCHEMA_VALID_UNVERIFIED", "provenance_verified": False}
