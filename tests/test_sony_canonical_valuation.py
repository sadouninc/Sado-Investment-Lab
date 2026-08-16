from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from scripts.boj_market_data import PROVIDER_CREDENTIAL_MISSING, PROVIDER_OK, PROVIDER_UNAVAILABLE, MarketDataRecord
from scripts.canonical_market_data import PRICE_INTRADAY, canonical_from_daily_record
from scripts.sony_canonical_valuation import (
    CURRENT_VALUATION_AVAILABLE,
    CURRENT_VALUATION_UNKNOWN,
    SonyValuationScenario,
    build_sony_canonical_valuation,
)


MARKET_DATE = date(2026, 8, 14)


def _daily(*, market_date: date = MARKET_DATE, source_timestamp: str = "2026-08-15T08:00:00+09:00", basis: str = "split_adjusted") -> MarketDataRecord:
    return MarketDataRecord(
        instrument_code="6758",
        instrument_kind="security",
        market_date=market_date,
        source="JQUANTS_V2",
        source_timestamp=source_timestamp,
        open=3990.0,
        high=4050.0,
        low=3980.0,
        close=4030.0,
        volume=10_000_000.0,
        adjustment_basis=basis,
    )


def _canonical(
    *,
    provider_status: str = PROVIDER_OK,
    not_market_truth: bool = False,
    security_id: str = "JP:6758",
    market_date: date = MARKET_DATE,
    source_timestamp: str = "2026-08-15T08:00:00+09:00",
    basis: str = "split_adjusted",
):
    return canonical_from_daily_record(
        _daily(market_date=market_date, source_timestamp=source_timestamp, basis=basis),
        security_id=security_id,
        provider_status=provider_status,
        not_market_truth=not_market_truth,
    )


def _scenario() -> SonyValuationScenario:
    return SonyValuationScenario(
        scenario_eps=200.0,
        fair_per_low=18.0,
        fair_per_high=20.0,
        scenario_as_of="2026-08-16",
    )


def _run(record=None, *, scenario=None, expected_date: date = MARKET_DATE, basis: str = "split_adjusted"):
    return build_sony_canonical_valuation(
        record or _canonical(),
        expected_trading_date=expected_date,
        expected_adjustment_basis=basis,
        scenario=scenario or _scenario(),
    )


def test_exact_fresh_canonical_price_drives_both_consumers_atomically() -> None:
    run = _run()
    board = run.decision_board
    fair_per = run.fair_per_consumer

    assert board is fair_per
    assert board.current_valuation_status == CURRENT_VALUATION_AVAILABLE
    assert board.current_price == 4030.0
    assert board.current_per == pytest.approx(20.15)
    assert board.fair_value_low == 3600.0
    assert board.fair_value_high == 4000.0
    assert board.gap_to_fair_low == pytest.approx((3600.0 - 4030.0) / 4030.0)
    assert board.gap_to_fair_high == pytest.approx((4000.0 - 4030.0) / 4030.0)
    assert board.canonical_identity.security_id == "JP:6758"
    assert board.canonical_identity.trading_date == MARKET_DATE
    assert board.price_as_of != board.scenario_as_of
    assert board.entry_zone is None
    assert board.decision_action is None


def test_stale_price_keeps_research_fair_value_but_current_valuation_unknown() -> None:
    run = _run(_canonical(source_timestamp="2026-08-16T13:00:00+09:00"))
    result = run.decision_board

    assert result.current_valuation_status == CURRENT_VALUATION_UNKNOWN
    assert result.current_price is None
    assert result.current_per is None
    assert result.gap_to_fair_low is None
    assert result.gap_to_fair_high is None
    assert result.fair_value_low == 3600.0
    assert result.fair_value_high == 4000.0
    assert "STALE_SOURCE" in result.validation_reasons


def test_naive_timestamp_is_unknown_without_fallback() -> None:
    result = _run(_canonical(source_timestamp="2026-08-15T08:00:00")).decision_board
    assert result.current_valuation_status == CURRENT_VALUATION_UNKNOWN
    assert result.current_price is None
    assert "NAIVE_TIMESTAMP" in result.validation_reasons


def test_previous_year_price_is_rejected() -> None:
    previous = _canonical(
        market_date=date(2025, 8, 14),
        source_timestamp="2025-08-15T08:00:00+09:00",
    )
    result = _run(previous).decision_board
    assert result.current_price is None
    assert "TRADING_DATE_MISMATCH" in result.validation_reasons


def test_security_identity_mismatch_is_rejected_even_when_symbol_matches() -> None:
    result = _run(_canonical(security_id="JP:6753")).decision_board
    assert result.current_price is None
    assert "SECURITY_ID_MISMATCH" in result.validation_reasons


def test_price_type_mismatch_is_rejected() -> None:
    record = replace(_canonical(), price_type=PRICE_INTRADAY)
    result = _run(record).decision_board
    assert result.current_price is None
    assert "PRICE_TYPE_MISMATCH" in result.validation_reasons


def test_adjustment_basis_mismatch_is_rejected() -> None:
    result = _run(_canonical(basis="raw")).decision_board
    assert result.current_price is None
    assert "ADJUSTMENT_BASIS_MISMATCH" in result.validation_reasons


@pytest.mark.parametrize("provider_status", [PROVIDER_CREDENTIAL_MISSING, PROVIDER_UNAVAILABLE])
def test_provider_failure_never_falls_back(provider_status: str) -> None:
    result = _run(_canonical(provider_status=provider_status)).decision_board
    assert result.current_price is None
    assert result.current_per is None
    assert any(reason.startswith("PROVIDER_") for reason in result.validation_reasons)


def test_fixture_market_data_never_becomes_current_valuation() -> None:
    result = _run(_canonical(not_market_truth=True)).decision_board
    assert result.current_price is None
    assert result.current_per is None
    assert "NOT_MARKET_TRUTH" in result.validation_reasons


def test_unknown_scenario_is_not_auto_upgraded_by_fresh_price() -> None:
    scenario = SonyValuationScenario(
        scenario_eps=None,
        fair_per_low=18.0,
        fair_per_high=20.0,
        scenario_as_of=None,
    )
    result = _run(scenario=scenario).decision_board

    assert result.current_valuation_status == CURRENT_VALUATION_UNKNOWN
    assert result.current_price == 4030.0
    assert result.current_per is None
    assert result.fair_value_low is None
    assert result.gap_to_fair_low is None
    assert "SCENARIO_INPUT_UNKNOWN" in result.validation_reasons


def test_non_positive_price_fails_closed() -> None:
    result = _run(replace(_canonical(), price=0.0)).decision_board
    assert result.current_price is None
    assert result.current_per is None
    assert "PRICE_NON_POSITIVE" in result.validation_reasons
