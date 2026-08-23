from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


VALID_RUN_STATUS = {"OK", "ERROR", "UNKNOWN"}
VALID_PERSISTENCE_STATUS = {"COMPLETED", "PENDING_PERSIST", "NOT_REQUIRED"}
MAX_FUTURE_SKEW_MINUTES = 5


@dataclass(frozen=True)
class WatchHealth:
    state: str
    age_minutes: float | None
    reason: str


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed


def validate_status(payload: dict[str, Any]) -> None:
    if payload.get("last_status") not in VALID_RUN_STATUS:
        raise ValueError("invalid last_status")
    if payload.get("persistence_status") not in VALID_PERSISTENCE_STATUS:
        raise ValueError("invalid persistence_status")
    stale_after = payload.get("stale_after_minutes")
    if not isinstance(stale_after, int) or stale_after <= 0:
        raise ValueError("stale_after_minutes must be a positive integer")
    news_delta = payload.get("news_delta")
    if news_delta is not None and (not isinstance(news_delta, int) or news_delta < 0):
        raise ValueError("news_delta must be null or a non-negative integer")
    for key in ("last_run_at", "last_success_at", "last_news_delta_at"):
        parse_timestamp(payload.get(key))


def validate_timestamp_order(
    payload: dict[str, Any],
    now: datetime,
    max_future_skew_minutes: int = MAX_FUTURE_SKEW_MINUTES,
) -> str | None:
    if now.tzinfo is None:
        raise ValueError("now must include timezone")
    current = now.astimezone(timezone.utc)
    future_limit = current + timedelta(minutes=max_future_skew_minutes)
    timestamps = {
        key: parse_timestamp(payload.get(key))
        for key in ("last_run_at", "last_success_at", "last_news_delta_at")
    }
    for key, value in timestamps.items():
        if value is not None and value.astimezone(timezone.utc) > future_limit:
            return f"{key} is more than {max_future_skew_minutes} minutes in the future"

    last_run = timestamps["last_run_at"]
    last_success = timestamps["last_success_at"]
    last_news_delta = timestamps["last_news_delta_at"]
    if last_run is not None and last_success is not None and last_success > last_run:
        return "last_success_at is later than last_run_at"
    if last_run is not None and last_news_delta is not None and last_news_delta > last_run:
        return "last_news_delta_at is later than last_run_at"
    return None


def classify_health(payload: dict[str, Any], now: datetime | None = None) -> WatchHealth:
    validate_status(payload)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must include timezone")

    timestamp_error = validate_timestamp_order(payload, current)
    if timestamp_error:
        return WatchHealth("DEGRADED", None, f"invalid heartbeat timestamp: {timestamp_error}")

    last_success = parse_timestamp(payload.get("last_success_at"))
    if last_success is None:
        return WatchHealth("STALE", None, "no successful run recorded")

    age_minutes = (current.astimezone(timezone.utc) - last_success.astimezone(timezone.utc)).total_seconds() / 60
    stale_after = payload["stale_after_minutes"]
    if age_minutes > stale_after:
        return WatchHealth("STALE", age_minutes, f"last successful run is older than {stale_after} minutes")
    if payload.get("last_status") == "ERROR":
        return WatchHealth("DEGRADED", age_minutes, "latest run failed but a recent successful run exists")
    if payload.get("persistence_status") == "PENDING_PERSIST":
        return WatchHealth("DEGRADED", age_minutes, "news persistence is pending")
    return WatchHealth("HEALTHY", age_minutes, "recent successful run recorded")


def load_status(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_status(payload)
    return payload


def save_status(path: Path, payload: dict[str, Any]) -> None:
    validate_status(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_run_evidence(evidence: dict[str, Any]) -> None:
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be a dictionary")
    parse_timestamp(evidence.get("run_at"))
    if evidence.get("status") not in VALID_RUN_STATUS:
        raise ValueError("invalid status in evidence")
    news_delta = evidence.get("news_delta")
    if not isinstance(news_delta, int) or news_delta < 0:
        raise ValueError("news_delta in evidence must be a non-negative integer")
    if not isinstance(evidence.get("news_persisted"), bool):
        raise ValueError("news_persisted in evidence must be a boolean")
    if evidence.get("persistence_status") not in VALID_PERSISTENCE_STATUS:
        raise ValueError("invalid persistence_status in evidence")


def update_status(current_payload: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    validate_status(current_payload)
    validate_run_evidence(evidence)

    evidence_run_at = evidence["run_at"]
    evidence_dt = parse_timestamp(evidence_run_at)
    current_run_at = current_payload.get("last_run_at")
    current_dt = parse_timestamp(current_run_at) if current_run_at else None

    if current_dt is not None and evidence_dt is not None:
        evidence_utc = evidence_dt.astimezone(timezone.utc)
        current_utc = current_dt.astimezone(timezone.utc)

        if evidence_utc < current_utc:
            raise ValueError(f"evidence run_at ({evidence_run_at}) is older than current last_run_at ({current_run_at})")

        if evidence_utc == current_utc:
            is_match = (
                current_payload.get("last_status") == evidence["status"]
                and current_payload.get("news_delta") == evidence["news_delta"]
                and current_payload.get("news_persisted") == evidence["news_persisted"]
                and current_payload.get("persistence_status") == evidence["persistence_status"]
            )
            if is_match:
                return dict(current_payload)
            raise ValueError(f"conflicting evidence for same run_at ({evidence_run_at})")

    updated = dict(current_payload)
    status = evidence["status"]
    news_delta = evidence["news_delta"]
    news_persisted = evidence["news_persisted"]
    persistence_status = evidence["persistence_status"]

    updated["last_run_at"] = evidence_run_at
    updated["last_status"] = status
    updated["news_delta"] = news_delta
    updated["news_persisted"] = news_persisted
    updated["persistence_status"] = persistence_status

    if status == "OK":
        updated["last_success_at"] = evidence_run_at
        if news_delta > 0:
            updated["last_news_delta_at"] = evidence_run_at

    validate_status(updated)
    return updated


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    status_path = root / "Ops" / "Monitoring" / "AI_Key_Person_Watch" / "status.json"
    payload = load_status(status_path)
    health = classify_health(payload)
    print(json.dumps({"state": health.state, "age_minutes": health.age_minutes, "reason": health.reason}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
