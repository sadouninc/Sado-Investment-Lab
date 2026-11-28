"""Review wait and revision turnaround intervals from a PR timeline (#1000, #479).

担当: ♦️ソラ

Independent helper (not yet wired into the existing KPI collectors
``build_productivity_baseline.py`` / ``telemetry_collector.py``). From a
normalized PR timeline it computes, per cycle:

* ``ready_to_review``       ready_for_review -> first submitted review
* ``changes_to_revision``   changes requested -> next pushed head
* ``revision_to_rereview``  that push -> next review on the new head
* ``merge_wait``            last review on the merged head -> merge

Fail closed: missing/invalid timestamps, order contradictions and reviews
that do not name the head current at that time make the affected interval
UNKNOWN (never a guessed duration). Identical events are counted once.
Review bodies are never read; a team verdict such as a COMMENTED review that
requires changes must be passed as the normalized field
``verdict: "CHANGES_REQUIRED"``.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from statistics import median
from typing import Any

SCHEMA_VERSION = 1
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
EVENT_TYPES = {"opened", "ready_for_review", "push", "review", "merged", "closed"}
REVIEW_STATES = {"APPROVED", "CHANGES_REQUESTED", "COMMENTED"}
INTERVALS = ("ready_to_review", "changes_to_revision", "revision_to_rereview", "merge_wait")


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not _UTC_RE.fullmatch(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _sha(value: Any) -> str | None:
    return value if isinstance(value, str) and _SHA_RE.fullmatch(value) else None


def normalize(timeline: Any) -> tuple[list[dict[str, Any]], int, int]:
    if not isinstance(timeline, list):
        return [], 1, 0
    seen: set[str] = set()
    events: list[dict[str, Any]] = []
    malformed = duplicates = 0
    for index, raw in enumerate(timeline):
        if not isinstance(raw, dict) or raw.get("type") not in EVENT_TYPES:
            malformed += 1
            continue
        at = _time(raw.get("at"))
        if at is None:
            malformed += 1
            continue
        event = {"type": raw["type"], "at": at, "_index": index}
        if raw["type"] in {"opened", "push", "merged"}:
            event["head_sha"] = _sha(raw.get("head_sha"))
            if event["head_sha"] is None:
                malformed += 1
                continue
        if raw["type"] == "opened":
            event["draft"] = raw.get("draft") is True
        if raw["type"] == "review":
            state, commit = raw.get("state"), _sha(raw.get("commit_id"))
            if state not in REVIEW_STATES or commit is None:
                malformed += 1
                continue
            event["state"] = state
            event["commit_id"] = commit
            event["changes"] = state == "CHANGES_REQUESTED" or raw.get("verdict") == "CHANGES_REQUIRED"
        key = json.dumps({k: (v.isoformat() if isinstance(v, datetime) else v)
                          for k, v in event.items() if k != "_index"}, sort_keys=True)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        events.append(event)
    events.sort(key=lambda e: (e["at"], e["_index"]))
    return events, malformed, duplicates


def _interval(name: str, start: dict | None, end: dict | None, *, head: str | None,
              reason: str | None = None) -> dict[str, Any]:
    entry = {"interval": name, "head_sha": head, "start": None, "end": None, "seconds": None,
             "status": "UNKNOWN", "reason": reason}
    if start is not None:
        entry["start"] = start["at"].strftime("%Y-%m-%dT%H:%M:%SZ")
    if end is not None:
        entry["end"] = end["at"].strftime("%Y-%m-%dT%H:%M:%SZ")
    if reason is None and start is not None and end is not None:
        seconds = int((end["at"] - start["at"]).total_seconds())
        if seconds < 0:
            entry["reason"] = "order contradiction (end before start)"
        else:
            entry.update(seconds=seconds, status="OK")
    elif reason is None:
        entry["reason"] = "matching event not observed"
    return entry


def compute_turnaround(timeline: Any) -> dict[str, Any]:
    """Pure computation over a normalized PR timeline."""
    events, malformed, duplicates = normalize(timeline)
    intervals: list[dict[str, Any]] = []
    head: str | None = None
    head_known = True

    # Track head over time: opened/push set the current head.
    for event in events:
        if event["type"] in {"opened", "push"}:
            head = event["head_sha"]
        event["_head"] = head
    if not any(e["type"] in {"opened", "push"} for e in events):
        head_known = False

    def head_ok(review: dict[str, Any]) -> bool:
        return head_known and review["commit_id"] == review["_head"]

    reviews = [e for e in events if e["type"] == "review"]

    # ready_to_review: explicit ready_for_review, or opened non-draft.
    ready = next((e for e in events if e["type"] == "ready_for_review"
                  or (e["type"] == "opened" and not e.get("draft"))), None)
    if ready is not None:
        first = next((r for r in reviews if r["at"] >= ready["at"]), None)
        if first is not None and not head_ok(first):
            intervals.append(_interval("ready_to_review", ready, first, head=first["_head"],
                                       reason="review does not name the head current at that time"))
        else:
            intervals.append(_interval("ready_to_review", ready, first, head=ready.get("_head")))

    # Revision cycles.
    for review in reviews:
        if not review["changes"]:
            continue
        if not head_ok(review):
            intervals.append(_interval("changes_to_revision", review, None, head=review["_head"],
                                       reason="change request does not name the head current at that time"))
            continue
        push = next((e for e in events if e["type"] == "push" and e["at"] >= review["at"]
                     and e["head_sha"] != review["commit_id"]), None)
        intervals.append(_interval("changes_to_revision", review, push, head=review["commit_id"]))
        if push is None:
            continue
        rereview = next((r for r in reviews if r["at"] >= push["at"]), None)
        if rereview is not None and rereview["commit_id"] != push["head_sha"]:
            intervals.append(_interval("revision_to_rereview", push, rereview, head=push["head_sha"],
                                       reason="re-review names a different head than the revision"))
        else:
            intervals.append(_interval("revision_to_rereview", push, rereview, head=push["head_sha"]))

    merged = next((e for e in events if e["type"] == "merged"), None)
    if merged is not None:
        on_head = [r for r in reviews if r["at"] <= merged["at"] and r["commit_id"] == merged["head_sha"]]
        if not on_head:
            intervals.append(_interval("merge_wait", None, merged, head=merged["head_sha"],
                                       reason="no review on the merged head before merge"))
        else:
            intervals.append(_interval("merge_wait", on_head[-1], merged, head=merged["head_sha"]))

    summary = {}
    for name in INTERVALS:
        values = [i["seconds"] for i in intervals if i["interval"] == name and i["status"] == "OK"]
        summary[name] = {
            "ok_count": len(values),
            "unknown_count": sum(1 for i in intervals if i["interval"] == name and i["status"] == "UNKNOWN"),
            "total_seconds": sum(values) if values else None,
            "median_seconds": median(values) if values else None,
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "intervals": intervals,
        "summary": summary,
        "event_counts": {"accepted": len(events), "malformed": malformed, "duplicates": duplicates},
        "limits": [
            "synthetic/normalized timeline only; no GitHub API access",
            "review bodies are not parsed; team verdicts must be normalized by the caller",
            "independent helper; not wired into existing KPI collectors",
        ],
    }
