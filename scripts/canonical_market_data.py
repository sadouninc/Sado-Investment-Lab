from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from scripts.boj_market_data import (
    FRESHNESS_STALE_SOURCE,
    FRESHNESS_UNKNOWN,
    FRESHNESS_VERIFIED_SAME_DAY,
    FRESHNESS_VERIFIED_T_PLUS_1,
    PROVIDER_CREDENTIAL_MISSING,
    PROVIDER_OK,
    PROVIDER_UNAVAILABLE,
    MarketDataRecord,
    _observation_freshness,
)

IDENTITY_VERIFIED = "VERIFIED"
IDENTITY_FAILED = "FAILED"
IDENTITY_UNKNOWN = "UNKNOWN"
CANONICAL_FRESH = "FRESH"
CANONICAL_STALE = "STALE"
CANONICAL_UNKNOWN = "UNKNOWN"
PRICE_CLOSE = "close"
PRICE_INTRADAY = "intraday"


@dataclass(frozen=True)
class CanonicalMarketDataRecord:
    security_id: str
    symbol: str
    exchange: str
    price: float
    price_type: str
    price_as_of: str
    trading_date: date
    currency: str
    adjustment_basis: str
    source: str
    source_observed_at: str
    provider_status: str = PROVIDER_OK
    not_market_truth: bool = False


@dataclass(frozen=True)
class PriceIdentityExpectation:
    security_id: str
    symbol: str
    exchange: str
    trading_date: date
    price_type: str
    currency: str
    adjustment_basis: str


@dataclass(frozen=True)
class PriceIdentityGateResult:
    identity_status: str
    freshness_status: str
    provider_status: str
    expected_trading_date: date
    observed_trading_date: date
    expected_adjustment_basis: str
    observed_adjustment_basis: str
    validation_reasons: tuple[str, ...]
    usable_for_current_valuation: bool
    not_market_truth: bool


def canonical_from_daily_record(
    record: MarketDataRecord,
    *,
    security_id: str,
    exchange: str = "TSE",
    currency: str = "JPY",
    provider_status: str = PROVIDER_OK,
    not_market_truth: bool = False,
) -> CanonicalMarketDataRecord:
    """Normalize one validated provider daily record without promoting it to truth."""

    return CanonicalMarketDataRecord(
        security_id=security_id,
        symbol=record.instrument_code,
        exchange=exchange,
        price=record.close,
        price_type=PRICE_CLOSE,
        price_as_of=f"{record.market_date.isoformat()}T15:30:00+09:00",
        trading_date=record.market_date,
        currency=currency,
        adjustment_basis=record.adjustment_basis,
        source=record.source,
        source_observed_at=record.source_timestamp,
        provider_status=provider_status,
        not_market_truth=not_market_truth,
    )


def _freshness(record: CanonicalMarketDataRecord) -> tuple[str, str | None]:
    try:
        observed = datetime.fromisoformat(record.source_observed_at)
    except ValueError:
        return CANONICAL_UNKNOWN, "SOURCE_TIMESTAMP_INVALID"
    if observed.tzinfo is None or observed.utcoffset() is None:
        return CANONICAL_UNKNOWN, "NAIVE_TIMESTAMP"

    probe = MarketDataRecord(
        instrument_code=record.symbol,
        instrument_kind="security",
        market_date=record.trading_date,
        source=record.source,
        source_timestamp=record.source_observed_at,
        open=record.price,
        high=record.price,
        low=record.price,
        close=record.price,
        volume=None,
        adjustment_basis=record.adjustment_basis,
    )
    state = _observation_freshness(probe, record.trading_date)
    if state in {FRESHNESS_VERIFIED_SAME_DAY, FRESHNESS_VERIFIED_T_PLUS_1}:
        return CANONICAL_FRESH, None
    if state == FRESHNESS_STALE_SOURCE:
        return CANONICAL_STALE, "STALE_SOURCE"
    if state == FRESHNESS_UNKNOWN:
        return CANONICAL_UNKNOWN, "SOURCE_TIMESTAMP_INVALID"
    return CANONICAL_UNKNOWN, "SOURCE_CONFLICT"


def evaluate_price_identity_gate(
    record: CanonicalMarketDataRecord,
    *,
    expected: PriceIdentityExpectation,
) -> PriceIdentityGateResult:
    reasons: list[str] = []
    identity_failed = False

    checks = (
        (record.security_id == expected.security_id, "SECURITY_ID_MISMATCH"),
        (record.symbol == expected.symbol, "SYMBOL_MISMATCH"),
        (record.exchange == expected.exchange, "EXCHANGE_MISMATCH"),
        (record.trading_date == expected.trading_date, "TRADING_DATE_MISMATCH"),
        (record.price_type == expected.price_type, "PRICE_TYPE_MISMATCH"),
        (record.currency == expected.currency, "CURRENCY_MISMATCH"),
        (record.adjustment_basis == expected.adjustment_basis, "ADJUSTMENT_BASIS_MISMATCH"),
    )
    for passed, reason in checks:
        if not passed:
            identity_failed = True
            reasons.append(reason)

    freshness_status, freshness_reason = _freshness(record)
    if freshness_reason:
        reasons.append(freshness_reason)

    if record.provider_status == PROVIDER_CREDENTIAL_MISSING:
        reasons.append("PROVIDER_CREDENTIAL_MISSING")
    elif record.provider_status == PROVIDER_UNAVAILABLE:
        reasons.append("PROVIDER_UNAVAILABLE")
    elif record.provider_status != PROVIDER_OK:
        reasons.append("PROVIDER_STATUS_UNKNOWN")

    if record.not_market_truth:
        reasons.append("NOT_MARKET_TRUTH")

    identity_status = IDENTITY_FAILED if identity_failed else IDENTITY_VERIFIED
    usable = (
        identity_status == IDENTITY_VERIFIED
        and freshness_status == CANONICAL_FRESH
        and record.provider_status == PROVIDER_OK
        and not record.not_market_truth
    )
    return PriceIdentityGateResult(
        identity_status=identity_status,
        freshness_status=freshness_status,
        provider_status=record.provider_status,
        expected_trading_date=expected.trading_date,
        observed_trading_date=record.trading_date,
        expected_adjustment_basis=expected.adjustment_basis,
        observed_adjustment_basis=record.adjustment_basis,
        validation_reasons=tuple(reasons),
        usable_for_current_valuation=usable,
        not_market_truth=record.not_market_truth,
    )
