from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Mapping

from scripts.portfolio_risk_preflight_adapter import (
    PortfolioRiskAdapterError,
    calculate_trade_impact_from_canonical,
    canonical_data_status,
)


ACTIONS = {"BUY", "SELL"}
ACCOUNT_TYPES = {"CASH", "MARGIN", "UNKNOWN"}
PRICE_STATUSES = {"CURRENT", "STALE", "UNAVAILABLE", "UNKNOWN"}


class WhatIfIntentError(ValueError):
    def __init__(self, message: str, *, state: str = "INVALID_INPUT") -> None:
        super().__init__(message)
        self.state = state


def _positive_integer(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise WhatIfIntentError(f"{field} must be a positive integer")
    return value


def _positive_finite(value: Any, *, field: str) -> float:
    if isinstance(value, bool):
        raise WhatIfIntentError(f"{field} must be a positive finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise WhatIfIntentError(f"{field} must be a positive finite number") from exc
    if not math.isfinite(number) or number <= 0:
        raise WhatIfIntentError(f"{field} must be a positive finite number")
    return number


def validate_intent(intent: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize an ephemeral What-if intent without turning it into an order.

    A manually entered price is an explicit assumption. If the caller labels that
    price as a market quote via ``price_status``, stale/unavailable/unknown quotes
    fail closed instead of being treated as a usable current price.
    """

    source = deepcopy(dict(intent))
    security_code = str(source.get("security_code") or "").strip()
    if not security_code:
        raise WhatIfIntentError("security_code is required")

    action = str(source.get("action") or "").strip().upper()
    if action not in ACTIONS:
        raise WhatIfIntentError("action must be BUY or SELL")

    quantity = _positive_integer(source.get("quantity"), field="quantity")
    price = _positive_finite(source.get("price"), field="price")

    account_type = str(source.get("account_type") or "UNKNOWN").strip().upper()
    if account_type not in ACCOUNT_TYPES:
        raise WhatIfIntentError("account_type must be CASH, MARGIN, or UNKNOWN")

    price_status_raw = source.get("price_status")
    price_status = None
    if price_status_raw not in (None, ""):
        price_status = str(price_status_raw).strip().upper()
        if price_status not in PRICE_STATUSES:
            raise WhatIfIntentError("unsupported price_status")
        if price_status == "STALE":
            raise WhatIfIntentError(
                "price source is stale; refresh or enter an explicit assumption",
                state="SOURCE_STALE",
            )
        if price_status in {"UNAVAILABLE", "UNKNOWN"}:
            raise WhatIfIntentError(
                "price source is unavailable; enter a verified price assumption",
                state="SOURCE_UNAVAILABLE",
            )

    return {
        "security_code": security_code,
        "action": action,
        "quantity": quantity,
        "price": price,
        "account_type": account_type,
        "price_source": str(source.get("price_source") or "USER_INPUT").strip() or "USER_INPUT",
        "price_as_of": str(source.get("price_as_of") or "").strip() or None,
        "price_status": price_status,
    }


def _verified_long_quantity(
    portfolio: Mapping[str, Any],
    *,
    security_code: str,
    account_type: str,
    captured_at: str,
    max_age_days: int | None,
) -> float:
    verification = str(portfolio.get("verification_status") or "").strip().upper()
    if not verification:
        raise WhatIfIntentError(
            "canonical portfolio verification_status is unavailable",
            state="SOURCE_UNAVAILABLE",
        )
    if verification != "VERIFIED":
        raise WhatIfIntentError(
            f"SELL requires a VERIFIED canonical portfolio; got {verification}",
            state="NOT_JUDGABLE",
        )
    if not str(portfolio.get("authority") or "").strip():
        raise WhatIfIntentError(
            "canonical portfolio authority is unavailable",
            state="SOURCE_UNAVAILABLE",
        )
    if not str(portfolio.get("base_snapshot") or "").strip():
        raise WhatIfIntentError(
            "canonical portfolio snapshot ref is unavailable",
            state="SOURCE_UNAVAILABLE",
        )
    try:
        data_status = canonical_data_status(
            portfolio, captured_at=captured_at, max_age_days=max_age_days
        )
    except PortfolioRiskAdapterError as exc:
        raise WhatIfIntentError(str(exc), state="SOURCE_UNAVAILABLE") from exc
    if data_status == "STALE":
        raise WhatIfIntentError(
            "canonical portfolio is stale; refresh before SELL holding checks",
            state="SOURCE_STALE",
        )
    if data_status != "CURRENT":
        raise WhatIfIntentError(
            "canonical portfolio is not current enough for SELL holding checks",
            state="NOT_JUDGABLE",
        )

    positions = portfolio.get("positions")
    if not isinstance(positions, list):
        raise WhatIfIntentError("canonical portfolio positions are unavailable", state="SOURCE_UNAVAILABLE")

    if account_type == "UNKNOWN":
        raise WhatIfIntentError(
            "SELL requires an explicit CASH or MARGIN account context; short selling is not inferred",
            state="NOT_JUDGABLE",
        )

    wanted_type = "cash" if account_type == "CASH" else "margin_long"
    total = 0.0
    for row in positions:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("security_code") or "").strip() != security_code:
            continue
        if str(row.get("position_type") or "").strip() == "margin_short":
            raise WhatIfIntentError(
                "target has a margin short position; SELL semantics are ambiguous",
                state="NOT_JUDGABLE",
            )
        if str(row.get("position_type") or "").strip() == wanted_type:
            try:
                quantity = float(row.get("quantity"))
            except (TypeError, ValueError):
                raise WhatIfIntentError(
                    "canonical holding quantity is invalid", state="SOURCE_UNAVAILABLE"
                )
            if isinstance(row.get("quantity"), bool) or not math.isfinite(quantity) or quantity <= 0:
                raise WhatIfIntentError(
                    "canonical holding quantity is invalid", state="SOURCE_UNAVAILABLE"
                )
            total += quantity
    return total


def preview_what_if(
    portfolio: Mapping[str, Any],
    intent: Mapping[str, Any],
    *,
    captured_at: str,
    market_prices: Mapping[str, Any] | None = None,
    cash_available: Any | None = None,
    portfolio_equity: Any | None = None,
    max_age_days: int | None = None,
    rules: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run #233 Risk Preflight as a read-only ephemeral preview.

    This function deliberately delegates all portfolio-impact math and guardrail
    semantics to the existing #233 adapter/calculator. It does not create a
    Decision Journal record, Execution Intent, Portfolio mutation, or order.
    """

    portfolio_before = deepcopy(dict(portfolio))
    intent_before = deepcopy(dict(intent))
    normalized = validate_intent(intent_before)

    if normalized["action"] == "SELL":
        holding = _verified_long_quantity(
            portfolio_before,
            security_code=normalized["security_code"],
            account_type=normalized["account_type"],
            captured_at=captured_at,
            max_age_days=max_age_days,
        )
        if normalized["quantity"] > holding:
            raise WhatIfIntentError(
                f"SELL quantity {normalized['quantity']} exceeds verified holding {holding:g}",
                state="NOT_JUDGABLE",
            )

    proposed_action = {
        "security_code": normalized["security_code"],
        "action": normalized["action"],
        "quantity": normalized["quantity"],
        "price": normalized["price"],
        "account_type": normalized["account_type"],
    }

    try:
        impact = calculate_trade_impact_from_canonical(
            portfolio_before,
            captured_at=captured_at,
            proposed_action=proposed_action,
            market_prices=market_prices,
            cash_available=cash_available,
            portfolio_equity=portfolio_equity,
            max_age_days=max_age_days,
            rules=rules,
        )
    except PortfolioRiskAdapterError as exc:
        raise WhatIfIntentError(str(exc), state="NOT_JUDGABLE") from exc

    if portfolio_before != dict(portfolio) or intent_before != dict(intent):
        raise RuntimeError("What-if preview mutated caller-owned canonical/input data")

    return {
        "state": "CALCULATED",
        "ephemeral": True,
        "is_order": False,
        "intent": normalized,
        "risk_preflight": impact,
        "canonical_mutations": [],
    }
