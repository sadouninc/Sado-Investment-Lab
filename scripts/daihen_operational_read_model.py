from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping


class DaihenOperationalReadModelError(ValueError):
    """Raised when the #257 integration read-model contract is violated."""


SECTION_NAMES = (
    "review_context",
    "earnings_driver",
    "valuation",
    "expectations",
    "hypothesis",
    "portfolio_preflight",
    "decision_history",
)

SECTION_STATUSES = {"OK", "PARTIAL", "NEEDS_REVIEW", "UNAVAILABLE", "NOT_RUN"}
FRESHNESS_STATUSES = {"CURRENT", "STALE", "UNKNOWN"}
PROHIBITED_KEYS = {
    "recommendation",
    "trade_recommendation",
    "buy_sell_recommendation",
    "auto_decision",
}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DaihenOperationalReadModelError(f"{field} must be a non-empty string")
    return value.strip()


def _iso_datetime(value: Any, field: str) -> str:
    text = _text(value, field)
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise DaihenOperationalReadModelError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DaihenOperationalReadModelError(f"{field} must include timezone")
    return text


def _reject_prohibited(value: Any, *, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if key_text in PROHIBITED_KEYS:
                raise DaihenOperationalReadModelError(
                    f"{path}.{key_text} is prohibited: read model must not generate BUY/SELL decisions"
                )
            _reject_prohibited(child, path=f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_prohibited(child, path=f"{path}[{index}]")


def _source_refs(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise DaihenOperationalReadModelError(f"{field} must be an array")
    refs: list[str] = []
    for item in value:
        ref = _text(item, field)
        if ref not in refs:
            refs.append(ref)
    return sorted(refs)


def _section(name: str, raw: Any) -> dict[str, Any]:
    if raw is None:
        return {"status": "UNAVAILABLE", "freshness": "UNKNOWN", "source_refs": []}
    if not isinstance(raw, Mapping):
        raise DaihenOperationalReadModelError(f"{name} must be an object")

    out = deepcopy(dict(raw))
    status = _text(out.get("status"), f"{name}.status").upper()
    if status not in SECTION_STATUSES:
        raise DaihenOperationalReadModelError(f"unsupported {name}.status: {status}")
    if name != "portfolio_preflight" and status == "NOT_RUN":
        raise DaihenOperationalReadModelError("NOT_RUN is only valid for portfolio_preflight")

    freshness = str(out.get("freshness") or "UNKNOWN").upper()
    if freshness not in FRESHNESS_STATUSES:
        raise DaihenOperationalReadModelError(f"unsupported {name}.freshness: {freshness}")

    refs = _source_refs(out.get("source_refs"), f"{name}.source_refs")
    if out.get("basis_conflict") is True:
        status = "NEEDS_REVIEW"
    elif freshness == "STALE" and status == "OK":
        status = "PARTIAL"
    elif status == "OK" and not refs:
        status = "PARTIAL"

    out["status"] = status
    out["freshness"] = freshness
    out["source_refs"] = refs
    return out


def _overall_status(sections: Mapping[str, Mapping[str, Any]]) -> str:
    statuses = [str(sections[name]["status"]) for name in SECTION_NAMES]
    if "NEEDS_REVIEW" in statuses:
        return "NEEDS_REVIEW"

    meaningful = [status for status in statuses if status not in {"UNAVAILABLE", "NOT_RUN"}]
    if not meaningful:
        return "UNAVAILABLE"

    if all(status == "OK" for status in statuses) and all(
        sections[name].get("freshness") == "CURRENT" for name in SECTION_NAMES
    ):
        return "OK"
    return "PARTIAL"


def build_daihen_operational_read_model(
    upstream: Mapping[str, Any],
    *,
    generated_at: str,
) -> dict[str, Any]:
    """Bundle existing canonical outputs for #257 without recomputation or write-back.

    The function is intentionally presentation-neutral. It accepts already-authoritative
    upstream projections and only copies/aggregates explicit status, freshness and refs.
    It never derives EPS, valuation, expectation gaps, portfolio limits or trade actions.
    """
    if not isinstance(upstream, Mapping):
        raise DaihenOperationalReadModelError("upstream must be an object")
    _reject_prohibited(upstream)

    security_code = _text(upstream.get("security_code"), "security_code")
    if security_code != "6622":
        raise DaihenOperationalReadModelError("#257 PR-A fixture is restricted to Daihen security_code=6622")
    company_name = _text(upstream.get("company_name"), "company_name")
    generated = _iso_datetime(generated_at, "generated_at")

    sections = {name: _section(name, upstream.get(name)) for name in SECTION_NAMES}
    missing_components = [
        name for name in SECTION_NAMES if sections[name]["status"] in {"UNAVAILABLE", "NOT_RUN"}
    ]
    stale_components = [name for name in SECTION_NAMES if sections[name].get("freshness") == "STALE"]
    unknown_components = [name for name in SECTION_NAMES if sections[name].get("freshness") == "UNKNOWN"]

    all_refs: set[str] = set()
    for name in SECTION_NAMES:
        all_refs.update(sections[name].get("source_refs") or [])

    if stale_components:
        freshness_overall = "STALE"
    elif unknown_components:
        freshness_overall = "PARTIAL"
    else:
        freshness_overall = "CURRENT"

    result: dict[str, Any] = {
        "security_code": security_code,
        "company_name": company_name,
        "generated_at": generated,
        "overall_status": _overall_status(sections),
        **sections,
        "freshness": {
            "overall": freshness_overall,
            "stale_components": sorted(stale_components),
            "unknown_components": sorted(unknown_components),
        },
        "missing_components": sorted(missing_components),
        "source_refs": sorted(all_refs),
    }
    return result
