from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite

from scripts.boj_market_data import PROVIDER_OK
from scripts.canonical_market_data import (
    CANONICAL_FRESH,
    IDENTITY_VERIFIED,
    PRICE_CLOSE,
    CanonicalMarketDataRecord,
    PriceIdentityExpectation,
    evaluate_price_identity_gate,
)

SONY_SECURITY_ID = "JP:6758"
SONY_SYMBOL = "6758"
SONY_EXCHANGE = "TSE"
SONY_CURRENCY = "JPY"
CURRENT_VALUATION_AVAILABLE = "AVAILABLE"
CURRENT_VALUATION_UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SonyValuationScenario:
    """Research-owned scenario inputs.

    ``scenario_as_of`` remains distinct from the canonical market price timestamp.
    This consumer does not decide whether a Research scenario should be upgraded.
    """

    scenario_eps: float | None
    fair_per_low: float | None
    fair_per_high: float | None
    scenario_as_of: str | None


@dataclass(frozen=True)
class CanonicalPriceIdentity:
    security_id: str
    symbol: str
    exchange: str
    trading_date: date
    price_type: str
    adjustment_basis: str
    source: str
    source_observed_at: str


@dataclass(frozen=True)
class SonyCanonicalValuation:
    current_valuation_status: str
    current_price: float | None
    current_per: float | None
    fair_value_low: float | None
    fair_value_high: float | None
    gap_to_fair_low: float | None
    gap_to_fair_high: float | None
    price_as_of: str | None
    scenario_as_of: str | None
    canonical_identity: CanonicalPriceIdentity
    validation_reasons: tuple[str, ...]
    entry_zone: None = None
    decision_action: None = None


@dataclass(frozen=True)
class SonyValuationConsumers:
    """Atomic #403/#626 projection from one canonical valuation run."""

    decision_board: SonyCanonicalValuation
    fair_per_consumer: SonyCanonicalValuation


def _identity(record: CanonicalMarketDataRecord) -> CanonicalPriceIdentity:
    return CanonicalPriceIdentity(
        security_id=record.security_id,
        symbol=record.symbol,
        exchange=record.exchange,
        trading_date=record.trading_date,
        price_type=record.price_type,
        adjustment_basis=record.adjustment_basis,
        source=record.source,
        source_observed_at=record.source_observed_at,
    )


def _scenario_values(scenario: SonyValuationScenario) -> tuple[float | None, float | None, tuple[str, ...]]:
    values = (scenario.scenario_eps, scenario.fair_per_low, scenario.fair_per_high)
    if any(value is None for value in values):
        return None, None, ("SCENARIO_INPUT_UNKNOWN",)

    eps = float(scenario.scenario_eps)
    low = float(scenario.fair_per_low)
    high = float(scenario.fair_per_high)
    if not all(isfinite(value) for value in (eps, low, high)):
        return None, None, ("SCENARIO_INPUT_INVALID",)
    if eps <= 0 or low <= 0 or high <= 0 or low > high:
        return None, None, ("SCENARIO_INPUT_INVALID",)
    return eps * low, eps * high, ()


def build_sony_canonical_valuation(
    record: CanonicalMarketDataRecord,
    *,
    expected_trading_date: date,
    expected_adjustment_basis: str,
    scenario: SonyValuationScenario,
) -> SonyValuationConsumers:
    """Project one canonical Sony price into #403 and #626 consumers.

    No provider/Web/legacy-price fallback exists here. Current-price valuation is
    available only when the shared Price Identity Gate passes. Fair Value Range
    remains Research-derived (scenario EPS x Fair PER) and may therefore remain
    available when current market price is not usable. Relative fair-value gaps
    use ``(fair_value - current_price) / current_price``.
    """

    expected = PriceIdentityExpectation(
        security_id=SONY_SECURITY_ID,
        symbol=SONY_SYMBOL,
        exchange=SONY_EXCHANGE,
        trading_date=expected_trading_date,
        price_type=PRICE_CLOSE,
        currency=SONY_CURRENCY,
        adjustment_basis=expected_adjustment_basis,
    )
    gate = evaluate_price_identity_gate(record, expected=expected)
    identity = _identity(record)
    fair_low, fair_high, scenario_reasons = _scenario_values(scenario)

    gate_pass = (
        gate.usable_for_current_valuation
        and gate.identity_status == IDENTITY_VERIFIED
        and gate.freshness_status == CANONICAL_FRESH
        and gate.provider_status == PROVIDER_OK
        and not gate.not_market_truth
    )
    reasons = list(gate.validation_reasons)
    reasons.extend(scenario_reasons)

    if not gate_pass:
        valuation = SonyCanonicalValuation(
            current_valuation_status=CURRENT_VALUATION_UNKNOWN,
            current_price=None,
            current_per=None,
            fair_value_low=fair_low,
            fair_value_high=fair_high,
            gap_to_fair_low=None,
            gap_to_fair_high=None,
            price_as_of=None,
            scenario_as_of=scenario.scenario_as_of,
            canonical_identity=identity,
            validation_reasons=tuple(reasons),
        )
        return SonyValuationConsumers(valuation, valuation)

    if not isfinite(record.price) or record.price <= 0:
        reasons.append("PRICE_NON_POSITIVE")
        valuation = SonyCanonicalValuation(
            current_valuation_status=CURRENT_VALUATION_UNKNOWN,
            current_price=None,
            current_per=None,
            fair_value_low=fair_low,
            fair_value_high=fair_high,
            gap_to_fair_low=None,
            gap_to_fair_high=None,
            price_as_of=None,
            scenario_as_of=scenario.scenario_as_of,
            canonical_identity=identity,
            validation_reasons=tuple(reasons),
        )
        return SonyValuationConsumers(valuation, valuation)

    if fair_low is None or fair_high is None or scenario.scenario_eps is None:
        valuation = SonyCanonicalValuation(
            current_valuation_status=CURRENT_VALUATION_UNKNOWN,
            current_price=record.price,
            current_per=None,
            fair_value_low=None,
            fair_value_high=None,
            gap_to_fair_low=None,
            gap_to_fair_high=None,
            price_as_of=record.price_as_of,
            scenario_as_of=scenario.scenario_as_of,
            canonical_identity=identity,
            validation_reasons=tuple(reasons),
        )
        return SonyValuationConsumers(valuation, valuation)

    eps = float(scenario.scenario_eps)
    current_per = record.price / eps
    valuation = SonyCanonicalValuation(
        current_valuation_status=CURRENT_VALUATION_AVAILABLE,
        current_price=record.price,
        current_per=current_per,
        fair_value_low=fair_low,
        fair_value_high=fair_high,
        gap_to_fair_low=(fair_low - record.price) / record.price,
        gap_to_fair_high=(fair_high - record.price) / record.price,
        price_as_of=record.price_as_of,
        scenario_as_of=scenario.scenario_as_of,
        canonical_identity=identity,
        validation_reasons=tuple(reasons),
    )
    # Both consumers intentionally receive the exact same immutable result object.
    return SonyValuationConsumers(valuation, valuation)
