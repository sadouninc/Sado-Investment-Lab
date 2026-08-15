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
