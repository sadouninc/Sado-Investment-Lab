from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any, Iterable, Mapping, Sequence

from scripts.policy_state_sequence import summarize_policy_state_sequence


class PolicyCheckpointTimelineError(ValueError):
    pass


def _parse_date(value: Any, field: str) -> date:
    if not isinstance(value, str) or not value.strip():
        raise PolicyCheckpointTimelineError(f"{field} must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise PolicyCheckpointTimelineError(f"{field} must be YYYY-MM-DD") from exc


def _days_after(checkpoint: date, observed: str | None) -> int | None:
    if observed is None:
        return None
    return (_parse_date(observed, "observed_at") - checkpoint).days


def _normalize_checkpoints(checkpoints: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in checkpoints:
        if not isinstance(raw, Mapping):
            raise PolicyCheckpointTimelineError("checkpoints must contain objects")
        checkpoint_id = raw.get("checkpoint_id")
        if not isinstance(checkpoint_id, str) or not checkpoint_id.strip():
            raise PolicyCheckpointTimelineError("checkpoint_id must be a non-empty string")
        checkpoint_id = checkpoint_id.strip()
        if checkpoint_id in seen_ids:
            raise PolicyCheckpointTimelineError(f"duplicate checkpoint_id: {checkpoint_id}")
        seen_ids.add(checkpoint_id)
        policy_t0 = _parse_date(raw.get("policy_t0"), "policy_t0").isoformat()
        stage = raw.get("stage")
        if stage is not None and (not isinstance(stage, str) or not stage.strip()):
            raise PolicyCheckpointTimelineError("stage must be a non-empty string when supplied")
        limitations = raw.get("limitations") or []
        if not isinstance(limitations, list) or any(not isinstance(item, str) or not item.strip() for item in limitations):
            raise PolicyCheckpointTimelineError("limitations must be a list of non-empty strings")
        normalized.append(
            {
                "checkpoint_id": checkpoint_id,
                "policy_t0": policy_t0,
                "stage": stage.strip() if isinstance(stage, str) else None,
                "limitations": sorted(set(item.strip().upper() for item in limitations)),
            }
        )
    return sorted(normalized, key=lambda row: (row["policy_t0"], row["checkpoint_id"]))


def build_policy_checkpoint_timeline(
    *,
    history: Iterable[Mapping[str, Any]],
    checkpoints: Sequence[Mapping[str, Any]],
    theme_id: str,
) -> dict[str, Any]:
    """Project Money Flow state around multiple policy checkpoints, read-only.

    Detector history is never rewritten and policy evidence is never added to the
    Money Flow score. Missing post-checkpoint observations stay ``None`` rather
    than being converted to zero-day or COLD signals.
    """
    if not isinstance(theme_id, str) or not theme_id.strip():
        raise PolicyCheckpointTimelineError("theme_id must be a non-empty string")
    canonical_theme_id = theme_id.strip()
    history_copy = deepcopy(list(history))
    checkpoint_copy = deepcopy(list(checkpoints))

    timeline: list[dict[str, Any]] = []
    for checkpoint in _normalize_checkpoints(checkpoint_copy):
        checkpoint_date = _parse_date(checkpoint["policy_t0"], "policy_t0")
        summary = summarize_policy_state_sequence(
            history_copy,
            policy_t0=checkpoint["policy_t0"],
            theme_id=canonical_theme_id,
        )
        reliable_warming = summary["reliable_first_post_policy_warming"]
        reliable_inflow = summary["reliable_first_post_policy_inflow"]
        timeline.append(
            {
                "checkpoint_id": checkpoint["checkpoint_id"],
                "policy_t0": checkpoint["policy_t0"],
                "stage": checkpoint["stage"],
                "market_state_at_checkpoint": deepcopy(summary["state_at_or_before_policy"]),
                "next_reliable_warming": reliable_warming,
                "next_reliable_warming_days": _days_after(checkpoint_date, reliable_warming),
                "next_reliable_inflow": reliable_inflow,
                "next_reliable_inflow_days": _days_after(checkpoint_date, reliable_inflow),
                "post_policy_persistence": summary["post_policy_persistence"],
                "post_policy_reacceleration": summary["post_policy_reacceleration"],
                "limitations": checkpoint["limitations"],
            }
        )

    return {
        "theme_id": canonical_theme_id,
        "checkpoints": timeline,
        "policy_evidence_in_market_score": False,
    }
