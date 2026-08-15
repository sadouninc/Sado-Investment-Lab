from __future__ import annotations

from typing import Any, Iterable, Mapping

from scripts.queue_auto_promotion import select_next_work


def should_replenish_away_queue(
    *,
    user_mode: str,
    worker_state: str,
    active_implementation_wip_count: int | None = None,
    open_pr_count: int | None = None,
) -> bool:
    """Return whether an AWAY run should invoke the pure queue selector.

    Review/CI/Gate-wait PRs do not consume implementation capacity. New callers
    must pass ``active_implementation_wip_count``. ``open_pr_count`` remains only
    as a fail-safe compatibility input for older callers until they migrate.
    """
    if active_implementation_wip_count is None:
        if open_pr_count is None:
            return False
        active_implementation_wip_count = open_pr_count

    return (
        user_mode == "AWAY"
        and active_implementation_wip_count == 0
        and worker_state in {"available", "idle"}
    )


def select_away_work(
    candidates: Iterable[Mapping[str, Any]],
    *,
    user_mode: str,
    worker: str,
    worker_states: Mapping[str, str],
    active_implementation_wip_count: int | None = None,
    open_pr_count: int | None = None,
    active_owner_slices: Iterable[str] = (),
    active_paths: Iterable[str] = (),
) -> dict[str, Any]:
    """Run Queue Auto-Promotion only when AWAY replenishment conditions are met.

    The policy is intentionally read-only. It selects or fails closed; it does not
    assign Issues, dispatch agents, merge PRs, or change Authority state.
    """
    state = worker_states.get(worker, "blocked")
    if not should_replenish_away_queue(
        user_mode=user_mode,
        worker_state=state,
        active_implementation_wip_count=active_implementation_wip_count,
        open_pr_count=open_pr_count,
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
