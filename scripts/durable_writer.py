"""Durable Writer / Landing Executor v1 (#828).

When ChatGPT direct-write is refused by its execution context, 🌊ナギ keeps
routing/judgement authority while a verified external writer performs a
bounded GitHub mutation and returns attributable durable evidence (a GitHub
id or commit SHA). This module is the fail-closed gate + landing boundary
between a ``scripts.pr_rescue_diagnostics.authorize_mutation`` decision and
the actual write.

Like ``scripts/pr_rescue_diagnostics.py``, this module performs no GitHub or
git I/O itself: the caller supplies already-fetched evidence
(:class:`WriteObservation`) and a ``perform_write`` callable that executes
the bounded mutation. This keeps the gate deterministic, dependency-free and
unit-testable, and keeps a single routing authority (🌊ナギ) instead of a
second implicit one living inside this writer.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Callable, Iterable, Mapping

from scripts.pr_rescue_diagnostics import authorize_mutation

LANDING_MARKER_PREFIX = "AUTO_LANDING_EXECUTOR"

# Evaluation order also doubles as the deterministic reason_codes ordering
# returned by evaluate_landing_gate.
FAIL_CLOSED_REASON_ORDER = (
    "LEASE_MISSING",
    "LEASE_STALE",
    "SCOPE_DENIED",
    "RED_BLOCKED",
    "EXACT_HEAD_MISMATCH",
    "CI_NOT_GREEN",
    "REVIEW_BLOCKER_UNRESOLVED",
    "REVIEW_BLOCKER_UNKNOWN",
    "MERGEABILITY_UNKNOWN",
    "MERGEABILITY_BLOCKED",
    "AUTHORITY_AMBIGUOUS",
)


@dataclass(frozen=True)
class WriteObservation:
    """Durable evidence snapshot the caller already fetched from GitHub.

    ``unresolved_review_threads=None`` and ``mergeability="UNKNOWN"`` are
    distinct, deliberate "unknown" states: they must fail closed exactly like
    an explicit blocker, never be treated as an implicit pass.
    """

    exact_head_sha: str
    observed_head_sha: str
    ci_status: str
    unresolved_review_threads: int | None
    mergeability: str
    authority: str


def landing_marker(*, idempotency_key: str) -> str:
    return f"<!-- {LANDING_MARKER_PREFIX} idempotency_key={idempotency_key} -->"


def already_landed(
    evidence_records: Iterable[Mapping[str, Any]], *, idempotency_key: str
) -> Mapping[str, Any] | None:
    """Return already-persisted durable evidence for this write, if any.

    ``evidence_records`` is whatever durable records the caller already
    fetched (PR/issue comments, commit trailers, prior run artifacts), each
    expected to carry a ``landing_marker()`` string under a ``marker`` or
    ``body`` field. A match here is what lets a validated rerun promote
    existing evidence instead of repeating the implementation run.
    """
    needle = f"idempotency_key={idempotency_key}"
    for record in evidence_records:
        haystack = str(record.get("marker", "") or record.get("body", ""))
        if LANDING_MARKER_PREFIX in haystack and needle in haystack:
            return record
    return None


def build_idempotency_key(*, lease_id: str, action: str, paths: Iterable[str]) -> str:
    material = "|".join(
        [
            str(lease_id).strip(),
            str(action).strip().upper(),
            ",".join(sorted(str(path) for path in paths)),
        ]
    )
    return sha256(material.encode("utf-8")).hexdigest()


def evaluate_landing_gate(
    lease: Mapping[str, Any] | None,
    request: Mapping[str, Any],
    observation: WriteObservation,
) -> dict[str, Any]:
    """Fail-closed pre-write gate.

    Combines the existing ``authorize_mutation`` scope/lease/RED-action gate
    with durable-write specific evidence: exact-head match, CI GREEN,
    resolved review threads, confirmed mergeability and unambiguous
    authority. Any missing or non-affirmative evidence blocks the write.
    """
    auth_status = authorize_mutation(lease, request)
    reasons: list[str] = []
    if auth_status != "AUTHORIZED":
        reasons.append(auth_status)

    if observation.observed_head_sha != observation.exact_head_sha:
        reasons.append("EXACT_HEAD_MISMATCH")
    if str(observation.ci_status).strip().upper() != "GREEN":
        reasons.append("CI_NOT_GREEN")
    if observation.unresolved_review_threads is None:
        reasons.append("REVIEW_BLOCKER_UNKNOWN")
    elif observation.unresolved_review_threads > 0:
        reasons.append("REVIEW_BLOCKER_UNRESOLVED")

    mergeability = str(observation.mergeability).strip().upper()
    if mergeability == "UNKNOWN":
        reasons.append("MERGEABILITY_UNKNOWN")
    elif mergeability != "MERGEABLE":
        reasons.append("MERGEABILITY_BLOCKED")

    if str(observation.authority).strip().upper() != "STANDARD":
        reasons.append("AUTHORITY_AMBIGUOUS")

    ordered = tuple(code for code in FAIL_CLOSED_REASON_ORDER if code in reasons)
    if ordered:
        return {"status": "BLOCKED", "write_allowed": False, "reason_codes": ordered}
    return {"status": "READY", "write_allowed": True, "reason_codes": ()}


def execute_landing(
    *,
    lease: Mapping[str, Any] | None,
    request: Mapping[str, Any],
    observation: WriteObservation,
    idempotency_key: str,
    evidence_records: Iterable[Mapping[str, Any]] = (),
    perform_write: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    executed_by: str,
) -> dict[str, Any]:
    """Execute a bounded durable write at most once and return attributable evidence.

    If durable evidence for ``idempotency_key`` already exists,
    ``perform_write`` is never invoked again; the existing evidence is
    returned with ``rerun_action="PROMOTE_FOLLOWUP"`` so a validated rerun
    attempt can trigger follow-up re-evaluation and promotion without a
    duplicate implementation run.
    """
    if not str(idempotency_key).strip():
        raise ValueError("idempotency_key must be non-blank")
    if not str(executed_by).strip():
        raise ValueError("executed_by must be non-blank for attribution")

    existing = already_landed(evidence_records, idempotency_key=idempotency_key)
    if existing is not None:
        return {
            "status": "ALREADY_LANDED",
            "idempotency_key": idempotency_key,
            "durable_evidence": dict(existing),
            "rerun_action": "PROMOTE_FOLLOWUP",
        }

    gate = evaluate_landing_gate(lease, request, observation)
    if not gate["write_allowed"]:
        return {
            "status": "FAIL_CLOSED",
            "idempotency_key": idempotency_key,
            "gate_status": gate["status"],
            "reason_codes": gate["reason_codes"],
            "durable_evidence": None,
            "rerun_action": None,
        }

    result = perform_write(request)
    github_id = result.get("id")
    sha = result.get("sha")
    if not github_id and not sha:
        raise ValueError("perform_write must return a durable GitHub id or sha")

    durable_evidence = {
        "idempotency_key": idempotency_key,
        "github_id": github_id,
        "sha": sha,
        "executed_by": executed_by,
        "action": request.get("action"),
        "paths": sorted(str(path) for path in request.get("paths", [])),
        "marker": landing_marker(idempotency_key=idempotency_key),
    }
    return {
        "status": "LANDED",
        "idempotency_key": idempotency_key,
        "durable_evidence": durable_evidence,
        "rerun_action": None,
    }
