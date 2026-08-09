from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

EXPECTATION_TYPES = {"CONSENSUS", "COMPANY_GUIDANCE", "MARKET_IMPLIED_PROXY", "SADO_SCENARIO"}
METRICS = {"REVENUE", "OPERATING_PROFIT", "NET_INCOME", "EPS", "MARGIN", "KPI"}
AUTHORITIES = {"PRIMARY", "SECONDARY", "INTERNAL"}
COVERAGE_STATES = {"OK", "PARTIAL", "STALE", "UNAVAILABLE"}
DIRECTIONS = {"UP", "DOWN", "FLAT", "MIXED", "UNKNOWN"}


class ExpectationContractError(ValueError):
    pass


def deterministic_expectation_id(record: dict[str, Any]) -> str:
    key = "|".join(
        str(record.get(field) or "").strip()
        for field in ("security_code", "target_fiscal_period", "expectation_type", "metric", "unit", "as_of")
    )
    if "||" in key or key.startswith("|") or key.endswith("|"):
        raise ExpectationContractError("expectation identity fields are required")
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"expectation:{record['security_code']}:{record['target_fiscal_period']}:{digest}"


def validate_snapshot(record: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    result = dict(record)
    required = [
        "security_code", "target_fiscal_period", "as_of", "expectation_type", "metric", "unit",
        "source_ref", "source_authority", "observed_at", "coverage",
    ]
    missing = [field for field in required if result.get(field) in (None, "")]
    if missing:
        raise ExpectationContractError(f"missing required fields: {', '.join(missing)}")
    if result["expectation_type"] not in EXPECTATION_TYPES:
        raise ExpectationContractError("invalid expectation_type")
    if result["metric"] not in METRICS:
        raise ExpectationContractError("invalid metric")
    if result["source_authority"] not in AUTHORITIES:
        raise ExpectationContractError("invalid source_authority")
    coverage = dict(result.get("coverage") or {})
    status = str(coverage.get("status") or "")
    if status not in COVERAGE_STATES:
        raise ExpectationContractError("invalid coverage.status")
    if status == "UNAVAILABLE" and result.get("value") is not None:
        raise ExpectationContractError("UNAVAILABLE expectation must not carry a value")
    if status != "UNAVAILABLE" and result.get("value") is None:
        raise ExpectationContractError("available expectation requires value")
    date.fromisoformat(str(result["as_of"]))
    datetime.fromisoformat(str(result["observed_at"]).replace("Z", "+00:00"))
    result["expectation_id"] = deterministic_expectation_id(result)
    result["coverage"] = coverage
    result.setdefault("provenance", {})
    return result


def _canonical_json(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def append_snapshot(path: Path, record: dict[str, Any]) -> str:
    candidate = validate_snapshot(record)
    existing = load_history(path)
    same = [row for row in existing if row.get("expectation_id") == candidate["expectation_id"]]
    if same:
        if any(_canonical_json(row) == _canonical_json(candidate) for row in same):
            return "UNCHANGED"
        raise ExpectationContractError("conflicting payload for same expectation identity")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(candidate, ensure_ascii=False, sort_keys=True) + "\n")
    return "INSERTED"


def load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def same_series_key(record: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(record["security_code"]), str(record["target_fiscal_period"]), str(record["expectation_type"]),
        str(record["metric"]), str(record["unit"]),
    )


def revision_series(history: list[dict[str, Any]], *, template: dict[str, Any]) -> list[dict[str, Any]]:
    key = same_series_key(template)
    rows = [row for row in history if same_series_key(row) == key]
    return sorted(rows, key=lambda row: (str(row["as_of"]), str(row["observed_at"])))


def revision_delta(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    if same_series_key(previous) != same_series_key(current):
        raise ExpectationContractError("revision comparison requires same fiscal/metric/type/unit basis")
    if previous.get("value") is None or current.get("value") is None:
        return {"absolute": None, "pct": None, "direction": "UNKNOWN"}
    old = float(previous["value"])
    new = float(current["value"])
    absolute = new - old
    pct = None if old == 0 else absolute / abs(old) * 100.0
    epsilon = 1e-12
    direction = "FLAT" if abs(absolute) <= epsilon else ("UP" if absolute > 0 else "DOWN")
    return {"absolute": round(absolute, 10), "pct": None if pct is None else round(pct, 6), "direction": direction}


def summarize_revision_direction(series: list[dict[str, Any]]) -> str:
    available = [row for row in series if row.get("value") is not None]
    if len(available) < 2:
        return "UNKNOWN"
    directions = [revision_delta(a, b)["direction"] for a, b in zip(available, available[1:])]
    directional = {value for value in directions if value != "FLAT"}
    if not directional:
        return "FLAT"
    if directional == {"UP"}:
        return "UP"
    if directional == {"DOWN"}:
        return "DOWN"
    return "MIXED"


def latest_revision_view(history: list[dict[str, Any]], *, template: dict[str, Any]) -> dict[str, Any]:
    series = revision_series(history, template=template)
    latest = series[-1] if series else None
    previous = series[-2] if len(series) >= 2 else None
    return {
        "latest": latest,
        "previous": previous,
        "revision_since_previous": None if not (latest and previous) else revision_delta(previous, latest),
        "direction": summarize_revision_direction(series),
        "observation_count": len(series),
        "acceleration": None,
        "acceleration_status": "INSUFFICIENT_OBSERVATIONS" if len([r for r in series if r.get("value") is not None]) < 3 else "NOT_IMPLEMENTED_V1",
    }
