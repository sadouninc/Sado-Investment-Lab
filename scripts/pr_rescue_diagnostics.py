from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable


TERMINAL_STATES = {"CLOSED", "MERGED"}
RED_ACTIONS = {
    "MERGE",
    "MAIN_PUSH",
    "FORCE_PUSH",
    "HISTORY_REWRITE",
    "ISSUE_CLOSE",
    "SCOPE_CHANGE",
    "SECRETS_CHANGE",
    "AUTH_CHANGE",
    "PERMISSIONS_CHANGE",
    "INVESTMENT_AUTHORITY_CHANGE",
    "TOUCH_ISSUE_79",
}


@dataclass(frozen=True)
class RescueDiagnosis:
    status: str
    classes: tuple[str, ...]
    pr_number: int
    head_sha: str
    base_sha_at_scan: str
    evidence: tuple[str, ...]
    affected_paths: tuple[str, ...]
    suggested_actions: tuple[str, ...]
    mutation_performed: bool
    unknowns: tuple[str, ...]
    diagnosis_key: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "classes": list(self.classes),
            "pr_number": self.pr_number,
            "head_sha": self.head_sha,
            "base_sha_at_scan": self.base_sha_at_scan,
            "evidence": list(self.evidence),
            "affected_paths": list(self.affected_paths),
            "suggested_actions": list(self.suggested_actions),
            "mutation_performed": self.mutation_performed,
            "unknowns": list(self.unknowns),
            "diagnosis_key": self.diagnosis_key,
        }


def _normalized_strings(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _required_text(snapshot: dict[str, Any], field: str) -> str:
    value = snapshot.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _diagnosis_key(snapshot: dict[str, Any], trigger: str) -> str:
    checks = snapshot.get("checks")
    check_snapshot = "UNKNOWN" if checks is None else checks
    payload = {
        "repository": _required_text(snapshot, "repository"),
        "pr_number": snapshot.get("pr_number"),
        "head_sha": _required_text(snapshot, "head_sha"),
        "base_sha_at_scan": _required_text(snapshot, "base_sha_at_scan"),
        "trigger": trigger,
        "checks": check_snapshot,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def diagnose(snapshot: dict[str, Any], *, trigger: str = "MANUAL_SCAN") -> RescueDiagnosis:
    """Classify a PR snapshot without mutating GitHub or a worktree.

    The caller owns GitHub API access. This pure boundary accepts only an explicit
    snapshot so the same evidence always produces the same report.
    """
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be an object")
    pr_number = snapshot.get("pr_number")
    if not isinstance(pr_number, int) or isinstance(pr_number, bool) or pr_number <= 0:
        raise ValueError("pr_number must be a positive integer")

    normalized_trigger = str(trigger).strip().upper() or "MANUAL_SCAN"
    state = _required_text(snapshot, "state").upper()
    head_sha = _required_text(snapshot, "head_sha")
    base_sha = _required_text(snapshot, "base_sha_at_scan")
    key = _diagnosis_key(snapshot, normalized_trigger)

    affected_paths = _normalized_strings(snapshot.get("changed_paths", []))
    evidence: list[str] = []
    classes: list[str] = []
    suggestions: list[str] = []
    unknowns: list[str] = []

    if state in TERMINAL_STATES or snapshot.get("superseded") is True:
        terminal = "SUPERSEDED" if snapshot.get("superseded") is True else state
        return RescueDiagnosis(
            status="NOT_APPLICABLE",
            classes=(terminal,),
            pr_number=pr_number,
            head_sha=head_sha,
            base_sha_at_scan=base_sha,
            evidence=(f"PR state is {terminal}",),
            affected_paths=affected_paths,
            suggested_actions=(),
            mutation_performed=False,
            unknowns=(),
            diagnosis_key=key,
        )

    checks = snapshot.get("checks")
    if checks is None:
        unknowns.append("CHECK_STATUS_UNAVAILABLE")
    elif not isinstance(checks, list):
        raise ValueError("checks must be a list or null")
    else:
        failed = sorted(
            str(item.get("name", "UNKNOWN"))
            for item in checks
            if isinstance(item, dict) and str(item.get("conclusion", "")).upper() in {"FAILURE", "TIMED_OUT", "CANCELLED"}
        )
        if failed:
            classes.append("CI_FAILURE")
            evidence.append("failed checks: " + ", ".join(failed))
            suggestions.append("inspect failed job logs and identify the smallest owner-scoped fix")

    if snapshot.get("base_advanced") is True:
        classes.append("STALE_BASE")
        evidence.append("base branch advanced after the PR base snapshot")
        suggestions.append("refresh latest base after an explicit mutation lease")
    elif snapshot.get("base_advanced") is None:
        unknowns.append("BASE_FRESHNESS_UNKNOWN")

    overlap = _normalized_strings(snapshot.get("overlapping_paths", []))
    if overlap:
        classes.append("PATH_OVERLAP")
        evidence.append("overlapping paths: " + ", ".join(overlap))
        suggestions.append("preserve already-merged behavior and reduce the rescue diff")

    if snapshot.get("owner_scope_conflict") is True:
        classes.append("OWNER_SCOPE_CONFLICT")
        evidence.append("another implementation owner changed the same scope")
        suggestions.append("request an explicit owner handoff before any mutation")

    unresolved = snapshot.get("unresolved_review_threads")
    if unresolved is None:
        unknowns.append("REVIEW_THREAD_STATUS_UNKNOWN")
    elif not isinstance(unresolved, int) or isinstance(unresolved, bool) or unresolved < 0:
        raise ValueError("unresolved_review_threads must be a non-negative integer or null")
    elif unresolved:
        classes.append("REVIEW_FEEDBACK")
        evidence.append(f"unresolved review threads: {unresolved}")
        suggestions.append("classify feedback against the existing Issue scope")

    classes_out = _normalized_strings(classes)
    if classes_out:
        status = "OWNER_LEASE_REQUIRED"
    elif unknowns:
        status = "UNKNOWN"
    else:
        status = "NO_ACTION"

    return RescueDiagnosis(
        status=status,
        classes=classes_out,
        pr_number=pr_number,
        head_sha=head_sha,
        base_sha_at_scan=base_sha,
        evidence=_normalized_strings(evidence),
        affected_paths=affected_paths,
        suggested_actions=_normalized_strings(suggestions),
        mutation_performed=False,
        unknowns=_normalized_strings(unknowns),
        diagnosis_key=key,
    )


def authorize_mutation(lease: dict[str, Any] | None, request: dict[str, Any]) -> str:
    """Fail-closed authorization gate for a future YELLOW rescue worker.

    PR1 never performs the mutation. Returning ``AUTHORIZED`` only means a later
    worker may continue with its own expiry and GitHub-state checks.
    """
    action = str(request.get("action", "")).strip().upper()
    if action in RED_ACTIONS or request.get("issue_number") == 79:
        return "RED_BLOCKED"
    if lease is None:
        return "LEASE_MISSING"
    if request.get("current_head_sha") != lease.get("expected_head_sha"):
        return "LEASE_STALE"

    allowed_actions = {str(item).strip().upper() for item in lease.get("allowed_actions", [])}
    if action not in allowed_actions:
        return "SCOPE_DENIED"

    allowed_paths = tuple(str(item).strip().rstrip("*") for item in lease.get("allowed_paths", []))
    requested_paths = _normalized_strings(request.get("paths", []))
    if any(not any(path.startswith(prefix) for prefix in allowed_paths if prefix) for path in requested_paths):
        return "SCOPE_DENIED"
    return "AUTHORIZED"

