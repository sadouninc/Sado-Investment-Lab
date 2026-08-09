from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


class DecisionTimingError(ValueError):
    pass


MILESTONES = (
    "first_discovered_at",
    "research_started_at",
    "first_current_research_at",
    "hypothesis_created_at",
    "valuation_created_at",
    "first_decision_at",
    "latest_material_evidence_at",
    "review_started_at",
    "decision_reconsidered_at",
)

LATENCY_PAIRS = {
    "discovery_to_research_hours": ("first_discovered_at", "research_started_at"),
    "research_to_hypothesis_hours": ("research_started_at", "hypothesis_created_at"),
    "hypothesis_to_decision_hours": ("hypothesis_created_at", "first_decision_at"),
    "evidence_to_research_refresh_hours": ("latest_material_evidence_at", "first_current_research_at"),
    "material_change_to_review_hours": ("latest_material_evidence_at", "review_started_at"),
    "invalidation_to_decision_change_hours": ("latest_material_evidence_at", "decision_reconsidered_at"),
}

ALLOWED_KINDS = {
    "DISCOVERY",
    "RESEARCH_STARTED",
    "CURRENT_RESEARCH",
    "HYPOTHESIS_CREATED",
    "VALUATION_CREATED",
    "DECISION",
    "MATERIAL_EVIDENCE",
    "REVIEW_STARTED",
    "DECISION_RECONSIDERED",
}

KIND_TO_MILESTONE = {
    "DISCOVERY": "first_discovered_at",
    "RESEARCH_STARTED": "research_started_at",
    "CURRENT_RESEARCH": "first_current_research_at",
    "HYPOTHESIS_CREATED": "hypothesis_created_at",
    "VALUATION_CREATED": "valuation_created_at",
    "DECISION": "first_decision_at",
    "MATERIAL_EVIDENCE": "latest_material_evidence_at",
    "REVIEW_STARTED": "review_started_at",
    "DECISION_RECONSIDERED": "decision_reconsidered_at",
}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionTimingError(f"{field} must be a non-empty string")
    return value.strip()


def _dt(value: Any, field: str) -> datetime:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DecisionTimingError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise DecisionTimingError(f"{field} must include timezone")
    return parsed


def _event(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise DecisionTimingError("timing event must be an object")
    out = deepcopy(dict(value))
    out["kind"] = _text(out.get("kind"), "event.kind").upper()
    if out["kind"] not in ALLOWED_KINDS:
        raise DecisionTimingError("unsupported timing event kind")
    out["observed_at"] = _text(out.get("observed_at"), "event.observed_at")
    _dt(out["observed_at"], "event.observed_at")
    out["source_ref"] = _text(out.get("source_ref"), "event.source_ref")
    out["authority"] = _text(out.get("authority"), "event.authority").upper()
    if out["authority"] != "EXPLICIT":
        raise DecisionTimingError("timing events must have EXPLICIT authority")
    out["material"] = bool(out.get("material", True))
    out["presentation_only"] = bool(out.get("presentation_only", False))
    return out


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _hours(start: str | None, end: str | None) -> float | None:
    if start is None or end is None:
        return None
    delta = _dt(end, "latency.end") - _dt(start, "latency.start")
    if delta.total_seconds() < 0:
        return None
    return round(delta.total_seconds() / 3600.0, 6)


def build_timing_projection(
    episode: Mapping[str, Any],
    events: Iterable[Mapping[str, Any]],
    *,
    as_of: str,
    generated_at: str | None = None,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project explicit event timestamps onto one Investment Episode.

    This is a read model only. It never infers timestamps from commits, transactions,
    prices, ordering, or later knowledge. Events after ``as_of`` are excluded to avoid
    look-ahead. Presentation-only and non-material MATERIAL_EVIDENCE records do not
    create material-change milestones.
    """
    if not isinstance(episode, Mapping):
        raise DecisionTimingError("episode must be an object")
    episode_ref = _text(episode.get("episode_id"), "episode.episode_id")
    security_code = _text(episode.get("security_code"), "episode.security_code")
    cutoff = _dt(as_of, "as_of")
    generated = _dt(generated_at, "generated_at") if generated_at is not None else cutoff

    accepted: list[dict[str, Any]] = []
    for raw in events:
        item = _event(raw)
        if _dt(item["observed_at"], "event.observed_at") > cutoff:
            continue
        if item.get("episode_ref") not in (None, episode_ref):
            continue
        if item.get("security_code") not in (None, security_code):
            continue
        if item["presentation_only"]:
            continue
        if item["kind"] == "MATERIAL_EVIDENCE" and not item["material"]:
            continue
        accepted.append(item)

    accepted.sort(key=lambda item: (_dt(item["observed_at"], "event.observed_at"), item["source_ref"], item["kind"]))
    milestones: dict[str, str | None] = {name: None for name in MILESTONES}
    source_refs: dict[str, str] = {}

    for item in accepted:
        milestone = KIND_TO_MILESTONE[item["kind"]]
        current = milestones[milestone]
        when = item["observed_at"]
        if milestone == "latest_material_evidence_at":
            if current is None or _dt(when, "event.observed_at") > _dt(current, milestone):
                milestones[milestone] = when
                source_refs[milestone] = item["source_ref"]
        elif current is None:
            milestones[milestone] = when
            source_refs[milestone] = item["source_ref"]

    latencies = {name: _hours(milestones[start], milestones[end]) for name, (start, end) in LATENCY_PAIRS.items()}
    missing = [name for name in MILESTONES if milestones[name] is None]
    core = ("research_started_at", "hypothesis_created_at", "first_decision_at")
    if all(milestones[name] is None for name in core):
        status = "INSUFFICIENT_DATA"
    elif missing:
        status = "PARTIAL"
    else:
        status = "COMPLETE"

    return {
        "episode_ref": episode_ref,
        "security_code": security_code,
        "generated_at": _iso(generated),
        "as_of": _iso(cutoff),
        "milestones": milestones,
        "latencies": latencies,
        "context": deepcopy(dict(context or {})),
        "status": status,
        "missing_milestones": missing,
        "source_refs": [{"milestone": name, "source_ref": source_refs[name]} for name in sorted(source_refs)],
    }


def aggregate_latency(values: Iterable[float | None]) -> dict[str, Any]:
    """Small-sample-safe summary; never labels a latency good/bad or a trend for N<3."""
    observed = sorted(float(value) for value in values if value is not None)
    n = len(observed)
    if n == 0:
        return {"n": 0, "status": "INSUFFICIENT_DATA", "median_hours": None, "trend": None}
    middle = n // 2
    median = observed[middle] if n % 2 else (observed[middle - 1] + observed[middle]) / 2
    return {
        "n": n,
        "status": "INSUFFICIENT_DATA" if n < 3 else "OBSERVED",
        "median_hours": median,
        "trend": None,
    }
