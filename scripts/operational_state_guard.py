from __future__ import annotations

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
) -> AutoGreenMergeResult:
    """Evaluate AUTO_GREEN eligibility. Any unsafe/unknown caller input should be passed as False/True to block."""
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
