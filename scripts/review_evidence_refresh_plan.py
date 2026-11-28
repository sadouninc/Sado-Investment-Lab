"""Refresh planning for PR review evidence after CI / review events (#999).

担当: ♦️ソラ

The #983 collector (``scripts/pr_review_evidence.py``) runs on pull_request
events, so CI is usually still PENDING when it samples. This module decides,
from *observed* events only, whether a fresh read-only evidence collection is
warranted. It is a pure function: it never schedules, dispatches, calls an API
or approves anything, and it does not modify the #983 collector.

Decisions:
* ``REFRESH``  - collect evidence again for ``latest_head`` (with ``refresh_key``).
* ``WAIT``     - nothing new since the last evidence, or runs still in progress.
* ``DONE``     - the PR is closed/merged, or the per-head refresh bound is reached.
* ``UNKNOWN``  - inputs malformed or the latest head cannot be determined.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import re
from typing import Any, Iterable

SCHEMA_VERSION = 1
DEFAULT_MAX_REFRESHES_PER_HEAD = 6
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
HEAD_EVENTS = {"opened", "synchronize", "reopened", "ready_for_review"}
OBSERVATION_KINDS = {"workflow_run", "check_suite", "check_run", "review", "review_comment", "review_thread"}
KINDS = OBSERVATION_KINDS | {"pull_request"}
EVIDENCE_STATUSES = {"EVIDENCE_COLLECTED", "BLOCKED", "PENDING", "STALE", "UNKNOWN"}


def _utc(value: Any) -> str | None:
    if not isinstance(value, str) or not _UTC_RE.fullmatch(value):
        return None
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return value


def _sha(value: Any) -> str | None:
    return value if isinstance(value, str) and _SHA_RE.fullmatch(value) else None


def _pos_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def normalize_events(events: Any) -> tuple[list[dict[str, Any]], int, int]:
    """Validate and de-duplicate observed events. Returns (events, malformed, duplicates)."""
    if not isinstance(events, list):
        return [], 1, 0
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    malformed = duplicates = 0
    for index, raw in enumerate(events):
        if not isinstance(raw, dict) or raw.get("kind") not in KINDS:
            malformed += 1
            continue
        at = _utc(raw.get("at"))
        head = _sha(raw.get("head_sha"))
        if at is None or head is None:
            malformed += 1
            continue
        event = {
            "kind": raw["kind"],
            "at": at,
            "head_sha": head,
            "action": raw.get("action") if isinstance(raw.get("action"), str) else None,
            "name": raw.get("name") if isinstance(raw.get("name"), str) else None,
            "run_id": _pos_int(raw.get("run_id")),
            "run_attempt": _pos_int(raw.get("run_attempt")),
            "status": raw.get("status") if isinstance(raw.get("status"), str) else None,
            "conclusion": raw.get("conclusion") if isinstance(raw.get("conclusion"), str) else None,
            "merged": raw.get("merged") is True,
            "_index": index,
        }
        if event["kind"] == "workflow_run" and (event["run_id"] is None or event["name"] is None):
            malformed += 1
            continue
        key = json.dumps({k: v for k, v in event.items() if k != "_index"}, sort_keys=True)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        out.append(event)
    out.sort(key=lambda e: (e["at"], e["_index"]))
    return out, malformed, duplicates


def latest_runs(events: Iterable[dict[str, Any]], head: str) -> list[dict[str, Any]]:
    """Latest observation per workflow on ``head`` (time order; attempts not compared across runs)."""
    latest: dict[str, dict[str, Any]] = {}
    for event in events:
        if event["kind"] != "workflow_run" or event["head_sha"] != head:
            continue
        previous = latest.get(event["name"])
        order = (event["at"], event["run_id"], event["run_attempt"] or 0)
        if previous is None or order >= previous["_order"]:
            latest[event["name"]] = {**event, "_order": order}
    return [
        {"name": e["name"], "run_id": e["run_id"], "run_attempt": e["run_attempt"],
         "status": e["status"], "conclusion": e["conclusion"], "at": e["at"]}
        for e in sorted(latest.values(), key=lambda item: item["name"])
    ]


def plan_refresh(events: Any, previous: Any = None, *,
                 max_refreshes_per_head: int = DEFAULT_MAX_REFRESHES_PER_HEAD) -> dict[str, Any]:
    """Decide whether review evidence should be collected again. Pure; no I/O."""
    normalized, malformed, duplicates = normalize_events(events)
    previous = previous if isinstance(previous, dict) else None
    reasons: list[str] = []

    def result(decision: str, *, head: str | None = None, runs: list | None = None,
               key: str | None = None, terminal: bool = False) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "decision": decision,
            "terminal": terminal,
            "latest_head": head,
            "refresh_key": key,
            "latest_runs": runs or [],
            "reasons": reasons,
            "event_counts": {"accepted": len(normalized), "malformed": malformed, "duplicates": duplicates},
            "side_effects": "none (plan only; no scheduling, API call, dispatch or approval)",
        }

    if malformed:
        reasons.append(f"{malformed} malformed event(s) ignored")

    closes = [e for e in normalized if e["kind"] == "pull_request" and e["action"] == "closed"]
    reopens = [e for e in normalized if e["kind"] == "pull_request" and e["action"] == "reopened"]
    if closes and (not reopens or closes[-1]["at"] >= reopens[-1]["at"]):
        reasons.append("pull request merged" if closes[-1]["merged"] else "pull request closed")
        return result("DONE", head=closes[-1]["head_sha"], terminal=True)

    head_events = [e for e in normalized if e["kind"] == "pull_request" and e["action"] in HEAD_EVENTS]
    head = head_events[-1]["head_sha"] if head_events else _sha(previous.get("head_sha")) if previous else None
    if head is None:
        reasons.append("latest head cannot be determined from events or previous evidence")
        return result("UNKNOWN")

    relevant = [e for e in normalized if e["kind"] in OBSERVATION_KINDS and e["head_sha"] == head]
    stale_count = sum(1 for e in normalized if e["kind"] in OBSERVATION_KINDS and e["head_sha"] != head)
    if stale_count:
        reasons.append(f"{stale_count} event(s) for older heads ignored")
    runs = latest_runs(normalized, head)
    pending = [r["name"] for r in runs if r["status"] != "completed"]

    trigger_at = max([e["at"] for e in relevant] + [e["at"] for e in head_events if e["head_sha"] == head] or [""])
    key = hashlib.sha256(f"{head}|{trigger_at}".encode()).hexdigest()[:16] if trigger_at else None

    prev_head = _sha(previous.get("head_sha")) if previous else None
    prev_at = _utc(previous.get("collected_at")) if previous else None
    prev_status = previous.get("status") if previous else None
    prev_key = previous.get("refresh_key") if previous else None
    prev_count = previous.get("refresh_count") if previous else 0
    prev_count = prev_count if isinstance(prev_count, int) and not isinstance(prev_count, bool) and prev_count >= 0 else None

    if previous is not None and (prev_at is None or prev_status not in EVIDENCE_STATUSES or prev_count is None):
        reasons.append("previous evidence record malformed; collecting fresh evidence")
        return result("REFRESH", head=head, runs=runs, key=key)
    if previous is None or prev_head != head:
        reasons.append("no evidence for the latest head yet" if previous is None else "head changed since last evidence")
        return result("REFRESH", head=head, runs=runs, key=key)

    if prev_count >= max_refreshes_per_head:
        reasons.append(f"refresh bound reached for this head ({prev_count}/{max_refreshes_per_head})")
        return result("DONE", head=head, runs=runs, key=key, terminal=True)
    if key is not None and prev_key == key:
        reasons.append("already refreshed for this trigger (duplicate suppressed)")
        return result("WAIT", head=head, runs=runs, key=key)

    newer = [e for e in relevant if e["at"] > prev_at]
    if not newer:
        reasons.append("no new CI or review observation since last evidence")
        return result("WAIT", head=head, runs=runs, key=key)
    if pending and not any(e["kind"] != "workflow_run" for e in newer):
        reasons.append("workflow run(s) still in progress: " + ", ".join(pending))
        return result("WAIT", head=head, runs=runs, key=key)
    reasons.append(f"{len(newer)} new observation(s) on the latest head since last evidence")
    return result("REFRESH", head=head, runs=runs, key=key)
