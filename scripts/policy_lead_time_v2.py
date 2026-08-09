from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any, Mapping


CLASSIFICATIONS = {
    "POLICY_LEADS",
    "MARKET_LEADS",
    "POLICY_CONFIRMATION",
    "REACCELERATION_AFTER_POLICY",
    "INCONCLUSIVE",
    "DATA_LIMITED",
}
DATA_QUALITY = {"OK", "PARTIAL", "LIMITED"}
CRITICAL_LIMITATIONS = {"INSUFFICIENT_LOOKBACK", "PARTIAL_SCORE_AXES"}


class PolicyLeadTimeError(ValueError):
    pass


def _date(value: Any, field: str, *, optional: bool = False) -> date | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip():
        raise PolicyLeadTimeError(f"{field} must be YYYY-MM-DD" + (" or null" if optional else ""))
    try:
        parsed = date.fromisoformat(value.strip())
    except ValueError as exc:
        raise PolicyLeadTimeError(f"{field} must be YYYY-MM-DD") from exc
    return parsed


def _date_text(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _days(policy: date, event: date | None) -> int | None:
    return None if event is None else (event - policy).days


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise PolicyLeadTimeError(f"{field} must be boolean")
    return value


def _limitations(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise PolicyLeadTimeError("limitations must be an array of non-empty strings")
    return sorted(set(item.strip().upper() for item in value))


def _first(*values: date | None) -> date | None:
    known = [value for value in values if value is not None]
    return min(known) if known else None


def evaluate_policy_lead_time_v2(record: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate policy/market lead relationship without changing Money Flow history.

    PR1 intentionally accepts two explicit post-policy observations supplied by a
    state-transition layer: ``post_policy_persistence`` and
    ``post_policy_reacceleration``. It does not infer them from first dates alone.
    PR2 can derive those booleans from the canonical state sequence later.
    """
    if not isinstance(record, Mapping):
        raise PolicyLeadTimeError("record must be an object")
    source = deepcopy(dict(record))

    policy = _date(source.get("policy_t0"), "policy_t0")
    assert policy is not None
    raw_warming = _date(source.get("raw_first_warming_date"), "raw_first_warming_date", optional=True)
    raw_inflow = _date(source.get("raw_first_inflow_date"), "raw_first_inflow_date", optional=True)
    reliable_warming = _date(
        source.get("reliable_first_warming_date"), "reliable_first_warming_date", optional=True
    )
    reliable_inflow = _date(
        source.get("reliable_first_inflow_date"), "reliable_first_inflow_date", optional=True
    )

    quality = str(source.get("data_quality") or "").strip().upper()
    if quality not in DATA_QUALITY:
        raise PolicyLeadTimeError("data_quality must be OK, PARTIAL, or LIMITED")
    limitations = _limitations(source.get("limitations", []))
    persistence = _bool(source.get("post_policy_persistence", False), "post_policy_persistence")
    reacceleration = _bool(
        source.get("post_policy_reacceleration", False), "post_policy_reacceleration"
    )
    if reacceleration and not persistence:
        # Reacceleration is itself a post-policy market observation; requiring the
        # persistence flag keeps PR1 input semantics explicit and auditable.
        raise PolicyLeadTimeError("post_policy_reacceleration requires post_policy_persistence")

    reliable_first = _first(reliable_warming, reliable_inflow)
    raw_first = _first(raw_warming, raw_inflow)

    data_limited = quality != "OK" or bool(CRITICAL_LIMITATIONS.intersection(limitations))
    if reliable_first is None:
        classification = "DATA_LIMITED" if (data_limited or limitations) else "INCONCLUSIVE"
    elif data_limited:
        classification = "DATA_LIMITED"
    elif reliable_first > policy:
        classification = "POLICY_LEADS"
    elif reliable_first < policy:
        if reacceleration:
            classification = "REACCELERATION_AFTER_POLICY"
        elif persistence:
            classification = "POLICY_CONFIRMATION"
        else:
            classification = "MARKET_LEADS"
    else:
        # Same-day ordering cannot be established from date precision alone.
        classification = "INCONCLUSIVE"

    return {
        "schema_version": 2,
        "policy_t0": policy.isoformat(),
        "raw_first": {
            "warming_date": _date_text(raw_warming),
            "inflow_date": _date_text(raw_inflow),
            "first_market_date": _date_text(raw_first),
            "policy_to_warming_days": _days(policy, raw_warming),
            "policy_to_inflow_days": _days(policy, raw_inflow),
        },
        "reliable_first": {
            "warming_date": _date_text(reliable_warming),
            "inflow_date": _date_text(reliable_inflow),
            "first_market_date": _date_text(reliable_first),
            "policy_to_warming_days": _days(policy, reliable_warming),
            "policy_to_inflow_days": _days(policy, reliable_inflow),
        },
        "classification": classification,
        "data_quality": quality,
        "limitations": limitations,
        "post_policy_persistence": persistence,
        "post_policy_reacceleration": reacceleration,
        "policy_evidence_in_market_score": False,
    }
