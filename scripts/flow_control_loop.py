from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from scripts.away_queue_policy import select_away_work
from scripts.flow_health_guard import active_implementation_wip, evaluate_flow_health
from scripts.queue_auto_promotion import select_next_work


@dataclass(frozen=True)
class DispatchLease:
    work_ref: str
    fallback_owner: str
    assigned_at: str
    lease_expires_at: str
    acknowledged_at: str | None = None
    owner_slice: str | None = None


def _parse_aware_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("dispatch lease timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def evaluate_dispatch_lease(
    raw: Mapping[str, Any] | DispatchLease | None,
    *,
    now: datetime,
) -> dict[str, Any]:
    """Return deterministic lease state without mutating assignment state."""
    if raw is None:
        return {
            "status": "NONE",
            "work_ref": None,
            "fallback_owner": None,
            "owner_slice": None,
            "unacked_age_minutes": None,
        }

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now_utc = now.astimezone(timezone.utc)

    try:
        lease = raw if isinstance(raw, DispatchLease) else DispatchLease(
            work_ref=str(raw["work_ref"]).strip(),
            fallback_owner=str(raw["fallback_owner"]).strip(),
            assigned_at=str(raw["assigned_at"]),
            lease_expires_at=str(raw["lease_expires_at"]),
            acknowledged_at=(
                None if raw.get("acknowledged_at") in {None, ""}
                else str(raw["acknowledged_at"])
            ),
            owner_slice=(
                None if raw.get("owner_slice") in {None, ""}
                else str(raw["owner_slice"]).strip()
            ),
        )
        if not lease.work_ref or not lease.fallback_owner:
            raise ValueError("dispatch lease requires nonblank work_ref and fallback_owner")
        assigned_at = _parse_aware_timestamp(lease.assigned_at)
        expires_at = _parse_aware_timestamp(lease.lease_expires_at)
        acknowledged_at = (
            None
            if lease.acknowledged_at is None
            else _parse_aware_timestamp(lease.acknowledged_at)
        )
    except (KeyError, TypeError, ValueError) as exc:
        return {
            "status": "INVALID",
            "work_ref": None,
            "fallback_owner": None,
            "owner_slice": None,
            "unacked_age_minutes": None,
            "error": str(exc),
        }

    if expires_at <= assigned_at:
        return {
            "status": "INVALID",
            "work_ref": lease.work_ref,
            "fallback_owner": lease.fallback_owner,
            "owner_slice": lease.owner_slice,
            "unacked_age_minutes": None,
            "error": "lease_expires_at must be after assigned_at",
        }

    age_minutes = max(0, int((now_utc - assigned_at).total_seconds() // 60))
    if acknowledged_at is not None:
        if acknowledged_at < assigned_at:
            return {
                "status": "INVALID",
                "work_ref": lease.work_ref,
                "fallback_owner": lease.fallback_owner,
                "owner_slice": lease.owner_slice,
                "unacked_age_minutes": None,
                "error": "acknowledged_at must not be before assigned_at",
            }
        if acknowledged_at > now_utc:
            return {
                "status": "INVALID",
                "work_ref": lease.work_ref,
                "fallback_owner": lease.fallback_owner,
                "owner_slice": lease.owner_slice,
                "unacked_age_minutes": None,
                "error": "acknowledged_at must not be in the future",
            }
        if acknowledged_at >= expires_at:
            return {
                "status": "EXPIRED",
                "work_ref": lease.work_ref,
                "fallback_owner": lease.fallback_owner,
                "owner_slice": lease.owner_slice,
                "unacked_age_minutes": age_minutes,
                "late_acknowledgement": True,
            }
        return {
            "status": "ACKNOWLEDGED",
            "work_ref": lease.work_ref,
            "fallback_owner": lease.fallback_owner,
            "owner_slice": lease.owner_slice,
            "unacked_age_minutes": None,
        }
    if now_utc >= expires_at:
        return {
            "status": "EXPIRED",
            "work_ref": lease.work_ref,
            "fallback_owner": lease.fallback_owner,
            "owner_slice": lease.owner_slice,
            "unacked_age_minutes": age_minutes,
        }
    return {
        "status": "ACTIVE",
        "work_ref": lease.work_ref,
        "fallback_owner": lease.fallback_owner,
        "owner_slice": lease.owner_slice,
        "unacked_age_minutes": age_minutes,
    }


def evaluate_and_select_flow_action(
    candidates: Iterable[Mapping[str, Any]],
    *,
    user_mode: str,
    worker: str,
    worker_states: Mapping[str, str],
    work_states: Iterable[str],
    ready_nonconflicting_count: int,
    last_durable_output_age_minutes: int | None,
    now: datetime,
    dispatch_lease: Mapping[str, Any] | DispatchLease | None = None,
    same_blocker_run_count: int = 0,
    active_owner_slices: Iterable[str] = (),
    active_paths: Iterable[str] = (),
) -> dict[str, Any]:
    """Closed-loop decision adapter: detect stall, then invoke #556 selector.

    The function remains write-free. Runtime callers must persist the decision and
    perform the selected routing action. This separation keeps GitHub mutation and
    Authority checks outside the pure decision core while preventing detector-only
    operation.
    """
    states = tuple(str(state) for state in work_states)
    active_wip = active_implementation_wip(states)
    lease = evaluate_dispatch_lease(dispatch_lease, now=now)
    worker_state = str(worker_states.get(worker, "unknown")).lower()

    dispatch_age = lease.get("unacked_age_minutes")
    health = evaluate_flow_health(
        {
            "user_mode": user_mode,
            "worker_state": worker_state,
            "work_states": states,
            "ready_nonconflicting_count": ready_nonconflicting_count,
            "last_durable_output_age_minutes": last_durable_output_age_minutes,
            "dispatch_unacked_age_minutes": dispatch_age,
            "same_blocker_run_count": same_blocker_run_count,
        }
    )

    reasons = list(health["reasons"])
    actions = list(health["actions"])
    if lease["status"] == "INVALID":
        if health["status"] == "PASS":
            health["status"] = "WARN"
        reasons.append("DISPATCH_LEASE_INVALID")
        actions.append("REPAIR_DISPATCH_LEASE")
    health["reasons"] = tuple(dict.fromkeys(reasons))
    health["actions"] = tuple(dict.fromkeys(actions))

    effective_owner_slices = set(active_owner_slices)
    if lease["status"] == "EXPIRED" and lease.get("owner_slice"):
        effective_owner_slices.discard(str(lease["owner_slice"]))

    route_actions = {
        "ROUTE_READY_WORK",
        "CHECK_QUEUE_REPLENISH",
        "REROUTE_SAME_RUN",
        "EXPIRE_OR_REROUTE_DISPATCH",
        "REROUTE_TO_AVAILABLE_WORKER",
    }
    routing = {
        "status": "NO_ROUTING_ACTION",
        "selected": None,
        "metrics": {"flow_routing_invoked": 0},
    }

    if route_actions.intersection(health["actions"]):
        # select_away_work intentionally requires the current worker to be
        # explicitly idle/available. If that state is stale/unknown/blocked,
        # route through the global safe selector instead of detecting a stall
        # and then silently refusing to select any work.
        if worker_state not in {"idle", "available"}:
            routing = select_next_work(
                candidates,
                worker_states=worker_states,
                active_owner_slices=effective_owner_slices,
                active_paths=active_paths,
            )
        else:
            routing = select_away_work(
                candidates,
                user_mode=user_mode,
                worker=worker,
                worker_states=worker_states,
                active_implementation_wip_count=active_wip,
                active_owner_slices=effective_owner_slices,
                active_paths=active_paths,
            )
        routing.setdefault("metrics", {})["flow_routing_invoked"] = 1

    return {
        "health": health,
        "dispatch_lease": lease,
        "routing": routing,
    }
