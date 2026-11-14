from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Mapping

VALID_MODES = {"ACTIVE_MANUAL", "ACTIVE_AUTO", "AWAY"}
LEGACY_MODE_ALIASES = {"ACTIVE": "ACTIVE_MANUAL"}
BLOCKER_CLASSES = {
    "OWNER_AUTHORITY",
    "REVIEW_WAIT",
    "CI_FAILURE",
    "DEPENDENCY",
    "MISSING_ARTIFACT",
    "TECHNICAL_INVESTIGATION",
    "TOOL_LIMIT",
    "EXTERNAL",
    "OWNER_CONFLICT",
}
DELEGATED_SORA_SM_TRIGGERS = {
    "QUEUE_STARVATION",
    "OWNER_CONFLICT",
    "NO_REROUTE_AFTER_BLOCKED_ESCAPE",
    "PRIORITY_CONFLICT",
    "STATE_DRIFT",
    "GLOBAL_BLOCKER",
}


@dataclass(frozen=True)
class ModeTransitionResult:
    allowed: bool
    status: str
    current_mode: str
    target_mode: str
    transition_id: str


@dataclass(frozen=True)
class AutoGreenMergeResult:
    allowed: bool
    status: str
    blocking_reasons: tuple[str, ...]


@dataclass(frozen=True)
class AutoGreenBlockerRecordResult:
    action: str
    fingerprint: str
    blocking_reasons: tuple[str, ...]


def normalize_mode(value: str) -> str:
    normalized = value.strip().upper()
    return LEGACY_MODE_ALIASES.get(normalized, normalized)


def mode_contract(mode: str) -> dict[str, str]:
    """Return the orthogonal runtime contract for one user-facing mode."""
    normalized = normalize_mode(mode)
    contracts = {
        "ACTIVE_MANUAL": {
            "mode": "ACTIVE_MANUAL",
            "presence": "ACTIVE",
            "merge_policy": "MANUAL",
            "flow_authority": "NAGI",
        },
        "ACTIVE_AUTO": {
            "mode": "ACTIVE_AUTO",
            "presence": "ACTIVE",
            "merge_policy": "AUTO_GREEN",
            "flow_authority": "NAGI",
        },
        "AWAY": {
            "mode": "AWAY",
            "presence": "AWAY",
            "merge_policy": "AUTO_GREEN",
            "flow_authority": "NAGI_OR_SORA_DELEGATED",
        },
    }
    if normalized not in contracts:
        return {
            "mode": "UNKNOWN",
            "presence": "UNKNOWN",
            "merge_policy": "UNKNOWN",
            "flow_authority": "UNKNOWN",
        }
    return contracts[normalized]


def validate_mode_transition(
    *,
    current_mode: str,
    expected_current_mode: str,
    target_mode: str,
    transition_id: str,
    last_transition_id: str | None = None,
) -> ModeTransitionResult:
    """Validate a compare-and-set style User Mode transition.

    Legacy ``ACTIVE`` is normalized to ``ACTIVE_MANUAL`` for migration safety.
    A stale transition must fail closed instead of overwriting a newer state.
    This function performs no GitHub writes.
    """
    current = normalize_mode(current_mode)
    expected = normalize_mode(expected_current_mode)
    target = normalize_mode(target_mode)
    for value in (current, expected, target):
        if value not in VALID_MODES:
            return ModeTransitionResult(False, "INVALID_MODE", current, target, transition_id)
    if not transition_id.strip():
        return ModeTransitionResult(False, "MISSING_TRANSITION_ID", current, target, transition_id)
    if last_transition_id and transition_id == last_transition_id:
        return ModeTransitionResult(False, "DUPLICATE_TRANSITION_ID", current, target, transition_id)
    if current != expected:
        return ModeTransitionResult(False, "STALE_EXPECTED_MODE", current, target, transition_id)
    if current == target:
        return ModeTransitionResult(False, "NOOP_TRANSITION", current, target, transition_id)
    return ModeTransitionResult(True, "TRANSITION_ALLOWED", current, target, transition_id)


def should_activate_delegated_sora_sm(*, mode: str, trigger: str) -> bool:
    """Activate Sora's delegated Flow Authority only for explicit AWAY traffic events."""
    return normalize_mode(mode) == "AWAY" and trigger.strip().upper() in DELEGATED_SORA_SM_TRIGGERS


def evaluate_auto_green_merge(
    *,
    mode: str,
    ci_pass: bool,
    request_changes: bool,
    merge_conflict: bool,
    required_gates_pass: bool,
    latest_head_reviewed: bool,
    owner_or_investment_authority: bool,
    sensitive_change: bool,
    explicit_owner_acceptance_required: bool,
    protected_issue_79: bool,
    required_review_policy: str = "PASS",
    github_approved: bool = False,
) -> AutoGreenMergeResult:
    """Evaluate AUTO_GREEN eligibility with fail-safe defaults.
    
    For uncertain/unknown inputs:
    - Pass False for ci_pass, required_gates_pass, latest_head_reviewed (blocks when False)
    - Pass True for request_changes, merge_conflict, owner_or_investment_authority, 
      sensitive_change, explicit_owner_acceptance_required, protected_issue_79 (blocks when True)
    
    This ensures unknown states fail closed and block auto-merge.
    """
    contract = mode_contract(mode)
    reasons: list[str] = []
    if contract["merge_policy"] != "AUTO_GREEN":
        reasons.append("MERGE_POLICY_NOT_AUTO_GREEN")
    if not ci_pass:
        reasons.append("CI_NOT_PASS")
    if request_changes:
        reasons.append("REQUEST_CHANGES")
    if merge_conflict:
        reasons.append("MERGE_CONFLICT")
    if not required_gates_pass:
        reasons.append("REQUIRED_GATE_NOT_PASS")
    if not latest_head_reviewed:
        reasons.append("LATEST_HEAD_NOT_REVIEWED")
    review_policy = required_review_policy.strip().upper()
    if review_policy not in {"PASS", "REQUIRED"}:
        reasons.append("REQUIRED_REVIEW_POLICY_UNKNOWN")
    elif review_policy == "REQUIRED" and not github_approved:
        reasons.append("GITHUB_APPROVAL_REQUIRED")
    if owner_or_investment_authority:
        reasons.append("OWNER_OR_INVESTMENT_AUTHORITY")
    if sensitive_change:
        reasons.append("SENSITIVE_CHANGE")
    if explicit_owner_acceptance_required:
        reasons.append("OWNER_ACCEPTANCE_REQUIRED")
    if protected_issue_79:
        reasons.append("PROTECTED_ISSUE_79")
    if reasons:
        return AutoGreenMergeResult(False, "AUTO_GREEN_BLOCKED", tuple(reasons))
    return AutoGreenMergeResult(True, "AUTO_GREEN_ALLOWED", ())


def build_auto_green_evidence_fingerprint(
    *,
    pr_number: int,
    head_sha: str,
    ci_state: str,
    ci_contexts: Iterable[str],
    technical_review_state: str,
    technical_review_evidence_id: str,
    request_changes: bool,
    unresolved_blockers: Iterable[str],
    required_review_policy: str,
    required_review_policy_source: str,
    mergeable: bool,
    required_gates_pass: bool,
    owner_or_investment_authority: bool,
    path_conflict: bool,
    sensitive_change: bool,
    explicit_owner_acceptance_required: bool,
    protected_issue_79: bool,
) -> str:
    """Hash the exact evidence that justified one AUTO_GREEN block.

    Suppression is deliberately separate from merge eligibility: this digest
    can only deduplicate an already-blocked notification. Missing or ambiguous
    evidence raises instead of producing a suppressible fingerprint.
    """
    policy = required_review_policy.strip().upper()
    required_text = {
        "head_sha": head_sha,
        "ci_state": ci_state,
        "technical_review_state": technical_review_state,
        "technical_review_evidence_id": technical_review_evidence_id,
        "required_review_policy_source": required_review_policy_source,
    }
    if pr_number <= 0 or any(not value.strip() for value in required_text.values()):
        raise ValueError("incomplete AUTO_GREEN evidence")
    if policy not in {"PASS", "REQUIRED", "UNKNOWN"}:
        raise ValueError("invalid required review policy state")

    evidence = {
        "pr_number": pr_number,
        "head_sha": head_sha.strip(),
        "ci_state": ci_state.strip().upper(),
        "ci_contexts": sorted({value.strip() for value in ci_contexts if value.strip()}),
        "technical_review_state": technical_review_state.strip().upper(),
        "technical_review_evidence_id": technical_review_evidence_id.strip(),
        "request_changes": request_changes,
        "unresolved_blockers": sorted({value.strip() for value in unresolved_blockers if value.strip()}),
        "required_review_policy": policy,
        "required_review_policy_source": required_review_policy_source.strip(),
        "mergeable": mergeable,
        "required_gates_pass": required_gates_pass,
        "owner_or_investment_authority": owner_or_investment_authority,
        "path_conflict": path_conflict,
        "sensitive_change": sensitive_change,
        "explicit_owner_acceptance_required": explicit_owner_acceptance_required,
        "protected_issue_79": protected_issue_79,
    }
    canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def decide_auto_green_blocker_record(
    *,
    fingerprint: str,
    blocking_reasons: Iterable[str],
    previous_fingerprint: str | None = None,
    previous_blocking_reasons: Iterable[str] | None = None,
) -> AutoGreenBlockerRecordResult:
    """Decide whether to emit or suppress an already-blocked escape record."""
    reasons = tuple(sorted({value.strip() for value in blocking_reasons if value.strip()}))
    if not reasons:
        return AutoGreenBlockerRecordResult("NO_BLOCKER_RECORD", fingerprint, ())
    valid_fingerprint = len(fingerprint) == 64 and all(char in "0123456789abcdef" for char in fingerprint)
    if not valid_fingerprint:
        raise ValueError("invalid AUTO_GREEN evidence fingerprint")
    previous_reasons = tuple(
        sorted({value.strip() for value in (previous_blocking_reasons or ()) if value.strip()})
    )
    if previous_fingerprint == fingerprint and previous_reasons == reasons:
        action = "SUPPRESS_UNCHANGED_BLOCKER"
    elif previous_fingerprint:
        action = "REEVALUATE_CHANGED_EVIDENCE"
    else:
        action = "EMIT_BLOCKED_ESCAPE"
    return AutoGreenBlockerRecordResult(action, fingerprint, reasons)


def classify_blocker(blocker_class: str, *, detail: str, ref: str) -> dict[str, str]:
    """Normalize one blocker for AWAY routing without deciding Owner Authority.

    An unrecognized class is never silently reinterpreted as a known
    autonomous-safe class (e.g. TECHNICAL_INVESTIGATION); it is preserved as
    ``UNKNOWN`` so routing can fail closed instead of guessing.
    """
    normalized = blocker_class.strip().upper().replace(" ", "_")
    if normalized not in BLOCKER_CLASSES:
        normalized = "UNKNOWN"
    return {"class": normalized, "detail": detail.strip(), "ref": ref.strip()}


def split_away_blockers(blockers: Iterable[Mapping[str, str]]) -> dict[str, list[dict[str, str]]]:
    """Separate true Owner Authority from work that should continue autonomously.

    Blockers with an unrecognized class fail closed into ``owner_authority``
    rather than being guessed into the autonomous bucket, since an unknown
    class may in fact require Owner Authority.
    """
    owner: list[dict[str, str]] = []
    autonomous: list[dict[str, str]] = []
    for raw in blockers:
        item = classify_blocker(
            str(raw.get("class", "")), detail=str(raw.get("detail", "")), ref=str(raw.get("ref", ""))
        )
        if item["class"] in ("OWNER_AUTHORITY", "UNKNOWN"):
            owner.append(item)
        else:
            autonomous.append(item)
    return {"owner_authority": owner, "autonomous": autonomous}

