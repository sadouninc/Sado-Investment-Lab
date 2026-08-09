from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any, Iterable, Mapping

STATES = {"COLD", "WARMING", "INFLOW", "HOT", "OVERHEATED"}
STATE_RANK = {"COLD": 0, "WARMING": 1, "INFLOW": 2, "HOT": 3, "OVERHEATED": 4}
REQUIRED_SCORE_AXES = {"relative_strength", "activity", "breadth", "heat", "acceleration"}


class PolicyStateSequenceError(ValueError):
    pass


def _parse_date(value: Any, field: str) -> date:
    if not isinstance(value, str) or not value.strip():
        raise PolicyStateSequenceError(f"{field} must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise PolicyStateSequenceError(f"{field} must be YYYY-MM-DD") from exc


def _is_reliable(row: Mapping[str, Any]) -> bool:
    if str(row.get("data_completeness") or "").upper() != "OK":
        return False
    scores = row.get("scores")
    if not isinstance(scores, Mapping):
        return False
    return all(axis in scores and scores.get(axis) is not None for axis in REQUIRED_SCORE_AXES)


def _normalize(history: Iterable[Mapping[str, Any]], *, theme_id: str | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}
    for raw in history:
        if not isinstance(raw, Mapping):
            raise PolicyStateSequenceError("history rows must be objects")
        if theme_id is not None and str(raw.get("id") or "") != theme_id:
            continue
        if raw.get("kind") not in (None, "THEME"):
            continue
        as_of = _parse_date(raw.get("as_of"), "history.as_of").isoformat()
        state = str(raw.get("state") or "").upper()
        if state not in STATES:
            raise PolicyStateSequenceError(f"unsupported state: {state}")
        row = {
            "as_of": as_of,
            "state": state,
            "data_completeness": str(raw.get("data_completeness") or "UNKNOWN").upper(),
            "reliable": _is_reliable(raw),
        }
        previous = seen.get(as_of)
        if previous is not None and previous != row:
            raise PolicyStateSequenceError(f"conflicting history rows for {as_of}")
        seen[as_of] = row
    rows = sorted(seen.values(), key=lambda row: row["as_of"])
    return rows


def _latest(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return deepcopy(rows[-1]) if rows else None


def _first_state(rows: list[dict[str, Any]], state: str) -> str | None:
    for row in rows:
        if row["state"] == state:
            return str(row["as_of"])
    return None


def _strongest(rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return None
    return max((row["state"] for row in rows), key=lambda state: STATE_RANK[state])


def summarize_policy_state_sequence(
    history: Iterable[Mapping[str, Any]],
    *,
    policy_t0: str,
    theme_id: str | None = None,
) -> dict[str, Any]:
    """Summarize observed Money Flow states around a policy checkpoint.

    This is a read-only projection. It never rewrites Detector history and never
    promotes PARTIAL observations into reliable ones.
    """
    policy = _parse_date(policy_t0, "policy_t0")
    rows = _normalize(history, theme_id=theme_id)
    before = [row for row in rows if _parse_date(row["as_of"], "history.as_of") < policy]
    at_or_before = [row for row in rows if _parse_date(row["as_of"], "history.as_of") <= policy]
    after = [row for row in rows if _parse_date(row["as_of"], "history.as_of") > policy]

    reliable_before = [row for row in before if row["reliable"]]
    reliable_after = [row for row in after if row["reliable"]]
    signal_before = [row for row in reliable_before if STATE_RANK[row["state"]] >= STATE_RANK["WARMING"]]
    signal_after = [row for row in reliable_after if STATE_RANK[row["state"]] >= STATE_RANK["WARMING"]]

    first_signal_before = signal_before[0] if signal_before else None
    cooled_after_pre_signal = False
    if first_signal_before is not None:
        first_date = _parse_date(first_signal_before["as_of"], "history.as_of")
        cooled_after_pre_signal = any(
            row["state"] == "COLD" and _parse_date(row["as_of"], "history.as_of") > first_date
            for row in at_or_before
        )

    post_policy_persistence = bool(signal_before and signal_after)
    post_policy_reacceleration = bool(signal_before and cooled_after_pre_signal and signal_after)

    return {
        "policy_t0": policy.isoformat(),
        "theme_id": theme_id,
        "pre_policy_state": _latest(before),
        "state_at_or_before_policy": _latest(at_or_before),
        "first_post_policy_warming": _first_state(after, "WARMING"),
        "first_post_policy_inflow": _first_state(after, "INFLOW"),
        "reliable_first_post_policy_warming": _first_state(reliable_after, "WARMING"),
        "reliable_first_post_policy_inflow": _first_state(reliable_after, "INFLOW"),
        "strongest_pre_policy_state": _strongest(before),
        "strongest_post_policy_state": _strongest(after),
        "reliable_strongest_pre_policy_state": _strongest(reliable_before),
        "reliable_strongest_post_policy_state": _strongest(reliable_after),
        "post_policy_persistence": post_policy_persistence,
        "post_policy_reacceleration": post_policy_reacceleration,
        "sequence": deepcopy(rows),
        "policy_evidence_in_market_score": False,
    }
