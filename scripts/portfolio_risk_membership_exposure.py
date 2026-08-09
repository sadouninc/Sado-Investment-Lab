from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Mapping


class MembershipExposureError(ValueError):
    pass


ACTIONS = {"BUY", "ADD", "REDUCE", "SELL"}
POSITION_TYPES = {"cash", "margin_long", "margin_short"}
ACCOUNT_TYPES = {"CASH", "MARGIN", "UNKNOWN"}


def _finite_positive(value: Any, *, field: str, allow_zero: bool = True) -> float:
    if isinstance(value, bool):
        raise MembershipExposureError(f"{field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise MembershipExposureError(f"{field} must be numeric") from exc
    if not math.isfinite(number):
        raise MembershipExposureError(f"{field} must be finite")
    if number < 0 or (not allow_zero and number == 0):
        raise MembershipExposureError(f"{field} must be positive")
    return number


def _validated_membership_catalog(catalog: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    authority = str(catalog.get("authority") or "").strip()
    source_ref = str(catalog.get("source_ref") or "").strip()
    if authority != "CANONICAL":
        raise MembershipExposureError("membership authority must be CANONICAL")
    if not source_ref:
        raise MembershipExposureError("membership source_ref is required")
    raw = catalog.get("memberships")
    if not isinstance(raw, Mapping):
        raise MembershipExposureError("memberships must be an object")

    result: dict[str, dict[str, Any]] = {}
    for raw_code, value in raw.items():
        code = str(raw_code).strip()
        if not code or not isinstance(value, Mapping):
            raise MembershipExposureError("invalid membership entry")
        themes = value.get("themes")
        sector = value.get("sector")
        if themes is None or not isinstance(themes, list):
            raise MembershipExposureError(f"membership[{code}].themes must be an array")
        cleaned_themes: list[str] = []
        for theme in themes:
            text = str(theme or "").strip()
            if not text:
                raise MembershipExposureError(f"membership[{code}] contains empty theme")
            if text in cleaned_themes:
                raise MembershipExposureError(f"membership[{code}] contains duplicate theme")
            cleaned_themes.append(text)
        sector_text = None if sector is None else str(sector).strip()
        if sector is not None and not sector_text:
            raise MembershipExposureError(f"membership[{code}].sector must not be empty")
        result[code] = {"themes": cleaned_themes, "sector": sector_text}
    return result


def _position_notionals(
    portfolio: Mapping[str, Any], market_prices: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    positions = portfolio.get("positions")
    if not isinstance(positions, list):
        raise MembershipExposureError("portfolio.positions must be an array")

    valued: list[dict[str, Any]] = []
    missing_prices: list[str] = []
    for index, item in enumerate(positions):
        if not isinstance(item, Mapping):
            raise MembershipExposureError(f"portfolio.positions[{index}] must be an object")
        code = str(item.get("security_code") or "").strip()
        position_type = str(item.get("position_type") or "").strip()
        if not code:
            raise MembershipExposureError(f"portfolio.positions[{index}].security_code is required")
        if position_type not in POSITION_TYPES:
            raise MembershipExposureError(f"unsupported position_type: {position_type}")
        quantity = _finite_positive(
            item.get("quantity"), field=f"portfolio.positions[{index}].quantity", allow_zero=False
        )
        if code not in market_prices:
            missing_prices.append(code)
            valued.append(
                {
                    "security_code": code,
                    "position_type": position_type,
                    "quantity": quantity,
                    "notional": None,
                }
            )
            continue
        price = _finite_positive(market_prices[code], field=f"market_prices[{code}]", allow_zero=False)
        valued.append(
            {
                "security_code": code,
                "position_type": position_type,
                "quantity": quantity,
                "notional": quantity * price,
            }
        )
    return valued, sorted(set(missing_prices))


def _aggregate_known(
    valued_positions: list[dict[str, Any]],
    memberships: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, float], dict[str, float], list[str]]:
    theme_totals: dict[str, float] = {}
    sector_totals: dict[str, float] = {}
    unknown_membership: list[str] = []

    for position in valued_positions:
        code = position["security_code"]
        notional = position["notional"]
        membership = memberships.get(code)
        if membership is None:
            unknown_membership.append(code)
            continue
        if notional is None:
            continue
        for theme in membership["themes"]:
            theme_totals[theme] = theme_totals.get(theme, 0.0) + notional
        sector = membership.get("sector")
        if sector is not None:
            sector_totals[sector] = sector_totals.get(sector, 0.0) + notional
    return theme_totals, sector_totals, sorted(set(unknown_membership))


def _target_long_quantity(
    valued_positions: list[dict[str, Any]], *, security_code: str, account_type: str
) -> float:
    if account_type not in ACCOUNT_TYPES:
        raise MembershipExposureError("invalid proposed account_type")
    matching = [p for p in valued_positions if p["security_code"] == security_code]
    if any(p["position_type"] == "margin_short" for p in matching):
        raise MembershipExposureError(
            "margin_short target is outside v1 theme/sector action semantics"
        )
    if account_type == "CASH":
        return sum(p["quantity"] for p in matching if p["position_type"] == "cash")
    if account_type == "MARGIN":
        return sum(p["quantity"] for p in matching if p["position_type"] == "margin_long")
    return sum(
        p["quantity"] for p in matching if p["position_type"] in {"cash", "margin_long"}
    )


def _category_projection(
    *, before: float, delta: float, equity: float | None, complete: bool
) -> dict[str, Any]:
    after = before + delta
    if after < -1e-9:
        raise MembershipExposureError("category exposure would become negative")
    after = max(after, 0.0)
    return {
        "known_before_notional": before,
        "known_after_notional": after,
        "before_weight": None if equity is None or not complete else before / equity,
        "after_weight": None if equity is None or not complete else after / equity,
        "status": "CURRENT" if complete else "UNKNOWN",
    }


def calculate_membership_exposure(
    portfolio: Mapping[str, Any],
    *,
    proposed_action: Mapping[str, Any],
    market_prices: Mapping[str, Any],
    membership_catalog: Mapping[str, Any],
    portfolio_equity: Any | None = None,
) -> dict[str, Any]:
    """Calculate theme/sector exposure only from explicit canonical membership.

    Unknown membership or missing market prices never count as zero. Known subtotals are
    retained for diagnostics, but aggregate weights remain UNKNOWN until coverage is complete.
    v1 treats long/cash notionals as gross category exposure and fails closed for target shorts.
    """

    portfolio_copy = deepcopy(dict(portfolio))
    action_copy = deepcopy(dict(proposed_action))
    memberships = _validated_membership_catalog(membership_catalog)
    valued_positions, missing_prices = _position_notionals(portfolio_copy, market_prices)
    theme_before, sector_before, unknown_membership = _aggregate_known(
        valued_positions, memberships
    )

    code = str(action_copy.get("security_code") or "").strip()
    action = str(action_copy.get("action") or "").strip()
    account_type = str(action_copy.get("account_type") or "UNKNOWN").strip()
    if not code:
        raise MembershipExposureError("proposed_action.security_code is required")
    if action not in ACTIONS:
        raise MembershipExposureError("invalid proposed action")
    if account_type not in ACCOUNT_TYPES:
        raise MembershipExposureError("invalid proposed account_type")
    quantity = _finite_positive(
        action_copy.get("quantity"), field="proposed_action.quantity", allow_zero=False
    )
    price = _finite_positive(
        action_copy.get("price"), field="proposed_action.price", allow_zero=False
    )
    notional = quantity * price
    sign = 1.0 if action in {"BUY", "ADD"} else -1.0

    current_target_quantity = _target_long_quantity(
        valued_positions, security_code=code, account_type=account_type
    )
    if action in {"REDUCE", "SELL"} and quantity > current_target_quantity + 1e-9:
        raise MembershipExposureError("proposed reduction exceeds current target position")

    target_membership = memberships.get(code)
    target_membership_status = "CURRENT" if target_membership is not None else "UNKNOWN"
    if target_membership is None and code not in unknown_membership:
        unknown_membership.append(code)
        unknown_membership.sort()

    equity = (
        None
        if portfolio_equity is None
        else _finite_positive(portfolio_equity, field="portfolio_equity", allow_zero=False)
    )
    complete = not unknown_membership and not missing_prices

    theme_results: dict[str, dict[str, Any]] = {}
    sector_results: dict[str, dict[str, Any]] = {}

    all_themes = set(theme_before)
    all_sectors = set(sector_before)
    if target_membership is not None:
        all_themes.update(target_membership["themes"])
        if target_membership.get("sector") is not None:
            all_sectors.add(target_membership["sector"])

    for theme in sorted(all_themes):
        delta = (
            sign * notional
            if target_membership is not None and theme in target_membership["themes"]
            else 0.0
        )
        theme_results[theme] = _category_projection(
            before=theme_before.get(theme, 0.0),
            delta=delta,
            equity=equity,
            complete=complete,
        )

    for sector in sorted(all_sectors):
        delta = (
            sign * notional
            if target_membership is not None and sector == target_membership.get("sector")
            else 0.0
        )
        sector_results[sector] = _category_projection(
            before=sector_before.get(sector, 0.0),
            delta=delta,
            equity=equity,
            complete=complete,
        )

    return {
        "membership_source_ref": membership_catalog.get("source_ref"),
        "membership_authority": membership_catalog.get("authority"),
        "target_security_code": code,
        "target_membership_status": target_membership_status,
        "theme_exposure": theme_results,
        "sector_exposure": sector_results,
        "coverage": {
            "status": "CURRENT" if complete else "UNKNOWN",
            "unknown_membership_security_codes": unknown_membership,
            "missing_price_security_codes": missing_prices,
        },
        "trade_action": None,
    }
