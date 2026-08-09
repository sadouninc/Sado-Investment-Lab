from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping

from scripts.investment_decision_journal import validate_decision
from scripts.opportunity_cost_ledger import validate_opportunity_set


class OpportunityCostAdapterError(ValueError):
    pass


_SUPPORTED_DECISIONS = {"BUY", "ADD", "HOLD", "REDUCE", "SELL", "PASS"}
_RESEARCH_STATUS_TO_DATA_STATUS = {
    "CURRENT": "CURRENT",
    "STALE": "STALE",
    "NOT_STARTED": "MISSING",
    "IN_PROGRESS": "UNKNOWN",
}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OpportunityCostAdapterError(f"{field} must be a non-empty string")
    return value.strip()


def _dt(value: Any, field: str) -> datetime:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OpportunityCostAdapterError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise OpportunityCostAdapterError(f"{field} must include timezone")
    return parsed


def _validate_selector_snapshot(selector_snapshot: Mapping[str, Any], *, decided_at: str) -> dict[str, Any]:
    if not isinstance(selector_snapshot, Mapping):
        raise OpportunityCostAdapterError("selector_snapshot must be an object")
    snapshot = deepcopy(dict(selector_snapshot))
    ref = _text(snapshot.get("ref"), "selector_snapshot.ref")
    captured_at = _dt(snapshot.get("captured_at"), "selector_snapshot.captured_at")
    if captured_at > _dt(decided_at, "decided_at"):
        raise OpportunityCostAdapterError("Candidate Selector snapshot must not be later than the decision")
    data = snapshot.get("data")
    if not isinstance(data, Mapping):
        raise OpportunityCostAdapterError("selector_snapshot.data must be an object")
    ranked = data.get("ranked_candidates")
    if not isinstance(ranked, list):
        raise OpportunityCostAdapterError("selector_snapshot.data.ranked_candidates must be a list")
    snapshot["ref"] = ref
    snapshot["data"] = deepcopy(dict(data))
    return snapshot


def _candidate_locator(selector_ref: str, *, rank: int, security_code: str) -> str:
    return f"{selector_ref}#rank:{rank}:security:{security_code}"


def _candidate_alternative(
    row: Mapping[str, Any],
    *,
    selector_ref: str,
    rank: int,
    action: str,
) -> dict[str, Any]:
    code = str(row.get("security_code") or "").strip()
    if not code or not code.isdigit() or len(code) != 4:
        raise OpportunityCostAdapterError("ranked Candidate alternative requires a 4-digit security_code")
    reason = str(row.get("selection_reason") or "").strip()
    if not reason:
        raise OpportunityCostAdapterError("ranked Candidate alternative requires selection_reason")
    research_status = str(row.get("research_status") or "").upper()
    if research_status not in _RESEARCH_STATUS_TO_DATA_STATUS:
        raise OpportunityCostAdapterError(f"unsupported Candidate research_status: {research_status}")

    item: dict[str, Any] = {
        "security_code": code,
        "action": action,
        "source": "CANDIDATE_SELECTOR",
        "candidate_ref": str(row.get("candidate_ref") or _candidate_locator(selector_ref, rank=rank, security_code=code)),
        "rank_at_decision": rank,
        "why_feasible": reason,
        "data_status": _RESEARCH_STATUS_TO_DATA_STATUS[research_status],
    }
    for field in ("research_ref", "valuation_ref", "hypothesis_ref"):
        if row.get(field) is not None:
            item[field] = str(row[field])
    return item


def _owner_named_alternative(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise OpportunityCostAdapterError("owner_named alternative must be an object")
    item = deepcopy(dict(raw))
    item["source"] = "OWNER_NAMED"
    item["security_code"] = _text(item.get("security_code"), "owner_named.security_code")
    item["action"] = _text(item.get("action"), "owner_named.action").upper()
    item["why_feasible"] = _text(item.get("why_feasible"), "owner_named.why_feasible")
    item["data_status"] = _text(item.get("data_status", "UNKNOWN"), "owner_named.data_status").upper()
    item.pop("rank_at_decision", None)
    item.pop("candidate_ref", None)
    return item


def build_opportunity_set_from_decision(
    decision: Mapping[str, Any],
    *,
    selector_snapshot: Mapping[str, Any],
    top_n: int = 3,
    owner_named_alternatives: list[Mapping[str, Any]] | None = None,
    capital_context: Mapping[str, Any] | None = None,
    include_cash: bool = True,
    candidate_action: str = "BUY",
) -> dict[str, Any]:
    """Build an ex-ante Opportunity Set from a Decision and captured Candidate Selector snapshot.

    The selector snapshot must have an explicit timezone-aware captured_at no later than
    the Decision. Candidate ranking is copied from that snapshot and never recomputed.
    Owner-named alternatives must be explicit inputs; they are never inferred from later
    winners or current market data.
    """
    validated_decision = validate_decision(dict(decision))
    decision_action = validated_decision["decision"]
    if decision_action not in _SUPPORTED_DECISIONS:
        raise OpportunityCostAdapterError(f"Decision type is outside #186 PR2 scope: {decision_action}")
    if isinstance(top_n, bool) or not isinstance(top_n, int) or top_n < 0:
        raise OpportunityCostAdapterError("top_n must be a non-negative integer")
    candidate_action = _text(candidate_action, "candidate_action").upper()
    if candidate_action not in {"BUY", "ADD", "HOLD", "REDUCE", "SELL", "PASS"}:
        raise OpportunityCostAdapterError("unsupported candidate_action")

    snapshot = _validate_selector_snapshot(selector_snapshot, decided_at=validated_decision["decided_at"])
    chosen_code = validated_decision["security_code"]
    alternatives: list[dict[str, Any]] = []

    for rank, raw in enumerate(snapshot["data"]["ranked_candidates"], start=1):
        if len([item for item in alternatives if item.get("source") == "CANDIDATE_SELECTOR"]) >= top_n:
            break
        if not isinstance(raw, Mapping):
            raise OpportunityCostAdapterError("ranked_candidates entries must be objects")
        code = str(raw.get("security_code") or "").strip()
        if not code:
            continue
        if code == chosen_code and candidate_action == decision_action:
            continue
        alternatives.append(
            _candidate_alternative(raw, selector_ref=snapshot["ref"], rank=rank, action=candidate_action)
        )

    for raw in owner_named_alternatives or []:
        alternatives.append(_owner_named_alternative(raw))

    if include_cash and decision_action != "CASH":
        alternatives.append(
            {
                "security_code": None,
                "action": "CASH",
                "source": "SYSTEM",
                "why_feasible": "資本を温存する選択肢",
                "data_status": "CURRENT",
            }
        )

    if not alternatives:
        raise OpportunityCostAdapterError("Opportunity Set requires at least one ex-ante alternative")

    opportunity = {
        "decision_ref": validated_decision["decision_id"],
        "captured_at": validated_decision["decided_at"],
        "actor": validated_decision["actor"],
        "capital_context": deepcopy(dict(capital_context or {})),
        "chosen_action": {
            "security_code": chosen_code,
            "action": decision_action,
            "decision_ref": validated_decision["decision_id"],
        },
        "alternatives": alternatives,
        "selection_rule": "TOP_N_RANKED_AT_DECISION_PLUS_OWNER_NAMED",
        "snapshot_freshness": str(snapshot["data"].get("as_of") or snapshot["captured_at"]),
    }
    return validate_opportunity_set(opportunity)


def opportunity_set_snapshot_source(opportunity_set: Mapping[str, Any]) -> dict[str, Any]:
    """Project an Opportunity Set into #133 PR2 source-record shape without duplication."""
    validated = validate_opportunity_set(dict(opportunity_set))
    return {
        "ref": validated["opportunity_set_id"],
        "captured_at": validated["captured_at"],
        "data": {"opportunity_set_id": validated["opportunity_set_id"]},
    }
