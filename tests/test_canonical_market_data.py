from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from scripts.boj_market_data import PROVIDER_CREDENTIAL_MISSING, PROVIDER_OK, MarketDataRecord
from scripts.canonical_market_data import (
    CANONICAL_FRESH,
    CANONICAL_STALE,
    CANONICAL_UNKNOWN,
    IDENTITY_FAILED,
    IDENTITY_VERIFIED,
    PRICE_CLOSE,
    PRICE_INTRADAY,
    PriceIdentityExpectation,
    canonical_from_daily_record,
    evaluate_price_identity_gate,
)


def _sony_daily(*, market_date: date = date(2026, 8, 14), source_timestamp: str = "2026-08-15T08:00:00+09:00", basis: str = "split_adjusted") -> MarketDataRecord:
    return MarketDataRecord(
        instrument_code="6758",
        instrument_kind="security",
        market_date=market_date,
        source="JQUANTS_V2",
        source_timestamp=source_timestamp,
        open=4010.0,
        high=4050.0,
        low=3990.0,
        close=4030.0,
        volume=10_000_000.0,
        adjustment_basis=basis,
    )


def _expected() -> PriceIdentityExpectation:
    return PriceIdentityExpectation(
        security_id="JP:6758",
        symbol="6758",
        exchange="TSE",
        trading_date=date(2026, 8, 14),
        price_type=PRICE_CLOSE,
        currency="JPY",
        adjustment_basis="split_adjusted",
    )


def _canonical(record: MarketDataRecord, *, security_id: str = "JP:6758"):
    return canonical_from_daily_record(
        record,
        security_id=security_id,
        provider_status=PROVIDER_OK,
        not_market_truth=False,
    )


def test_sony_exact_identity_fresh_close_is_usable() -> None:
    record = _canonical(_sony_daily())
    result = evaluate_price_identity_gate(record, expected=_expected())

    assert result.identity_status == IDENTITY_VERIFIED
    assert result.freshness_status == CANONICAL_FRESH
    assert result.validation_reasons == ()
    assert result.usable_for_current_valuation is True


def test_previous_year_same_calendar_date_is_blocked() -> None:
    record = _canonical(
        _sony_daily(market_date=date(2025, 8, 14), source_timestamp="2025-08-15T08:00:00+09:00")
    )
    result = evaluate_price_identity_gate(record, expected=_expected())

    assert result.identity_status == IDENTITY_FAILED
    assert "TRADING_DATE_MISMATCH" in result.validation_reasons
    assert result.usable_for_current_valuation is False


def test_symbol_mismatch_is_blocked() -> None:
    record = _canonical(_sony_daily())
    result = evaluate_price_identity_gate(replace(record, symbol="6753"), expected=_expected())

    assert result.identity_status == IDENTITY_FAILED
    assert "SYMBOL_MISMATCH" in result.validation_reasons
    assert result.usable_for_current_valuation is False


def test_security_id_mismatch_with_matching_symbol_is_blocked() -> None:
    record = _canonical(_sony_daily(), security_id="JP:6753")
    result = evaluate_price_identity_gate(record, expected=_expected())

    assert record.symbol == "6758"
    assert result.identity_status == IDENTITY_FAILED
    assert "SECURITY_ID_MISMATCH" in result.validation_reasons
    assert result.usable_for_current_valuation is False


def test_intraday_when_close_expected_is_blocked() -> None:
    record = _canonical(_sony_daily())
    result = evaluate_price_identity_gate(replace(record, price_type=PRICE_INTRADAY), expected=_expected())

    assert result.identity_status == IDENTITY_FAILED
    assert "PRICE_TYPE_MISMATCH" in result.validation_reasons
    assert result.usable_for_current_valuation is False


def test_stale_source_is_blocked() -> None:
    record = _canonical(_sony_daily(source_timestamp="2026-08-16T13:00:00+09:00"))
    result = evaluate_price_identity_gate(record, expected=_expected())

    assert result.freshness_status == CANONICAL_STALE
    assert "STALE_SOURCE" in result.validation_reasons
    assert result.usable_for_current_valuation is False


def test_split_basis_mismatch_is_blocked() -> None:
    record = _canonical(_sony_daily(basis="raw"))
    result = evaluate_price_identity_gate(record, expected=_expected())

    assert result.identity_status == IDENTITY_FAILED
    assert "ADJUSTMENT_BASIS_MISMATCH" in result.validation_reasons
    assert result.usable_for_current_valuation is False


def test_naive_source_timestamp_is_unknown_and_blocked() -> None:
    record = _canonical(_sony_daily(source_timestamp="2026-08-15T08:00:00"))
    result = evaluate_price_identity_gate(record, expected=_expected())

    assert result.freshness_status == CANONICAL_UNKNOWN
    assert "NAIVE_TIMESTAMP" in result.validation_reasons
    assert result.usable_for_current_valuation is False


def test_fixture_not_market_truth_and_missing_credential_are_blocked() -> None:
    record = canonical_from_daily_record(
        _sony_daily(),
        security_id="JP:6758",
        provider_status=PROVIDER_CREDENTIAL_MISSING,
        not_market_truth=True,
    )
    result = evaluate_price_identity_gate(record, expected=_expected())

    assert result.provider_status == PROVIDER_CREDENTIAL_MISSING
    assert "PROVIDER_CREDENTIAL_MISSING" in result.validation_reasons
    assert "NOT_MARKET_TRUTH" in result.validation_reasons
    assert result.usable_for_current_valuation is False


def test_provenance_must_be_explicit() -> None:
    with pytest.raises(TypeError):
        canonical_from_daily_record(_sony_daily(), security_id="JP:6758")


def test_provider_ok_is_explicitly_preserved() -> None:
    record = _canonical(_sony_daily())
    result = evaluate_price_identity_gate(record, expected=_expected())

    assert result.provider_status == PROVIDER_OK


@pytest.mark.parametrize("symbol", ["6501", "6503", "6622"])
def test_ai_dc_price_fixture_v1_exact_identity_fresh_close_is_usable(symbol: str) -> None:
    trading_date = date(2026, 8, 14)
    source_observed_at = "2026-08-15T08:00:00+09:00"
    security_id = f"JP:{symbol}"

    daily = MarketDataRecord(
        instrument_code=symbol,
        instrument_kind="security",
        market_date=trading_date,
        source="JQUANTS_V2",
        source_timestamp=source_observed_at,
        open=3000.0,
        high=3050.0,
        low=2980.0,
        close=3020.0,
        volume=5_000_000.0,
        adjustment_basis="split_adjusted",
    )
    expected = PriceIdentityExpectation(
        security_id=security_id,
        symbol=symbol,
        exchange="TSE",
        trading_date=trading_date,
        price_type=PRICE_CLOSE,
        currency="JPY",
        adjustment_basis="split_adjusted",
    )
    record = canonical_from_daily_record(
        daily,
        security_id=security_id,
        provider_status=PROVIDER_OK,
        not_market_truth=False,
    )
    result = evaluate_price_identity_gate(record, expected=expected)

    assert result.identity_status == IDENTITY_VERIFIED
    assert result.freshness_status == CANONICAL_FRESH
    assert result.validation_reasons == ()
    assert result.usable_for_current_valuation is True


@pytest.mark.parametrize("symbol", ["6501", "6503", "6622"])
def test_ai_dc_price_fixture_v1_fail_closed_behavior(symbol: str) -> None:
    trading_date = date(2026, 8, 14)
    source_observed_at = "2026-08-15T08:00:00+09:00"
    security_id = f"JP:{symbol}"

    daily = MarketDataRecord(
        instrument_code=symbol,
        instrument_kind="security",
        market_date=trading_date,
        source="JQUANTS_V2",
        source_timestamp=source_observed_at,
        open=3000.0,
        high=3050.0,
        low=2980.0,
        close=3020.0,
        volume=5_000_000.0,
        adjustment_basis="split_adjusted",
    )
    expected = PriceIdentityExpectation(
        security_id=security_id,
        symbol=symbol,
        exchange="TSE",
        trading_date=trading_date,
        price_type=PRICE_CLOSE,
        currency="JPY",
        adjustment_basis="split_adjusted",
    )

    # Stale source timestamp
    stale_record = canonical_from_daily_record(
        replace(daily, source_timestamp="2026-08-16T13:00:00+09:00"),
        security_id=security_id,
        provider_status=PROVIDER_OK,
        not_market_truth=False,
    )
    stale_res = evaluate_price_identity_gate(stale_record, expected=expected)
    assert stale_res.freshness_status == CANONICAL_STALE
    assert stale_res.usable_for_current_valuation is False

    # Identity / symbol mismatch
    mismatch_record = canonical_from_daily_record(
        replace(daily, instrument_code="9999"),
        security_id=security_id,
        provider_status=PROVIDER_OK,
        not_market_truth=False,
    )
    mismatch_res = evaluate_price_identity_gate(mismatch_record, expected=expected)
    assert mismatch_res.identity_status == IDENTITY_FAILED
    assert mismatch_res.usable_for_current_valuation is False

    # Not market truth & provider failure
    fake_record = canonical_from_daily_record(
        daily,
        security_id=security_id,
        provider_status=PROVIDER_CREDENTIAL_MISSING,
        not_market_truth=True,
    )
    fake_res = evaluate_price_identity_gate(fake_record, expected=expected)
    assert fake_res.provider_status == PROVIDER_CREDENTIAL_MISSING
    assert fake_res.not_market_truth is True
    assert fake_res.usable_for_current_valuation is False
