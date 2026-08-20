"""Unit tests for Canonical Market Observation Contract v1 (#460)."""

import pytest
from scripts.market_observation_contract import (
    BestBid,
    BestAsk,
    IndicativeOpen,
    MarketObservationSnapshot,
    ObservationStatus,
    SymbolObservation,
    validate_observation_snapshot,
)


def test_canonical_dataclasses_serialization():
    bid = BestBid(price=1000.0, size=500.0)
    ask = BestAsk(price=1005.0, size=300.0)
    indicative = IndicativeOpen(price=1002.0, special_quote_flag=None)

    sym_obs = SymbolObservation(
        symbol="6758",
        source_timestamp="2026-08-20T08:10:00+09:00",
        last_price=1001.0,
        previous_close=990.0,
        best_bid=bid,
        best_ask=ask,
        indicative_open=indicative,
        status=ObservationStatus.FULL,
    )

    snapshot = MarketObservationSnapshot(
        provider_id="kabu_station_mock",
        observed_at="2026-08-20T08:10:02+09:00",
        symbols={"6758": sym_obs},
        status=ObservationStatus.FULL,
    )

    snapshot_dict = snapshot.to_dict()

    assert snapshot_dict["provider_id"] == "kabu_station_mock"
    assert snapshot_dict["observed_at"] == "2026-08-20T08:10:02+09:00"
    assert "6758" in snapshot_dict["symbols"]

    sym_dict = snapshot_dict["symbols"]["6758"]
    assert sym_dict["best_bid"] == {"price": 1000.0, "size": 500.0}
    assert sym_dict["best_ask"] == {"price": 1005.0, "size": 300.0}
    assert sym_dict["indicative_open"] == {"price": 1002.0, "special_quote_flag": None}
    assert sym_dict["source_timestamp"] == "2026-08-20T08:10:00+09:00"


def test_field_semantic_distinctness():
    """Ensure best_bid, best_ask, and indicative_open are distinct concepts and cannot be derived from each other."""
    snapshot_dict = {
        "provider_id": "test_provider",
        "observed_at": "2026-08-20T08:30:00Z",
        "symbols": {
            "6758": {
                "symbol": "6758",
                "best_bid": {"price": 1000.0, "size": 100.0},
                "indicative_open": {
                    "price": 1000.0,
                    "derived_from": "best_bid",  # Explicit forbidden inference marker
                },
                "status": "FULL",
            }
        },
    }

    res = validate_observation_snapshot(snapshot_dict)
    assert not res.is_valid
    assert res.status == ObservationStatus.UNAVAILABLE
    assert any("cannot be derived/inferred from best_bid" in err for err in res.errors)


def test_forbidden_synthesized_data():
    """Synthesizing or fabricating live data must fail validation closed."""
    snapshot_dict = {
        "provider_id": "test_provider",
        "observed_at": "2026-08-20T08:30:00Z",
        "symbols": {
            "6758": {
                "symbol": "6758",
                "last_price": 1000.0,
                "metadata": {"synthesized": True},
                "status": "FULL",
            }
        },
    }

    res = validate_observation_snapshot(snapshot_dict)
    assert not res.is_valid
    assert res.status == ObservationStatus.UNAVAILABLE
    assert any("forbidden synthesized or inferred market data" in err for err in res.errors)


def test_independent_timestamps():
    """Verify observed_at and source_timestamp independence."""
    snapshot_dict = {
        "provider_id": "test_provider",
        "observed_at": "2026-08-20T08:30:05Z",  # OS observation timestamp
        "symbols": {
            "6758": {
                "symbol": "6758",
                "source_timestamp": "2026-08-20T08:30:00Z",  # Provider timestamp
                "last_price": 1000.0,
                "status": "FULL",
            }
        },
    }

    res = validate_observation_snapshot(snapshot_dict)
    assert res.is_valid
    assert res.status == ObservationStatus.FULL
    assert len(res.errors) == 0


def test_partial_capability_fail_closed():
    """Missing pre-open capability must reflect PARTIAL/UNKNOWN without errors if not falsely claimed as FULL."""
    snapshot_dict = {
        "provider_id": "partial_provider",
        "observed_at": "2026-08-20T08:10:00Z",
        "status": "PARTIAL",
        "symbols": {
            "6758": {
                "symbol": "6758",
                "last_price": None,
                "previous_close": 5000.0,
                "best_bid": None,
                "best_ask": None,
                "indicative_open": None,
                "status": "PARTIAL",
            }
        },
    }

    res = validate_observation_snapshot(snapshot_dict)
    assert res.is_valid
    assert res.status == ObservationStatus.PARTIAL


def test_deterministic_validation_result():
    """Same canonical input must produce deterministic validation result."""
    snapshot_dict = {
        "provider_id": "kabu_station",
        "observed_at": "2026-08-20T08:50:00+09:00",
        "status": "FULL",
        "symbols": {
            "3110": {
                "symbol": "3110",
                "source_timestamp": "2026-08-20T08:49:59+09:00",
                "previous_close": 3200.0,
                "best_bid": {"price": 3190.0, "size": 1000.0},
                "best_ask": {"price": 3210.0, "size": 800.0},
                "indicative_open": {"price": 3205.0, "special_quote_flag": None},
                "status": "FULL",
            }
        },
    }

    res1 = validate_observation_snapshot(snapshot_dict)
    res2 = validate_observation_snapshot(snapshot_dict)

    assert res1.to_dict() == res2.to_dict()
    assert res1.is_valid is True
    assert res1.status == ObservationStatus.FULL
