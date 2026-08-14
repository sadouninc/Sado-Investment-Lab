from __future__ import annotations

from typing import Any, Iterable, Mapping

from scripts.queue_auto_promotion import select_next_work


def should_replenish_away_queue(*, user_mode: str, open_pr_count: int, worker_state: str) -> bool:
    """Return whether an AWAY run should invoke the pure queue selector."""
    return (
        user_mode == "AWAY"
        and open_pr_count == 0
        and worker_state in {"available", "idle"}
    )


def select_away_work(
    candidates: Iterable[Mapping[str, Any]],
    *,
    user_mode: str,
    open_pr_count: int,
    worker: str,
    worker_states: Mapping[str, str],
    active_owner_slices: Iterable[str] = (),
    active_paths: Iterable[str] = (),
) -> dict[str, Any]:
    """Run Queue Auto-Promotion only when AWAY replenishment conditions are met.

    The policy is intentionally read-only. It selects or fails closed; it does not
    assign Issues, dispatch Copilot, merge PRs, or change Authority state.
    """
    state = worker_states.get(worker, "blocked")
    if not should_replenish_away_queue(
        user_mode=user_mode, open_pr_count=open_pr_count, worker_state=state
    ):
        return {
            "status": "NO_REPLENISH_TRIGGER",
            "selected": None,
            "metrics": {"away_replenish_triggered": 0},
        }

    result = select_next_work(
        candidates,
        worker_states=worker_states,
        active_owner_slices=active_owner_slices,
        active_paths=active_paths,
    )
    result.setdefault("metrics", {})["away_replenish_triggered"] = 1
    return result
