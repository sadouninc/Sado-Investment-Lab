"""Deterministic close preflight for issues with explicit Owner Acceptance gates.

This module is intentionally side-effect free.  It does not close/reopen issues and it
never infers Product Owner approval from CI, internal review, or readiness language.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Iterable


class GateStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    READY_FOR_OWNER_REVIEW = "READY_FOR_OWNER_REVIEW"
    OWNER_REVIEWED = "OWNER_REVIEWED"
    OWNER_ACCEPTANCE_UNVERIFIED = "OWNER_ACCEPTANCE_UNVERIFIED"


@dataclass(frozen=True)
class ClosePreflight:
    owner_gate_required: bool
    status: GateStatus
    close_allowed: bool
    evidence_ref: str | None = None
    reason: str = ""


_REQUIRED_MARKERS = (
    re.compile(r"owner\s+acceptance\s*:\s*required", re.I),
    re.compile(r"owner\s+review\s*:\s*required", re.I),
    re.compile(r"product\s+owner\s+approval\s*:\s*required", re.I),
    re.compile(r"👑\s*サド\s*実使用レビュー.{0,40}(?:必須|完了.*done|まで.*done)", re.I),
)

# Strong evidence only.  Readiness/planned wording is deliberately excluded.
_PASS_MARKERS = (
    re.compile(r"owner\s+acceptance\s*:\s*(?:pass|approved|ok)\b", re.I),
    re.compile(r"owner\s+review\s*:\s*(?:pass|approved|completed)\b", re.I),
    re.compile(r"reviewed\s+by\s*:\s*👑\s*サド", re.I),
    re.compile(r"👑\s*サド.{0,30}(?:実使用(?:レビュー)?完了|承認(?:済み)?|\bpass\b)", re.I),
)

_AMBIGUOUS_GATE_TERMS = re.compile(
    r"owner\s+acceptance|product\s+owner\s+approval|owner\s+review|👑\s*サド\s*実使用レビュー",
    re.I,
)


def owner_gate_required(issue_body: str) -> bool:
    """Return True only when the issue contract explicitly makes owner review a gate."""
    text = issue_body or ""
    if any(pattern.search(text) for pattern in _REQUIRED_MARKERS):
        return True

    # A checked/unchecked Definition-of-Done item is also an explicit contract.
    for line in text.splitlines():
        if re.search(r"^\s*[-*]\s*\[[ xX]\]", line) and _AMBIGUOUS_GATE_TERMS.search(line):
            return True
    return False


def find_owner_acceptance_evidence(comments: Iterable[tuple[str, str]]) -> str | None:
    """Return the first strong owner-acceptance evidence ref, otherwise None.

    comments are ``(ref, body)`` pairs.  Callers are responsible for supplying only
    comments whose author identity is trusted as Product Owner when author identity is
    available.  The textual contract remains strict so AI/internal-review comments do
    not become acceptance accidentally.
    """
    for ref, body in comments:
        text = body or ""
        if any(pattern.search(text) for pattern in _PASS_MARKERS):
            return ref
    return None


def evaluate_close_preflight(
    issue_body: str,
    comments: Iterable[tuple[str, str]],
    *,
    contract_ambiguous: bool = False,
) -> ClosePreflight:
    """Evaluate whether ``completed`` close is allowed for the supplied issue contract."""
    required = owner_gate_required(issue_body)
    if contract_ambiguous:
        return ClosePreflight(
            owner_gate_required=required,
            status=GateStatus.OWNER_ACCEPTANCE_UNVERIFIED,
            close_allowed=False,
            reason="Owner Acceptance contract is ambiguous; fail closed.",
        )

    if not required:
        return ClosePreflight(
            owner_gate_required=False,
            status=GateStatus.NOT_REQUIRED,
            close_allowed=True,
            reason="No explicit Owner Acceptance gate in issue contract.",
        )

    evidence_ref = find_owner_acceptance_evidence(comments)
    if evidence_ref:
        return ClosePreflight(
            owner_gate_required=True,
            status=GateStatus.OWNER_REVIEWED,
            close_allowed=True,
            evidence_ref=evidence_ref,
            reason="Explicit Owner Acceptance evidence found.",
        )

    return ClosePreflight(
        owner_gate_required=True,
        status=GateStatus.READY_FOR_OWNER_REVIEW,
        close_allowed=False,
        reason="Implementation may be complete, but explicit Owner Acceptance evidence is missing.",
    )
