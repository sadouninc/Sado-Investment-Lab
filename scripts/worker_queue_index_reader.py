"""Read-only reader / validator for ``WORKER_QUEUE_INDEX_V1`` comments (#738, #1001).

AGENTS.md "Startup: discover assigned work" tells every implementation worker
to locate the latest Flow-Authority-issued ``WORKER_QUEUE_INDEX_V1`` comment on
Issue #738, verify that the comment tail was actually reached, and then select
only its own ``review_prs`` and ``NOW -> NEXT -> RESERVE`` pointers.  This
module codifies that discovery contract so the checks are deterministic and
testable instead of re-done by hand in every run.

What it does (local JSON input only, no network, no GitHub writes):

* parses fenced ``json`` blocks whose ``schema`` is ``worker_queue_index_v1``
  out of a list of comment payloads (``id``, ``created_at``, ``body``,
  optional ``user.login`` / ``user``);
* verifies the tail was reached when the caller supplies the Issue's
  ``comments`` count (and optionally the expected last comment id);
* validates schema, ``authority`` (default allow-list: ``LUNA``), integer
  ``revision``, ``semantics: discovery_only`` and the worker table shape;
* detects duplicate comment ids, duplicate/conflicting revisions, revision
  regressions, an issue listed twice for one worker and an issue listed for
  more than one worker;
* selects exactly the explicitly requested worker identity (never inferred,
  case-sensitive) and returns its pointers.

What it deliberately does NOT do:

* it never authenticates the comment author (every team member may post as
  the same GitHub account), so the report always lists that limit;
* it never fetches or judges live Issue/PR state; ``READY_FOR_IMPLEMENTATION``
  in the index is reported as a pointer, not as a READY determination;
* it grants no permission, Lease, dispatch or merge authority.

Exit codes: ``0`` = ``INDEX_VERIFIED`` (pointers usable for live re-check),
``1`` = ``QUEUE_UNVERIFIED`` (report explains why), ``2`` = unreadable input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA = "worker_queue_index_v1"
MARKER = "WORKER_QUEUE_INDEX_V1"
DEFAULT_AUTHORITIES = ("LUNA",)
QUEUE_LANES = ("now", "next", "reserve")
NOT_READY_STATES = frozenset({"CONDITIONAL", "DEPENDENCY_HOLD", "ASSIGNED_PREFLIGHT"})

STATUS_VERIFIED = "INDEX_VERIFIED"
STATUS_UNVERIFIED = "QUEUE_UNVERIFIED"

EVIDENCE_LIMITS = (
    "comment author identity is not authenticated; the marker and JSON are pointers only",
    "live Issue/PR state, exact head, owner and path conflicts were not fetched or checked",
    "index state values are not READY determinations and grant no permission, Lease or dispatch",
)

_FENCE_RE = re.compile(r"```json[ \t]*\r?\n(.*?)\r?\n[ \t]*```", re.DOTALL)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _author(comment: Mapping[str, Any]) -> str | None:
    user = comment.get("user")
    if isinstance(user, Mapping):
        login = user.get("login")
        return login if isinstance(login, str) else None
    return user if isinstance(user, str) else None


def extract_index_payloads(body: str) -> list[Any]:
    """Return parsed JSON objects from fenced ``json`` blocks declaring the schema.

    Blocks that are not valid JSON but mention the schema name are returned as
    the sentinel string ``"<malformed>"`` so the caller can fail closed.
    """

    found: list[Any] = []
    for match in _FENCE_RE.finditer(body):
        raw = match.group(1)
        if SCHEMA not in raw:
            continue
        try:
            found.append(json.loads(raw))
        except (ValueError, RecursionError):
            found.append("<malformed>")
    return found


def validate_index(payload: Any, allowed_authorities: Iterable[str]) -> list[str]:
    """Return structural problems for one index payload (empty list = valid)."""

    if not isinstance(payload, dict):
        return ["payload is not a JSON object"]
    problems: list[str] = []
    if payload.get("schema") != SCHEMA:
        problems.append(f"schema must be {SCHEMA!r}")
    if payload.get("authority") not in set(allowed_authorities):
        problems.append(f"authority {payload.get('authority')!r} is not an allowed Flow Authority")
    revision = payload.get("revision")
    if not _is_int(revision) or revision < 1:
        problems.append("revision must be a positive integer")
    if payload.get("semantics") != "discovery_only":
        problems.append("semantics must be 'discovery_only'")
    workers = payload.get("workers")
    if not isinstance(workers, dict) or not workers:
        problems.append("workers must be a non-empty object")
        return problems
    for name, table in sorted(workers.items()):
        if not isinstance(table, dict):
            problems.append(f"worker {name}: entry must be an object")
            continue
        review = table.get("review_prs", [])
        if not isinstance(review, list) or not all(_is_int(n) and n > 0 for n in review):
            problems.append(f"worker {name}: review_prs must be a list of positive integers")
        for lane in QUEUE_LANES:
            items = table.get(lane, [])
            if not isinstance(items, list):
                problems.append(f"worker {name}: {lane} must be a list")
                continue
            for pos, item in enumerate(items):
                if not isinstance(item, dict):
                    problems.append(f"worker {name}: {lane}[{pos}] must be an object")
                    continue
                if not _is_int(item.get("issue")) or item["issue"] <= 0:
                    problems.append(f"worker {name}: {lane}[{pos}].issue must be a positive integer")
                if not isinstance(item.get("state"), str) or not item["state"]:
                    problems.append(f"worker {name}: {lane}[{pos}].state must be a non-empty string")
    return problems


def _issue_conflicts(workers: Mapping[str, Any]) -> list[str]:
    conflicts: list[str] = []
    owners: dict[int, set[str]] = {}
    for name, table in sorted(workers.items()):
        seen: set[int] = set()
        for lane in QUEUE_LANES:
            for item in table.get(lane, []):
                issue = item["issue"]
                if issue in seen:
                    conflicts.append(f"worker {name}: issue #{issue} listed more than once")
                seen.add(issue)
                owners.setdefault(issue, set()).add(name)
    for issue, names in sorted(owners.items()):
        if len(names) > 1:
            conflicts.append(f"issue #{issue} assigned to multiple workers: {', '.join(sorted(names))}")
    return conflicts


def build_report(
    comments: list[Mapping[str, Any]],
    *,
    worker: str,
    expected_comment_count: int | None = None,
    expected_last_comment_id: int | None = None,
    expected_broadcast_head: int | None = None,
    allowed_authorities: Iterable[str] = DEFAULT_AUTHORITIES,
) -> dict[str, Any]:
    """Build a deterministic discovery report. Never raises on bad content."""

    authorities = tuple(sorted(set(allowed_authorities)))
    blockers: list[str] = []
    warnings: list[str] = []

    # --- tail verification -------------------------------------------------
    ids = [c.get("id") for c in comments]
    if not all(_is_int(i) for i in ids):
        blockers.append("comment without integer id in input")
    elif len(set(ids)) != len(ids):
        blockers.append("duplicate comment ids in input (pagination overlap?)")
    elif ids != sorted(ids):
        blockers.append("comments are not in ascending id order")

    if expected_comment_count is None:
        blockers.append("tail not verified: expected comment count not supplied")
    elif expected_comment_count != len(comments):
        blockers.append(
            f"tail not verified: fetched {len(comments)} comments, issue reports {expected_comment_count}"
        )
    last_id = ids[-1] if ids and _is_int(ids[-1]) else None
    if expected_last_comment_id is not None and last_id != expected_last_comment_id:
        blockers.append(f"tail not verified: last fetched id {last_id} != expected {expected_last_comment_id}")

    # --- collect candidate index comments ---------------------------------
    candidates: list[dict[str, Any]] = []
    for comment in comments:
        body = comment.get("body")
        if not isinstance(body, str) or MARKER not in body:
            continue
        payloads = extract_index_payloads(body)
        if not payloads:
            warnings.append(f"comment {comment.get('id')}: marker without {SCHEMA} JSON block")
            continue
        if len(payloads) > 1:
            blockers.append(f"comment {comment.get('id')}: multiple index JSON blocks in one comment")
            continue
        payload = payloads[0]
        problems = validate_index(payload, authorities)
        if problems:
            warnings.extend(f"comment {comment.get('id')}: {p}" for p in problems)
            continue
        candidates.append(
            {
                "comment_id": comment.get("id"),
                "created_at": comment.get("created_at"),
                "author": _author(comment),
                "payload": payload,
            }
        )

    selected: dict[str, Any] | None = None
    if not candidates:
        blockers.append("no valid WORKER_QUEUE_INDEX_V1 comment found")
    else:
        by_revision: dict[int, list[dict[str, Any]]] = {}
        for cand in candidates:
            by_revision.setdefault(cand["payload"]["revision"], []).append(cand)
        for rev, group in sorted(by_revision.items()):
            bodies = {json.dumps(c["payload"], sort_keys=True) for c in group}
            if len(bodies) > 1:
                blockers.append(f"revision {rev} published with conflicting content")
        max_rev = max(by_revision)
        last = candidates[-1]
        if last["payload"]["revision"] != max_rev:
            blockers.append(
                f"latest index comment {last['comment_id']} has revision {last['payload']['revision']}"
                f" below earlier revision {max_rev} (regression)"
            )
        selected = by_revision[max_rev][-1]

    # --- worker selection --------------------------------------------------
    queue: dict[str, Any] | None = None
    if selected is not None:
        payload = selected["payload"]
        workers = payload["workers"]
        blockers.extend(_issue_conflicts(workers))
        if expected_broadcast_head is not None and payload.get("broadcast_head") != expected_broadcast_head:
            blockers.append(
                f"index broadcast_head {payload.get('broadcast_head')!r} != verified head {expected_broadcast_head}"
            )
        if worker not in workers:
            blockers.append(f"worker identity {worker!r} not present in index (not inferred)")
        else:
            table = workers[worker]
            queue = {"review_prs": list(table.get("review_prs", []))}
            for lane in QUEUE_LANES:
                queue[lane] = [
                    {
                        "issue": item["issue"],
                        "index_state": item["state"],
                        "pointer_only": True,
                        "not_ready_by_index": item["state"] in NOT_READY_STATES,
                    }
                    for item in table.get(lane, [])
                ]

    status = STATUS_VERIFIED if not blockers else STATUS_UNVERIFIED
    return {
        "schema": "worker_queue_index_report_v1",
        "status": status,
        "worker": worker,
        "allowed_authorities": list(authorities),
        "source": {
            "fetched_comments": len(comments),
            "expected_comment_count": expected_comment_count,
            "last_comment_id": last_id,
            "index_comment_id": selected["comment_id"] if selected else None,
            "index_created_at": selected["created_at"] if selected else None,
            "index_author_login": selected["author"] if selected else None,
            "index_revision": selected["payload"]["revision"] if selected else None,
            "index_broadcast_head": selected["payload"].get("broadcast_head") if selected else None,
        },
        "queue": queue if status == STATUS_VERIFIED else None,
        "blockers": blockers,
        "warnings": warnings,
        "evidence_limits": list(EVIDENCE_LIMITS),
        "grants_authority": False,
        "ready_determination": "not_performed",
    }


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--comments", type=Path, required=True, help="JSON list of comment payloads")
    parser.add_argument("--worker", required=True, help="explicit worker identity, e.g. SORA_SCHEDULED")
    parser.add_argument("--expected-comment-count", type=int)
    parser.add_argument("--expected-last-comment-id", type=int)
    parser.add_argument("--expected-broadcast-head", type=int)
    parser.add_argument("--authority", action="append", dest="authorities")
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        comments = json.loads(args.comments.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        print(f"error: cannot read comments: {exc}", file=sys.stderr)
        return 2
    if not isinstance(comments, list) or not all(isinstance(c, dict) for c in comments):
        print("error: comments must be a JSON list of objects", file=sys.stderr)
        return 2
    report = build_report(
        comments,
        worker=args.worker,
        expected_comment_count=args.expected_comment_count,
        expected_last_comment_id=args.expected_last_comment_id,
        expected_broadcast_head=args.expected_broadcast_head,
        allowed_authorities=args.authorities or DEFAULT_AUTHORITIES,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(text)
    if args.output is not None:
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0 if report["status"] == STATUS_VERIFIED else 1


if __name__ == "__main__":
    raise SystemExit(main())
