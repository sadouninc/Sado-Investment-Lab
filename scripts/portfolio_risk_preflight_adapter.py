from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
import math
from typing import Any, Mapping

from portfolio_risk_preflight import RiskPreflightError, calculate_trade_impact


VERIFICATION_STATUSES = {"VERIFIED", "PROVISIONAL", "MISMATCH"}
POSITION_TYPES = {"cash", "margin_long", "margin_short"}


class PortfolioRiskAdapterError(RiskPreflightError):
    pass


def _finite_positive(value: Any, *, field: str, allow_zero: bool = True) -> float:
    if isinstance(value, bool):
        raise PortfolioRiskAdapterError(f"{field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PortfolioRiskAdapterError(f"{field} must be numeric") from exc
    if not math.isfinite(number):
        raise PortfolioRiskAdapterError(f"{field} must be finite")
    if number < 0 or (not allow_zero and number == 0):
        raise PortfolioRiskAdapterError(f"{field} must be positive")
    return number


def _as_date(value: Any, *, field: str) -> date:
    text = str(value or "").strip()
    if not text:
        raise PortfolioRiskAdapterError(f"{field} is required")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise PortfolioRiskAdapterError(f"{field} must be ISO date") from exc


def _captured_date(value: Any) -> date:
    text = str(value or "").strip()
    if not text:
        raise PortfolioRiskAdapterError("captured_at is required")
    try:
        return datetime.fromisoformat(text).date()
    except ValueError as exc:
        raise PortfolioRiskAdapterError("captured_at must be ISO datetime") from exc


def canonical_data_status(
    portfolio: Mapping[str, Any],
    *,
    captured_at: str,
    max_age_days: int | None = None,
) -> str:
    verification = str(portfolio.get("verification_status") or "").strip()
    if verification not in VERIFICATION_STATUSES:
        raise PortfolioRiskAdapterError("invalid verification_status")
    if verification == "MISMATCH":
        return "UNKNOWN"
    if verification == "PROVISIONAL":
        return "PARTIAL"

    as_of = _as_date(portfolio.get("as_of"), field="portfolio.as_of")
    captured = _captured_date(captured_at)
    age_days = (captured - as_of).days
    if age_days < 0:
        raise PortfolioRiskAdapterError("portfolio.as_of must not be after captured_at")
    if max_age_days is not None:
        if isinstance(max_age_days, bool) or not isinstance(max_age_days, int) or max_age_days < 0:
            raise PortfolioRiskAdapterError("max_age_days must be a non-negative integer")
        if age_days > max_age_days:
            return "STALE"
    return "CURRENT"


def _validated_positions(portfolio: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = portfolio.get("positions")
    if not isinstance(raw, list):
        raise PortfolioRiskAdapterError("portfolio.positions must be an array")
    positions: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise PortfolioRiskAdapterError(f"portfolio.positions[{index}] must be an object")
        code = str(item.get("security_code") or "").strip()
        position_type = str(item.get("position_type") or "").strip()
        if not code:
            raise PortfolioRiskAdapterError(f"portfolio.positions[{index}].security_code is required")
        if position_type not in POSITION_TYPES:
            raise PortfolioRiskAdapterError(f"unsupported position_type: {position_type}")
        quantity = _finite_positive(item.get("quantity"), field=f"portfolio.positions[{index}].quantity", allow_zero=False)
        positions.append({**dict(item), "security_code": code, "position_type": position_type, "quantity": quantity})
    return positions


def _price_for(code: str, explicit_prices: Mapping[str, Any], fallback_price: float | None = None) -> float | None:
    if code in explicit_prices:
        return _finite_positive(explicit_prices[code], field=f"market_prices[{code}]", allow_zero=False)
    return fallback_price


def _position_notional_for_action(
    positions: list[dict[str, Any]],
    *,
    security_code: str,
    account_type: str,
    valuation_price: float,
) -> float:
    matching = [p for p in positions if p["security_code"] == security_code]
    if any(p["position_type"] == "margin_short" for p in matching):
        raise PortfolioRiskAdapterError("margin_short target is outside v1 BUY/ADD/REDUCE/SELL adapter semantics")
    if account_type == "CASH":
        quantity = sum(p["quantity"] for p in matching if p["position_type"] == "cash")
    elif account_type == "MARGIN":
        quantity = sum(p["quantity"] for p in matching if p["position_type"] == "margin_long")
    elif account_type == "UNKNOWN":
        quantity = sum(p["quantity"] for p in matching if p["position_type"] in {"cash", "margin_long"})
    else:
        raise PortfolioRiskAdapterError("invalid proposed account_type")
    return quantity * valuation_price


def build_preflight_payload_from_canonical(
    portfolio: Mapping[str, Any],
    *,
    captured_at: str,
    proposed_action: Mapping[str, Any],
    market_prices: Mapping[str, Any] | None = None,
    cash_available: Any | None = None,
    portfolio_equity: Any | None = None,
    max_age_days: int | None = None,
    rules: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build PR1 payload without inventing missing Portfolio metrics.

    Canonical Portfolio State is authoritative for positions/verification only. Market
    prices, cash and portfolio equity must be explicitly supplied. The proposed
    trade price may be used to value the target security because it is itself an
    explicit user/system input, not an inferred quote.
    """

    portfolio_copy = deepcopy(dict(portfolio))
    proposed = deepcopy(dict(proposed_action))
    positions = _validated_positions(portfolio_copy)
    security_code = str(proposed.get("security_code") or "").strip()
    account_type = str(proposed.get("account_type") or "UNKNOWN").strip()
    if not security_code:
        raise PortfolioRiskAdapterError("proposed_action.security_code is required")
    proposed_price = _finite_positive(proposed.get("price"), field="proposed_action.price", allow_zero=False)
    prices = dict(market_prices or {})
    valuation_price = _price_for(security_code, prices, fallback_price=proposed_price)
    assert valuation_price is not None

    position_notional = _position_notional_for_action(
        positions,
        security_code=security_code,
        account_type=account_type,
        valuation_price=valuation_price,
    )

    all_priced = True
    gross_exposure = 0.0
    margin_exposure = 0.0
    has_margin = False
    for position in positions:
        price = _price_for(
            position["security_code"],
            prices,
            fallback_price=proposed_price if position["security_code"] == security_code else None,
        )
        if price is None:
            all_priced = False
            continue
        notional = position["quantity"] * price
        gross_exposure += abs(notional)
        if position["position_type"] in {"margin_long", "margin_short"}:
            has_margin = True
            margin_exposure += abs(notional)

    before: dict[str, Any] = {
        "position_notional": position_notional,
        "cash_available": None,
        "gross_exposure": gross_exposure if all_priced else None,
        "margin_exposure": margin_exposure if all_priced and has_margin else (0.0 if all_priced else None),
        "portfolio_equity": None,
        "portfolio_as_of": portfolio_copy.get("as_of"),
        "verification_status": portfolio_copy.get("verification_status"),
        "authority": portfolio_copy.get("authority"),
    }
    if cash_available is not None:
        before["cash_available"] = _finite_positive(cash_available, field="cash_available")
    if portfolio_equity is not None:
        before["portfolio_equity"] = _finite_positive(portfolio_equity, field="portfolio_equity", allow_zero=False)

    base_snapshot = str(portfolio_copy.get("base_snapshot") or "").strip()
    portfolio_ref = base_snapshot or f"portfolio:{portfolio_copy.get('as_of', 'unknown')}"
    return {
        "captured_at": captured_at,
        "portfolio_ref": portfolio_ref,
        "proposed_action": proposed,
        "before": before,
        "rules": deepcopy(dict(rules or {})),
        "data_status": canonical_data_status(portfolio_copy, captured_at=captured_at, max_age_days=max_age_days),
    }


def calculate_trade_impact_from_canonical(
    portfolio: Mapping[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    payload = build_preflight_payload_from_canonical(portfolio, **kwargs)
    return calculate_trade_impact(payload)
