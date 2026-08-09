from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


class DecisionReviewComparisonError(ValueError):
    pass


_HYPOTHESIS_ORDER = {
    "BROKEN": 0,
    "WEAKENING": 1,
    "NEEDS_REVIEW": 2,
    "INTACT": 3,
    "STRENGTHENING": 4,
}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionReviewComparisonError(f"{field} must be a non-empty string")
    return value.strip()


def _num(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DecisionReviewComparisonError("numeric comparison value must be number or null")
    return float(value)


def _append(changes: list[dict[str, Any]], change_type: str, *, label_ja: str, before: Any, now: Any, priority: int) -> None:
    changes.append({
        "type": change_type,
        "label_ja": label_ja,
        "before": deepcopy(before),
        "now": deepcopy(now),
        "priority": priority,
    })


def _status_missing(component: Mapping[str, Any] | None) -> bool:
    if component is None:
        return True
    values = {
        str(component.get("status") or "").upper(),
        str(component.get("freshness") or "").upper(),
    }
    return bool(values & {"MISSING", "UNAVAILABLE", "UNKNOWN", "STALE"})


def _compare_earnings(before: Mapping[str, Any], now: Mapping[str, Any], changes: list[dict[str, Any]]) -> None:
    b = _num(before.get("base"))
    n = _num(now.get("base"))
    if b is None or n is None or b == n:
        return
    _append(
        changes,
        "EARNINGS_REVISION_UP" if n > b else "EARNINGS_REVISION_DOWN",
        label_ja="Base利益前提",
        before=b,
        now=n,
        priority=80,
    )


def _compare_valuation(before: Mapping[str, Any], now: Mapping[str, Any], changes: list[dict[str, Any]]) -> None:
    b = _num(before.get("forward_per"))
    n = _num(now.get("forward_per"))
    if b is None or n is None or b == n:
        return
    _append(
        changes,
        "VALUATION_CHEAPER" if n < b else "VALUATION_RICHER",
        label_ja="Forward PER",
        before=b,
        now=n,
        priority=60,
    )


def _compare_hypothesis(before: Mapping[str, Any], now: Mapping[str, Any], changes: list[dict[str, Any]]) -> None:
    b = before.get("health")
    n = now.get("health")
    if b is None or n is None or b == n:
        return
    b_key = str(b).upper()
    n_key = str(n).upper()
    if b_key not in _HYPOTHESIS_ORDER or n_key not in _HYPOTHESIS_ORDER:
        return
    if n_key == "BROKEN":
        kind, priority = "HYPOTHESIS_BROKEN", 100
    elif _HYPOTHESIS_ORDER[n_key] > _HYPOTHESIS_ORDER[b_key]:
        kind, priority = "HYPOTHESIS_STRENGTHENED", 70
    else:
        kind, priority = "HYPOTHESIS_WEAKENED", 90
    _append(changes, kind, label_ja="投資仮説", before=b_key, now=n_key, priority=priority)


def _compare_expectations(before: Mapping[str, Any], now: Mapping[str, Any], changes: list[dict[str, Any]]) -> None:
    b = _num(before.get("sado_vs_consensus_gap_pct"))
    n = _num(now.get("sado_vs_consensus_gap_pct"))
    if b is None or n is None or b == n:
        return
    kind = "EXPECTATION_GAP_WIDENED" if abs(n) > abs(b) else "EXPECTATION_GAP_NARROWED"
    _append(changes, kind, label_ja="Sado予想とConsensusの差", before=b, now=n, priority=50)


def build_decision_review_comparison(
    decision: Mapping[str, Any],
    decision_snapshot: Mapping[str, Any],
    current: Mapping[str, Any],
    *,
    max_change_summaries: int = 5,
) -> dict[str, Any]:
    """Compare immutable decision-time snapshot with a current read model.

    This function does not score Decision Quality, infer BUY/SELL actions, or invent
    materiality thresholds for numeric changes. Numeric changes are reported as deltas;
    deterministic state transitions are classified explicitly.
    """
    if not 1 <= max_change_summaries <= 5:
        raise DecisionReviewComparisonError("max_change_summaries must be between 1 and 5")
    decision_ref = _text(decision_snapshot.get("decision_ref"), "decision_snapshot.decision_ref")
    if decision.get("decision_id") != decision_ref:
        raise DecisionReviewComparisonError("decision_ref mismatch")
    code = _text(decision_snapshot.get("security_code"), "decision_snapshot.security_code")
    if str(decision.get("security_code")) != code or str(current.get("security_code")) != code:
        raise DecisionReviewComparisonError("security_code mismatch")

    owner = decision.get("owner_judgment")
    if not isinstance(owner, Mapping):
        raise DecisionReviewComparisonError("decision.owner_judgment must be an object")

    before = deepcopy(dict(decision_snapshot))
    now = deepcopy(dict(current))
    changes: list[dict[str, Any]] = []

    _compare_earnings(before.get("valuation") or {}, now.get("valuation") or {}, changes)
    _compare_valuation(before.get("valuation") or {}, now.get("valuation") or {}, changes)
    _compare_hypothesis(before.get("hypothesis") or {}, now.get("hypothesis") or {}, changes)
    _compare_expectations(before.get("expectations") or {}, now.get("expectations") or {}, changes)

    for component in ("portfolio", "market_price", "research", "valuation", "hypothesis", "expectations"):
        current_component = now.get(component)
        if isinstance(current_component, Mapping) and _status_missing(current_component):
            _append(changes, "SOURCE_STALE" if str(current_component.get("status") or current_component.get("freshness") or "").upper() == "STALE" else "SOURCE_MISSING", label_ja=f"{component}データ", before=(before.get(component) or {}).get("ref") if isinstance(before.get(component), Mapping) else None, now=deepcopy(current_component), priority=85)

    for checkpoint in now.get("checkpoints", []) or []:
        if not isinstance(checkpoint, Mapping):
            continue
        status = str(checkpoint.get("status") or "").upper()
        if status == "DUE":
            _append(changes, "CHECKPOINT_DUE", label_ja="確認予定", before=None, now=checkpoint.get("ref"), priority=75)
        elif status == "OCCURRED_UNHANDLED":
            _append(changes, "CHECKPOINT_OCCURRED_UNHANDLED", label_ja="未処理イベント", before=None, now=checkpoint.get("ref"), priority=95)

    changes.sort(key=lambda item: (-item["priority"], item["type"], str(item.get("label_ja"))))
    summary = changes[:max_change_summaries]
    return {
        "decision_ref": decision_ref,
        "security_code": code,
        "owner_context": {
            "why_now": owner.get("why_now"),
            "biggest_risk": owner.get("biggest_risk"),
            "what_changes_my_mind": owner.get("what_changes_my_mind"),
        },
        "at_decision": before,
        "now": now,
        "changes": changes,
        "review_summary": summary,
        "opportunity_set_ref": before.get("opportunity_set_ref"),
        "decision_quality": None,
        "outcome": None,
        "trade_action": None,
        "material_threshold": "UNSET",
    }
