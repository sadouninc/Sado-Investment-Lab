"""Read-only recovery pickup inspection over independently fetched GitHub snapshots.

This CLI is deliberately NOT a dispatcher, ACK writer, or authorization gate.
No GitHub network calls or mutations occur. The caller must supply snapshots
retrieved from the GitHub API; these inputs are never sufficient to authorize
execution or establish comment↔writer-run binding.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
from pathlib import Path
import sys
from typing import Any

from scripts.sora_recovery_pickup import discover_sora_pickup, verify_sora_pickup_provenance


def _json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def inspect_snapshot(*, issue: dict, comments: list, writer_run: dict | None,
                     repository: str, now: datetime) -> dict:
    """Return an informational verdict, never an execution authorization."""
    if not isinstance(issue, dict) or not isinstance(comments, list):
        return {"status": "EVIDENCE_UNVERIFIED", "execution_authorized": False}
    number = issue.get("number")
    if type(number) is not int or number <= 0:
        return {"status": "EVIDENCE_UNVERIFIED", "execution_authorized": False}
    if number == 79:
        return {"status": "PROTECTED_ISSUE", "execution_authorized": False}
    # An empty or stale comment snapshot must not hide a closed/non-contract
    # target. Check the target before interpreting absence of a lease.
    body = issue.get("body")
    required_contract = (
        r"^## Recovery Work Contract[^\n]*$",
        r"^\*\*Priority:\*\* P[01]\b",
        r"^\*\*Flow Authority:\*\* .*ナギ",
        r"^\*\*Recovery Engineer:\*\* .*ソラ",
    )
    if issue.get("state") != "open" or issue.get("pull_request") is not None:
        return {"status": "TARGET_NOT_OPEN", "execution_authorized": False,
                "write_performed": False}
    if not isinstance(body, str) or not all(re.search(pattern, body, re.M)
                                             for pattern in required_contract):
        return {"status": "RECOVERY_CONTRACT_UNVERIFIED", "execution_authorized": False,
                "write_performed": False}
    if not all(isinstance(x, dict) for x in comments):
        return {"status": "EVIDENCE_UNVERIFIED", "execution_authorized": False,
                "write_performed": False}
    # Issue metadata reports the canonical number of issue comments. Without
    # an all-page snapshot, an older active lease can be missed and a new
    # pickup/reroute decision can be based on incomplete evidence. The caller
    # must refetch both snapshots if concurrent comments cause a count drift.
    declared_count = issue.get("comments")
    if type(declared_count) is not int or declared_count < 0:
        return {"status": "COMMENT_SNAPSHOT_UNVERIFIED", "execution_authorized": False,
                "write_performed": False, "reason": "COMMENT_COUNT_MISSING"}
    if len(comments) != declared_count:
        return {"status": "COMMENT_SNAPSHOT_UNVERIFIED", "execution_authorized": False,
                "write_performed": False, "reason": "COMMENT_COUNT_MISMATCH",
                "expected": declared_count, "observed": len(comments)}
    discovery = discover_sora_pickup(issue_number=number, comments=comments, now=now)
    if discovery["status"] != "PICKUP_CANDIDATE":
        return {"status": discovery["status"], "execution_authorized": False,
                "write_performed": False}
    if not isinstance(writer_run, dict):
        return {"status": "WRITER_RUN_EVIDENCE_MISSING", "execution_authorized": False,
                "write_performed": False}
    result = verify_sora_pickup_provenance(candidate=discovery["candidate"],
                                           writer_run=writer_run, issue=issue,
                                           repository_full_name=repository, now=now)
    return {"status": result["status"], "execution_authorized": False,
            "write_performed": False,
            "required_next_gate": result.get("required_next_gate",
                                               "VERIFY_FRESH_AUTHORITY_AND_DURABLE_BINDING")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue", required=True, help="GitHub issue JSON snapshot")
    parser.add_argument("--comments", required=True, help="all-page issue comments JSON array")
    parser.add_argument("--writer-run", help="independently fetched GitHub Actions run JSON")
    parser.add_argument("--repository", required=True, help="exact owner/repo")
    parser.add_argument("--now", help="ISO 8601 UTC clock (defaults to current UTC)")
    args = parser.parse_args(argv)
    try:
        now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now(timezone.utc)
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone aware")
        result = inspect_snapshot(issue=_json(args.issue), comments=_json(args.comments),
                                  writer_run=_json(args.writer_run) if args.writer_run else None,
                                  repository=args.repository, now=now)
    except (ValueError, TypeError, OSError, json.JSONDecodeError, KeyError):
        result = {"status": "EVIDENCE_UNVERIFIED", "execution_authorized": False,
                  "write_performed": False}
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0 if result["status"] == "RUN_METADATA_CONSISTENT_READ_ONLY" else 2


if __name__ == "__main__":
    sys.exit(main())
