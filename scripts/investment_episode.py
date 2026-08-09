from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import datetime
from typing import Any, Iterable, Mapping

from scripts.investment_decision_journal import validate_decision


class InvestmentEpisodeError(ValueError):
    pass


EPISODE_STATUSES = {"OPEN", "CLOSED", "PARTIAL_EXIT", "UNKNOWN"}
DATA_STATUSES = {"COMPLETE", "PARTIAL", "UNKNOWN"}
POSITION_STATES = {"OWNED", "NOT_OWNED", "UNKNOWN"}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvestmentEpisodeError(f"{field} must be a non-empty string")
    return value.strip()


def _dt(value: Any, field: str) -> datetime:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvestmentEpisodeError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise InvestmentEpisodeError(f"{field} must include timezone")
    return parsed


def deterministic_episode_id(security_code: str, entry_decision_ref: str) -> str:
    code = _text(security_code, "security_code")
    ref = _text(entry_decision_ref, "entry_decision_ref")
    digest = hashlib.sha256(f"{code}|{ref}".encode("utf-8")).hexdigest()[:12]
    return f"episode:{code}:{digest}"


def _validate_portfolio_confirmation(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise InvestmentEpisodeError("portfolio confirmation must be an object")
    out = deepcopy(dict(value))
    out["security_code"] = _text(out.get("security_code"), "portfolio.security_code")
    out["as_of"] = _text(out.get("as_of"), "portfolio.as_of")
    _dt(out["as_of"], "portfolio.as_of")
    out["source_ref"] = _text(out.get("source_ref"), "portfolio.source_ref")
    authority = _text(out.get("authority"), "portfolio.authority").upper()
    if authority != "CANONICAL":
        raise InvestmentEpisodeError("portfolio close/open authority must be CANONICAL")
    state = _text(out.get("position_state"), "portfolio.position_state").upper()
    if state not in POSITION_STATES:
        raise InvestmentEpisodeError("unsupported portfolio position_state")
    out["authority"] = authority
    out["position_state"] = state
    return out


def _explicit_refs(values: Iterable[Any], field: str) -> list[str]:
    refs = [_text(value, field) for value in values]
    if len(refs) != len(set(refs)):
        raise InvestmentEpisodeError(f"duplicate {field}")
    return sorted(refs)


def _gap(trade: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(trade, Mapping):
        raise InvestmentEpisodeError("trade must be an object")
    value = deepcopy(dict(trade))
    trade_ref = _text(value.get("trade_ref"), "trade.trade_ref")
    code = _text(value.get("security_code"), "trade.security_code")
    executed_at = _text(value.get("executed_at"), "trade.executed_at")
    _dt(executed_at, "trade.executed_at")
    action = _text(value.get("action"), "trade.action").upper()
    if action not in {"BUY", "ADD", "REDUCE", "SELL"}:
        raise InvestmentEpisodeError("unsupported trade action")
    decision_ref = value.get("decision_ref")
    if decision_ref is not None:
        decision_ref = _text(decision_ref, "trade.decision_ref")
    return {
        "type": "UNJOURNALED_GAP",
        "trade_ref": trade_ref,
        "security_code": code,
        "executed_at": executed_at,
        "action": action,
        "decision_ref": decision_ref,
    }


def build_investment_episodes(
    decisions: Iterable[Mapping[str, Any]],
    *,
    portfolio_confirmations: Iterable[Mapping[str, Any]] = (),
    trades: Iterable[Mapping[str, Any]] = (),
    allocation_episode_refs: Mapping[str, Iterable[str]] | None = None,
    review_refs: Mapping[str, Iterable[str]] | None = None,
) -> dict[str, Any]:
    """Build a relation/read-model over immutable Decision Journal records.

    SELL never closes an episode by itself. Closure requires an explicit CANONICAL
    portfolio confirmation of NOT_OWNED at or after the SELL decision. Trades without
    an explicit Decision Journal ref are surfaced as UNJOURNALED_GAP and never used to
    invent owner reasoning or Decision records.
    """
    validated = [validate_decision(dict(item)) for item in decisions]
    validated.sort(key=lambda item: (_dt(item["decided_at"], "decided_at"), item["decision_id"]))
    by_ref = {item["decision_id"]: item for item in validated}
    if len(by_ref) != len(validated):
        raise InvestmentEpisodeError("duplicate decision_id")

    confirmations = [_validate_portfolio_confirmation(item) for item in portfolio_confirmations]
    confirmations.sort(key=lambda item: (_dt(item["as_of"], "portfolio.as_of"), item["source_ref"]))

    gaps = [_gap(item) for item in trades]
    known_decision_refs = set(by_ref)
    for gap in gaps:
        ref = gap["decision_ref"]
        if ref is not None and ref not in known_decision_refs:
            raise InvestmentEpisodeError("trade decision_ref is not present in Decision Journal input")
    gaps = [gap for gap in gaps if gap["decision_ref"] is None]

    allocation_map = allocation_episode_refs or {}
    review_map = review_refs or {}
    episodes: list[dict[str, Any]] = []
    open_by_code: dict[str, dict[str, Any]] = {}

    def closure_after(code: str, when: datetime) -> dict[str, Any] | None:
        matches = [
            item
            for item in confirmations
            if item["security_code"] == code
            and _dt(item["as_of"], "portfolio.as_of") >= when
            and item["position_state"] == "NOT_OWNED"
        ]
        return matches[0] if matches else None

    for decision in validated:
        action = decision["decision"]
        if action not in {"BUY", "ADD", "HOLD", "REDUCE", "SELL"}:
            continue
        code = decision["security_code"]
        current = open_by_code.get(code)

        if action == "BUY":
            if current is not None:
                # A second BUY cannot silently create a new episode while the prior one
                # is still open. Keep the relation explicit and data quality partial.
                current["decision_refs"].append(decision["decision_id"])
                current["data_status"] = "PARTIAL"
                continue
            episode = {
                "episode_id": deterministic_episode_id(code, decision["decision_id"]),
                "security_code": code,
                "opened_at": decision["decided_at"],
                "closed_at": None,
                "status": "OPEN",
                "decision_refs": [decision["decision_id"]],
                "entry_decision_ref": decision["decision_id"],
                "exit_decision_ref": None,
                "allocation_episode_refs": _explicit_refs(
                    allocation_map.get(decision["decision_id"], []), "allocation_episode_ref"
                ),
                "review_refs": _explicit_refs(review_map.get(decision["decision_id"], []), "review_ref"),
                "portfolio_authority_ref": None,
                "data_status": "COMPLETE",
            }
            episodes.append(episode)
            open_by_code[code] = episode
            continue

        if current is None:
            # Do not invent a missing BUY/entry Decision. The decision remains visible
            # as an orphan relation so downstream UI can show incomplete history.
            episode = {
                "episode_id": deterministic_episode_id(code, decision["decision_id"]),
                "security_code": code,
                "opened_at": decision["decided_at"],
                "closed_at": None,
                "status": "UNKNOWN",
                "decision_refs": [decision["decision_id"]],
                "entry_decision_ref": None,
                "exit_decision_ref": None,
                "allocation_episode_refs": _explicit_refs(
                    allocation_map.get(decision["decision_id"], []), "allocation_episode_ref"
                ),
                "review_refs": _explicit_refs(review_map.get(decision["decision_id"], []), "review_ref"),
                "portfolio_authority_ref": None,
                "data_status": "PARTIAL",
            }
            episodes.append(episode)
            continue

        current["decision_refs"].append(decision["decision_id"])
        current["allocation_episode_refs"] = sorted(set(current["allocation_episode_refs"] + list(allocation_map.get(decision["decision_id"], []))))
        current["review_refs"] = sorted(set(current["review_refs"] + list(review_map.get(decision["decision_id"], []))))

        if action == "REDUCE":
            current["status"] = "PARTIAL_EXIT"
        elif action == "SELL":
            confirmation = closure_after(code, _dt(decision["decided_at"], "decided_at"))
            if confirmation is None:
                current["status"] = "UNKNOWN"
                current["data_status"] = "PARTIAL"
            else:
                current["status"] = "CLOSED"
                current["closed_at"] = confirmation["as_of"]
                current["exit_decision_ref"] = decision["decision_id"]
                current["portfolio_authority_ref"] = confirmation["source_ref"]
                open_by_code.pop(code, None)

    for episode in episodes:
        episode["decision_refs"] = list(episode["decision_refs"])
        if episode["status"] not in EPISODE_STATUSES or episode["data_status"] not in DATA_STATUSES:
            raise InvestmentEpisodeError("invalid generated episode status")

    latest_by_security: dict[str, str] = {}
    for episode in episodes:
        latest_by_security[episode["security_code"]] = episode["episode_id"]

    return {
        "episodes": deepcopy(episodes),
        "unjournaled_gaps": deepcopy(gaps),
        "latest_episode_by_security": latest_by_security,
    }
