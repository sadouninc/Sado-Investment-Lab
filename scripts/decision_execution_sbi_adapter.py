from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from scripts.decision_execution_fidelity import capture_actual_execution

SOURCE_STATUSES = {"CURRENT", "STALE", "UNAVAILABLE", "UNKNOWN"}
EXECUTION_STATUSES = {"NOT_EXECUTED", "PARTIAL", "EXECUTED", "UNKNOWN"}
TIME_KEYS = ("約定時刻", "約定時間", "時刻", "execution_time", "executed_at")


class DecisionExecutionAdapterError(ValueError):
    pass


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionExecutionAdapterError(f"{field} must be a non-empty string")
    return value.strip()


def _enum(value: Any, field: str, allowed: set[str]) -> str:
    normalized = _text(value, field).upper()
    if normalized not in allowed:
        raise DecisionExecutionAdapterError(f"unsupported {field}: {normalized}")
    return normalized


def _date(value: Any, field: str) -> date:
    text = _text(value, field)
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise DecisionExecutionAdapterError(f"{field} must be YYYY-MM-DD") from exc


def _captured_at(value: Any) -> str:
    text = _text(value, "captured_at")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DecisionExecutionAdapterError("captured_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise DecisionExecutionAdapterError("captured_at must include timezone")
    return parsed.isoformat()


def _timezone_suffix(value: str | None) -> str | None:
    if value is None:
        return None
    text = _text(value, "source_timezone")
    if len(text) != 6 or text[0] not in "+-" or text[3] != ":":
        raise DecisionExecutionAdapterError("source_timezone must be an explicit offset such as +09:00")
    try:
        datetime.fromisoformat(f"2000-01-01T00:00:00{text}")
    except ValueError as exc:
        raise DecisionExecutionAdapterError("invalid source_timezone") from exc
    return text


def sbi_execution_ref(record: Mapping[str, Any]) -> str:
    fingerprint = _text(record.get("fingerprint"), "execution.fingerprint")
    return f"sbi-execution:{fingerprint}"


def _fingerprint_from_ref(ref: str) -> str:
    text = _text(ref, "execution_ref")
    prefix = "sbi-execution:"
    if not text.startswith(prefix) or len(text) == len(prefix):
        raise DecisionExecutionAdapterError("execution_ref must use sbi-execution:<fingerprint>")
    return text[len(prefix):]


def load_sbi_execution_rows(
    database: str | Path,
    execution_refs: Iterable[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    refs = list(execution_refs)
    fingerprints = [_fingerprint_from_ref(ref) for ref in refs]
    if len(fingerprints) != len(set(fingerprints)):
        raise DecisionExecutionAdapterError("duplicate execution_ref")
    path = Path(database)
    if not path.is_file():
        return [], refs

    try:
        with sqlite3.connect(path) as db:
            db.row_factory = sqlite3.Row
            table = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='executions'"
            ).fetchone()
            if table is None:
                return [], refs
            rows_by_fingerprint: dict[str, dict[str, Any]] = {}
            for fingerprint in fingerprints:
                row = db.execute(
                    "SELECT * FROM executions WHERE fingerprint = ?", (fingerprint,)
                ).fetchone()
                if row is not None:
                    rows_by_fingerprint[fingerprint] = dict(row)
    except sqlite3.Error:
        return [], refs

    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for ref, fingerprint in zip(refs, fingerprints):
        row = rows_by_fingerprint.get(fingerprint)
        if row is None:
            missing.append(ref)
        else:
            rows.append(row)
    return rows, missing


def _raw_fields(record: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = record.get("raw_json")
    if not raw:
        return {}
    if isinstance(raw, Mapping):
        return raw
    if not isinstance(raw, str):
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, Mapping) else {}


def _execution_timestamp(
    record: Mapping[str, Any], source_timezone: str | None
) -> tuple[str | None, str]:
    raw = _raw_fields(record)
    raw_value = None
    for key in TIME_KEYS:
        candidate = raw.get(key)
        if isinstance(candidate, str) and candidate.strip():
            raw_value = candidate.strip()
            break
    if raw_value is None:
        return None, "DATE_ONLY_SOURCE"

    normalized = raw_value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        parsed = None
    if parsed is not None:
        if parsed.tzinfo is None:
            if source_timezone is None:
                return None, "TIMEZONE_MISSING"
            parsed = datetime.fromisoformat(f"{parsed.isoformat()}{source_timezone}")
        return parsed.isoformat(), "TIMESTAMP"

    trade_date = _date(record.get("trade_date"), "execution.trade_date")
    parsed_time = None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            parsed_time = datetime.strptime(raw_value, fmt).time()
            break
        except ValueError:
            continue
    if parsed_time is None:
        return None, "TIME_UNPARSEABLE"
    if source_timezone is None:
        return None, "TIMEZONE_MISSING"
    parsed = datetime.fromisoformat(
        f"{trade_date.isoformat()}T{parsed_time.isoformat()}{source_timezone}"
    )
    return parsed.isoformat(), "TIMESTAMP"


def _session(executed_at: str) -> str:
    parsed = datetime.fromisoformat(executed_at)
    hm = (parsed.hour, parsed.minute)
    if (9, 0) <= hm <= (9, 1):
        return "OPEN"
    if (9, 0) <= hm <= (11, 30):
        return "AM"
    if (12, 30) <= hm <= (15, 30):
        return "PM"
    return "UNKNOWN"


def _account_type(record: Mapping[str, Any]) -> str:
    text = " ".join(
        str(record.get(key) or "") for key in ("product", "transaction_type")
    )
    if "信用" in text:
        return "MARGIN"
    if "現物" in text or "株式" in text:
        return "CASH"
    return "UNKNOWN"


def _direction(record: Mapping[str, Any]) -> str:
    side = _text(record.get("side"), "execution.side").upper()
    if side not in {"BUY", "SELL"}:
        raise DecisionExecutionAdapterError("execution.side must be BUY or SELL")
    transaction = str(record.get("transaction_type") or "")
    product = str(record.get("product") or "")
    credit = "信用" in f"{transaction} {product}"
    if credit and "返済" in transaction:
        return "SHORT_DECREASE" if side == "BUY" else "LONG_DECREASE"
    if credit and "新規" in transaction:
        return "SHORT_INCREASE" if side == "SELL" else "LONG_INCREASE"
    return "LONG_INCREASE" if side == "BUY" else "LONG_DECREASE"


def _number(value: Any, field: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise DecisionExecutionAdapterError(f"{field} must be a positive number")
    return value


def _portfolio_ref(snapshot: Mapping[str, Any] | None) -> str | None:
    if not isinstance(snapshot, Mapping):
        return None
    refs = snapshot.get("source_references")
    if isinstance(refs, Mapping):
        value = refs.get("snapshot_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    value = snapshot.get("base_snapshot")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _portfolio_status(snapshot: Mapping[str, Any] | None) -> str:
    if snapshot is None:
        return "NOT_JUDGABLE"
    if not isinstance(snapshot, Mapping):
        return "UNKNOWN"
    if str(snapshot.get("verification_status") or "").upper() != "VERIFIED":
        return "UNKNOWN"
    if not isinstance(snapshot.get("positions"), list) or _portfolio_ref(snapshot) is None:
        return "UNKNOWN"
    try:
        _date(snapshot.get("as_of"), "portfolio.as_of")
    except DecisionExecutionAdapterError:
        return "UNKNOWN"
    return "VERIFIED"


def _position_quantity(
    snapshot: Mapping[str, Any], security_code: str, position_side: str
) -> float:
    total = 0.0
    for position in snapshot.get("positions", []):
        if not isinstance(position, Mapping):
            raise DecisionExecutionAdapterError("portfolio position must be an object")
        if str(position.get("security_code") or "") != security_code:
            continue
        position_type = str(position.get("position_type") or "")
        if position_side == "LONG" and position_type not in {"cash", "margin_long"}:
            continue
        if position_side == "SHORT" and position_type != "margin_short":
            continue
        quantity = position.get("quantity")
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or quantity < 0:
            raise DecisionExecutionAdapterError("portfolio quantity must be non-negative")
        total += float(quantity)
    return total


def verify_position_change(
    portfolio_before: Mapping[str, Any] | None,
    portfolio_after: Mapping[str, Any] | None,
    security_code: str,
    direction: str | None,
    fills: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    before_status = _portfolio_status(portfolio_before)
    after_status = _portfolio_status(portfolio_after)
    result = {
        "status": "NOT_JUDGABLE",
        "before_ref": _portfolio_ref(portfolio_before),
        "after_ref": _portfolio_ref(portfolio_after),
        "before_quantity": None,
        "after_quantity": None,
        "position_delta": None,
        "execution_quantity": None,
        "direction": direction,
        "actual_action": "UNKNOWN",
    }
    if before_status == "UNKNOWN" or after_status == "UNKNOWN":
        result["status"] = "UNKNOWN"
        return result
    if before_status != "VERIFIED" or after_status != "VERIFIED" or direction is None:
        return result

    fill_list = [dict(fill) for fill in fills]
    if not fill_list:
        return result
    try:
        executed_times = [datetime.fromisoformat(_text(fill.get("executed_at"), "fill.executed_at")) for fill in fill_list]
    except ValueError as exc:
        raise DecisionExecutionAdapterError("fill.executed_at must be ISO-8601") from exc
    if any(item.tzinfo is None for item in executed_times):
        result["status"] = "UNKNOWN"
        return result

    before_date = _date(portfolio_before.get("as_of"), "portfolio_before.as_of")
    after_date = _date(portfolio_after.get("as_of"), "portfolio_after.as_of")
    if after_date < before_date:
        raise DecisionExecutionAdapterError("portfolio_after must not predate portfolio_before")

    first_execution_date = min(item.date() for item in executed_times)
    last_execution_date = max(item.date() for item in executed_times)
    if not (before_date < first_execution_date and after_date > last_execution_date):
        result["status"] = "NOT_JUDGABLE"
        return result

    side = "SHORT" if direction.startswith("SHORT") else "LONG"
    before_qty = _position_quantity(portfolio_before, security_code, side)
    after_qty = _position_quantity(portfolio_after, security_code, side)
    execution_qty = sum(float(_number(fill.get("quantity"), "fill.quantity")) for fill in fill_list)
    delta = after_qty - before_qty
    expected_delta = execution_qty if direction.endswith("INCREASE") else -execution_qty

    result["before_quantity"] = before_qty
    result["after_quantity"] = after_qty
    result["position_delta"] = delta
    result["execution_quantity"] = execution_qty

    if delta != expected_delta:
        result["status"] = "MISMATCH"
        return result

    result["status"] = "CONSISTENT"
    if direction == "LONG_INCREASE":
        result["actual_action"] = "BUY" if before_qty == 0 else "ADD"
    elif direction == "LONG_DECREASE":
        result["actual_action"] = "SELL" if after_qty == 0 else "REDUCE"
    elif direction == "SHORT_INCREASE":
        result["actual_action"] = "SHORT_OPEN" if before_qty == 0 else "SHORT_ADD"
    elif direction == "SHORT_DECREASE":
        result["actual_action"] = "COVER"
    return result


def build_actual_execution_from_sbi_rows(
    *,
    decision_ref: str,
    security_code: str,
    captured_at: str,
    rows: Iterable[Mapping[str, Any]],
    execution_refs: Iterable[str],
    execution_status: str,
    source_status: str = "CURRENT",
    source_timezone: str | None = None,
    portfolio_before: Mapping[str, Any] | None = None,
    portfolio_after: Mapping[str, Any] | None = None,
    missing_execution_refs: Iterable[str] = (),
) -> dict[str, Any]:
    decision = _text(decision_ref, "decision_ref")
    code = _text(security_code, "security_code")
    captured = _captured_at(captured_at)
    status = _enum(execution_status, "execution_status", EXECUTION_STATUSES)
    source = _enum(source_status, "source_status", SOURCE_STATUSES)
    timezone = _timezone_suffix(source_timezone)
    requested_refs = list(execution_refs)
    missing_refs = list(missing_execution_refs)
    if len(requested_refs) != len(set(requested_refs)):
        raise DecisionExecutionAdapterError("duplicate execution_ref")

    diagnostics: list[str] = []
    if source in {"UNAVAILABLE", "UNKNOWN"}:
        diagnostics.append("SBI_SOURCE_UNAVAILABLE")
        status = "UNKNOWN"
        rows = []
        requested_refs = []
    elif missing_refs:
        diagnostics.append("SBI_EXECUTION_REF_MISSING")
        status = "UNKNOWN"
        rows = []

    rows_list = [deepcopy(dict(row)) for row in rows]
    if len(rows_list) != len(requested_refs):
        if status not in {"UNKNOWN", "NOT_EXECUTED"}:
            raise DecisionExecutionAdapterError("rows and execution_refs must have identical length")

    if status == "NOT_EXECUTED":
        if rows_list or requested_refs:
            raise DecisionExecutionAdapterError("NOT_EXECUTED cannot include execution refs")
    elif status in {"EXECUTED", "PARTIAL"} and not rows_list:
        raise DecisionExecutionAdapterError(f"{status} requires confirmed SBI executions")

    fills: list[dict[str, Any]] = []
    directions: set[str] = set()
    if status in {"EXECUTED", "PARTIAL"}:
        for row, ref in zip(rows_list, requested_refs):
            expected_ref = sbi_execution_ref(row)
            if expected_ref != ref:
                raise DecisionExecutionAdapterError("SBI row fingerprint does not match execution_ref")
            if str(row.get("security_code") or "") != code:
                raise DecisionExecutionAdapterError("SBI execution security_code mismatch")
            executed_at, precision = _execution_timestamp(row, timezone)
            if executed_at is None:
                diagnostics.append(f"SBI_EXECUTION_TIME_{precision}")
                status = "UNKNOWN"
                fills = []
                directions.clear()
                break
            quantity = _number(row.get("quantity"), "execution.quantity")
            price = _number(row.get("price"), "execution.price")
            directions.add(_direction(row))
            fills.append(
                {
                    "executed_at": executed_at,
                    "side": _text(row.get("side"), "execution.side").upper(),
                    "quantity": int(quantity) if float(quantity).is_integer() else quantity,
                    "price": price,
                    "account_type": _account_type(row),
                    "source_ref": ref,
                    "session": _session(executed_at),
                }
            )

    direction = next(iter(directions)) if len(directions) == 1 else None
    if len(directions) > 1:
        diagnostics.append("MIXED_EXECUTION_DIRECTIONS")

    verification = verify_position_change(
        portfolio_before, portfolio_after, code, direction, fills
    )
    actual_action = verification["actual_action"]
    if (
        direction == "SHORT_DECREASE"
        and actual_action == "UNKNOWN"
        and status in {"EXECUTED", "PARTIAL"}
    ):
        actual_action = "COVER"

    if status == "UNKNOWN":
        fills = []
        actual_action = "UNKNOWN"

    record = {
        "decision_ref": decision,
        "security_code": code,
        "captured_at": captured,
        "execution_status": status,
        "source_status": source,
        "actual_action": actual_action,
        "fills": fills,
        "position_before_ref": verification["before_ref"],
        "position_after_ref": verification["after_ref"],
        "sbi_execution_refs": list(requested_refs),
        "portfolio_verification": verification,
        "adapter_diagnostics": sorted(set(diagnostics)),
    }
    return capture_actual_execution(record)


def build_actual_execution_from_sbi_db(
    *,
    database: str | Path,
    decision_ref: str,
    security_code: str,
    captured_at: str,
    execution_refs: Iterable[str],
    execution_status: str,
    source_status: str = "CURRENT",
    source_timezone: str | None = None,
    portfolio_before: Mapping[str, Any] | None = None,
    portfolio_after: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    refs = list(execution_refs)
    rows, missing = load_sbi_execution_rows(database, refs)
    effective_source = source_status
    if not Path(database).is_file() and source_status == "CURRENT":
        effective_source = "UNAVAILABLE"
    return build_actual_execution_from_sbi_rows(
        decision_ref=decision_ref,
        security_code=security_code,
        captured_at=captured_at,
        rows=rows,
        execution_refs=refs,
        execution_status=execution_status,
        source_status=effective_source,
        source_timezone=source_timezone,
        portfolio_before=portfolio_before,
        portfolio_after=portfolio_after,
        missing_execution_refs=missing,
    )