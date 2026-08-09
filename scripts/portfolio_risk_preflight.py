from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping


ACTIONS = {"BUY", "ADD", "REDUCE", "SELL"}
ACCOUNT_TYPES = {"CASH", "MARGIN", "UNKNOWN"}
DATA_STATUS = {"CURRENT", "STALE", "PARTIAL", "UNKNOWN"}
RULE_SOURCES = {"OWNER_DEFINED", "FRAMEWORK_DEFINED", "UNSET"}
RESULTS = {"PASS", "WARN", "BLOCK_REVIEW", "UNKNOWN"}


class RiskPreflightError(ValueError):
    pass


def _finite_number(value: Any, *, field: str, allow_zero: bool = True) -> float:
    if isinstance(value, bool):
        raise RiskPreflightError(f"{field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RiskPreflightError(f"{field} must be numeric") from exc
    if not math.isfinite(number):
        raise RiskPreflightError(f"{field} must be finite")
    if number < 0 or (not allow_zero and number == 0):
        raise RiskPreflightError(f"{field} must be positive")
    return number


def deterministic_snapshot_id(captured_at: str, security_code: str, action: str, portfolio_ref: str) -> str:
    values = [captured_at.strip(), security_code.strip(), action.strip(), portfolio_ref.strip()]
    if any(not value for value in values):
        raise RiskPreflightError("snapshot identity fields are required")
    digest = hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()[:16]
    return f"risk-preflight:{security_code}:{digest}"


def _rule_result(
    *,
    value: float | None,
    rule: Mapping[str, Any] | None,
    lower_is_worse: bool = False,
) -> dict[str, Any]:
    if value is None:
        return {"result": "UNKNOWN", "rule_source": "UNSET", "reason": "必要データが不足"}
    if not rule or rule.get("source", "UNSET") == "UNSET":
        return {"result": "UNKNOWN", "rule_source": "UNSET", "reason": "上限ルール未設定"}
    source = rule.get("source")
    if source not in RULE_SOURCES - {"UNSET"}:
        raise RiskPreflightError("invalid rule source")
    hard = rule.get("hard_limit")
    warn = rule.get("warn_limit")
    if hard is None:
        return {"result": "UNKNOWN", "rule_source": source, "reason": "hard_limit未設定"}
    hard_n = _finite_number(hard, field="hard_limit")
    warn_n = None if warn is None else _finite_number(warn, field="warn_limit")

    if lower_is_worse:
        if warn_n is not None and warn_n < hard_n:
            raise RiskPreflightError("minimum-rule warn_limit must not be below hard_limit")
        if value < hard_n:
            result = "BLOCK_REVIEW"
        elif warn_n is not None and value <= warn_n:
            result = "WARN"
        else:
            result = "PASS"
    else:
        if warn_n is not None and warn_n > hard_n:
            raise RiskPreflightError("warn_limit must not exceed hard_limit")
        if value > hard_n:
            result = "BLOCK_REVIEW"
        elif warn_n is not None and value >= warn_n:
            result = "WARN"
        else:
            result = "PASS"
    return {"result": result, "rule_source": source, "hard_limit": hard_n, "warn_limit": warn_n}


def calculate_trade_impact(payload: Mapping[str, Any]) -> dict[str, Any]:
    captured_at = str(payload.get("captured_at") or "").strip()
    portfolio_ref = str(payload.get("portfolio_ref") or "").strip()
    proposed = dict(payload.get("proposed_action") or {})
    before = dict(payload.get("before") or {})
    rules = dict(payload.get("rules") or {})
    data_status = str(payload.get("data_status") or "UNKNOWN")

    if data_status not in DATA_STATUS:
        raise RiskPreflightError("invalid data_status")
    security_code = str(proposed.get("security_code") or "").strip()
    action = str(proposed.get("action") or "").strip()
    account_type = str(proposed.get("account_type") or "UNKNOWN")
    if action not in ACTIONS:
        raise RiskPreflightError("invalid proposed action")
    if account_type not in ACCOUNT_TYPES:
        raise RiskPreflightError("invalid account_type")
    if not security_code:
        raise RiskPreflightError("security_code is required")

    quantity = proposed.get("quantity")
    price = proposed.get("price")
    notional = proposed.get("notional")
    if quantity is None or price is None:
        raise RiskPreflightError("quantity and price are required; do not infer missing trade size")
    quantity_n = _finite_number(quantity, field="quantity", allow_zero=False)
    price_n = _finite_number(price, field="price", allow_zero=False)
    computed_notional = quantity_n * price_n
    if notional is not None:
        supplied = _finite_number(notional, field="notional", allow_zero=False)
        if not math.isclose(supplied, computed_notional, rel_tol=1e-9, abs_tol=1e-6):
            raise RiskPreflightError("notional conflicts with quantity * price")
    notional_n = computed_notional

    current_position = _finite_number(before.get("position_notional", 0), field="position_notional")
    cash_available = before.get("cash_available")
    gross_exposure = before.get("gross_exposure")
    margin_exposure = before.get("margin_exposure")
    portfolio_equity = before.get("portfolio_equity")

    sign = 1 if action in {"BUY", "ADD"} else -1
    after_position = current_position + sign * notional_n
    if after_position < -1e-9:
        raise RiskPreflightError("proposed reduction exceeds current position")
    after_position = max(after_position, 0.0)

    after_cash = None
    if cash_available is not None:
        cash_n = _finite_number(cash_available, field="cash_available")
        if account_type == "CASH":
            after_cash = cash_n - sign * notional_n
            if after_cash < -1e-9 and action in {"BUY", "ADD"}:
                after_cash = after_cash
        else:
            after_cash = cash_n

    after_gross = None
    if gross_exposure is not None:
        gross_n = _finite_number(gross_exposure, field="gross_exposure")
        after_gross = gross_n + sign * notional_n
        if after_gross < -1e-9:
            raise RiskPreflightError("gross exposure would become negative")
        after_gross = max(after_gross, 0.0)

    after_margin = None
    if margin_exposure is not None:
        margin_n = _finite_number(margin_exposure, field="margin_exposure")
        if account_type == "MARGIN":
            after_margin = margin_n + sign * notional_n
            if after_margin < -1e-9:
                raise RiskPreflightError("margin exposure would become negative")
            after_margin = max(after_margin, 0.0)
        else:
            after_margin = margin_n

    position_weight = None
    if portfolio_equity is not None:
        equity_n = _finite_number(portfolio_equity, field="portfolio_equity", allow_zero=False)
        position_weight = after_position / equity_n

    concentration = _rule_result(value=position_weight, rule=rules.get("single_name"))
    cash_rule_value = None if after_cash is None else after_cash
    cash_rule = _rule_result(
        value=cash_rule_value,
        rule=rules.get("minimum_cash"),
        lower_is_worse=True,
    )

    if data_status != "CURRENT":
        concentration = {"result": "UNKNOWN", "rule_source": concentration.get("rule_source", "UNSET"), "reason": f"portfolio data_status={data_status}"}
        cash_rule = {"result": "UNKNOWN", "rule_source": cash_rule.get("rule_source", "UNSET"), "reason": f"portfolio data_status={data_status}"}

    result = {
        "snapshot_id": deterministic_snapshot_id(captured_at, security_code, action, portfolio_ref),
        "captured_at": captured_at,
        "portfolio_ref": portfolio_ref,
        "proposed_action": {
            "security_code": security_code,
            "action": action,
            "quantity": quantity_n,
            "price": price_n,
            "notional": notional_n,
            "account_type": account_type,
        },
        "before": before,
        "after_if_executed": {
            "cash_available": after_cash,
            "gross_exposure": after_gross,
            "margin_exposure": after_margin,
            "position_notional": after_position,
            "position_weight": position_weight,
        },
        "guardrail_results": [
            {"guardrail": "SINGLE_NAME_CONCENTRATION", **concentration},
            {"guardrail": "MINIMUM_CASH", **cash_rule},
        ],
        "data_status": data_status,
        "trade_action": None,
    }
    return result


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
