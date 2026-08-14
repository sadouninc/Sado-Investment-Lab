from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

VALID_MODES = {"ACTIVE", "AWAY"}
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


@dataclass(frozen=True)
class ModeTransitionResult:
    allowed: bool
    status: str
    current_mode: str
    target_mode: str
    transition_id: str


def validate_mode_transition(
    *,
    current_mode: str,
    expected_current_mode: str,
    target_mode: str,
    transition_id: str,
    last_transition_id: str | None = None,
) -> ModeTransitionResult:
    """Validate a compare-and-set style User Mode transition.

    A stale transition must fail closed instead of overwriting a newer state.
    This function performs no GitHub writes.
    """
    for value in (current_mode, expected_current_mode, target_mode):
        if value not in VALID_MODES:
            return ModeTransitionResult(False, "INVALID_MODE", current_mode, target_mode, transition_id)
    if not transition_id.strip():
        return ModeTransitionResult(False, "MISSING_TRANSITION_ID", current_mode, target_mode, transition_id)
    if last_transition_id and transition_id == last_transition_id:
        return ModeTransitionResult(False, "DUPLICATE_TRANSITION_ID", current_mode, target_mode, transition_id)
    if current_mode != expected_current_mode:
        return ModeTransitionResult(False, "STALE_EXPECTED_MODE", current_mode, target_mode, transition_id)
    if current_mode == target_mode:
        return ModeTransitionResult(False, "NOOP_TRANSITION", current_mode, target_mode, transition_id)
    return ModeTransitionResult(True, "TRANSITION_ALLOWED", current_mode, target_mode, transition_id)


def classify_blocker(blocker_class: str, *, detail: str, ref: str) -> dict[str, str]:
    """Normalize one blocker for AWAY routing without deciding Owner Authority."""
    normalized = blocker_class.strip().upper().replace(" ", "_")
    if normalized not in BLOCKER_CLASSES:
        normalized = "TECHNICAL_INVESTIGATION"
    return {"class": normalized, "detail": detail.strip(), "ref": ref.strip()}


def split_away_blockers(blockers: Iterable[Mapping[str, str]]) -> dict[str, list[dict[str, str]]]:
    """Separate true Owner Authority from work that should continue autonomously."""
    owner: list[dict[str, str]] = []
    autonomous: list[dict[str, str]] = []
    for raw in blockers:
        item = classify_blocker(
            str(raw.get("class", "")), detail=str(raw.get("detail", "")), ref=str(raw.get("ref", ""))
        )
        if item["class"] == "OWNER_AUTHORITY":
            owner.append(item)
        else:
            autonomous.append(item)
    return {"owner_authority": owner, "autonomous": autonomous}
