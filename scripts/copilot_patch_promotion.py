from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from typing import Iterable


@dataclass(frozen=True)
class PromotionDecision:
    eligible: bool
    reason: str


def evaluate_promotion(
    *,
    issue_number: int,
    source_run_success: bool,
    harness_outcome: str | None,
    source_base_sha: str | None,
    current_base_sha: str | None,
    changed_paths: Iterable[str] | None,
    allowed_paths: Iterable[str] | None,
    forbidden_paths: Iterable[str] | None,
    duplicate_pr_exists: bool = False,
    already_applied: bool = False,
) -> PromotionDecision:
    if issue_number == 79:
        return PromotionDecision(False, "PROTECTED_ISSUE_79")
    if not source_run_success:
        return PromotionDecision(False, "SOURCE_RUN_NOT_SUCCESS")
    if harness_outcome != "REVIEW_READY_VALIDATED":
        return PromotionDecision(False, "SOURCE_NOT_REVIEW_READY_VALIDATED")
    if not source_base_sha or not current_base_sha:
        return PromotionDecision(False, "MALFORMED_METADATA")
    if source_base_sha != current_base_sha:
        return PromotionDecision(False, "BASE_SHA_MISMATCH")
    if duplicate_pr_exists:
        return PromotionDecision(False, "PR_ALREADY_EXISTS")
    if already_applied:
        return PromotionDecision(False, "ALREADY_APPLIED")

    changed = [p for p in (changed_paths or []) if p]
    allowed = [p for p in (allowed_paths or []) if p]
    forbidden = [p for p in (forbidden_paths or []) if p]
    if not changed or not allowed:
        return PromotionDecision(False, "ISSUE_CONTRACT_INVALID")

    for path in changed:
        if not any(fnmatch(path, pattern) for pattern in allowed):
            return PromotionDecision(False, "OUTSIDE_ALLOWED_PATHS")
        if any(fnmatch(path, pattern) for pattern in forbidden):
            return PromotionDecision(False, "FORBIDDEN_PATH")

    return PromotionDecision(True, "ELIGIBLE")
