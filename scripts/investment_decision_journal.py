from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from typing import Any

DECISIONS = {"START_WATCH","START_RESEARCH","BUY","ADD","HOLD","REDUCE","SELL","PASS","REENTER_WATCH"}
CONFIDENCE = {"LOW","MEDIUM","HIGH"}
DECISION_QUALITY = {"GOOD","MIXED","POOR","NOT_YET_JUDGABLE"}
OUTCOMES = {"POSITIVE","NEGATIVE","FLAT","NOT_RELEVANT"}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _dt(value: Any, field: str) -> datetime:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include timezone")
    return parsed


def deterministic_decision_id(security_code: str, decided_at: str, decision: str, actor: str) -> str:
    code = _text(security_code, "security_code")
    at = _dt(decided_at, "decided_at").isoformat()
    action = _text(decision, "decision").upper()
    owner = _text(actor, "actor").upper()
    digest = hashlib.sha256(f"{code}|{at}|{action}|{owner}".encode()).hexdigest()[:12]
    return f"decision:{code}:{digest}"


def validate_decision(snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be an object")
    out = deepcopy(snapshot)
    code = _text(out.get("security_code"), "security_code")
    _dt(out.get("decided_at"), "decided_at")
    action = _text(out.get("decision"), "decision").upper()
    if action not in DECISIONS:
        raise ValueError("unsupported decision")
    actor = _text(out.get("actor"), "actor")
    confidence = _text(out.get("confidence"), "confidence").upper()
    if confidence not in CONFIDENCE:
        raise ValueError("unsupported confidence")
    owner = out.get("owner_judgment")
    system = out.get("system_snapshot")
    if not isinstance(owner, dict) or not isinstance(system, dict):
        raise ValueError("owner_judgment and system_snapshot must be objects")
    for field in ("why_now", "biggest_risk", "what_changes_my_mind"):
        _text(owner.get(field), f"owner_judgment.{field}")
    retrospective = out.get("retrospective_note", False)
    if not isinstance(retrospective, bool):
        raise ValueError("retrospective_note must be boolean")
    expected = deterministic_decision_id(code, out["decided_at"], action, actor)
    if out.get("decision_id") not in (None, expected):
        raise ValueError("decision_id does not match deterministic identity")
    out["decision_id"] = expected
    out["decision"] = action
    out["confidence"] = confidence
    out["retrospective_note"] = retrospective
    refs = out.get("evidence_refs", [])
    if not isinstance(refs, list) or any(not isinstance(x, str) or not x.strip() for x in refs):
        raise ValueError("evidence_refs must be non-empty strings")
    return out


def capture_decision(snapshot: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    current = validate_decision(snapshot)
    if existing is None:
        return current
    prior = validate_decision(existing)
    if prior != current:
        raise ValueError("immutable decision snapshot conflict")
    return prior


def validate_review(review: dict[str, Any], *, decision_id: str) -> dict[str, Any]:
    if not isinstance(review, dict):
        raise ValueError("review must be an object")
    out = deepcopy(review)
    if _text(out.get("decision_id"), "decision_id") != _text(decision_id, "decision_id"):
        raise ValueError("review decision_id mismatch")
    _dt(out.get("reviewed_at"), "reviewed_at")
    _text(out.get("trigger"), "trigger")
    _text(out.get("what_happened"), "what_happened")
    quality = _text(out.get("decision_quality"), "decision_quality").upper()
    outcome = _text(out.get("outcome"), "outcome").upper()
    if quality not in DECISION_QUALITY:
        raise ValueError("unsupported decision_quality")
    if outcome not in OUTCOMES:
        raise ValueError("unsupported outcome")
    tags = out.get("mistake_tags", [])
    if not isinstance(tags, list) or any(not isinstance(x, str) or not x.strip() for x in tags):
        raise ValueError("mistake_tags must be strings")
    out["decision_quality"] = quality
    out["outcome"] = outcome
    return out


def dumps(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
