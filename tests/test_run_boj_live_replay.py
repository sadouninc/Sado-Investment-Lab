from __future__ import annotations

from datetime import date
from pathlib import Path

from scripts.boj_market_data import (
    PROVIDER_CREDENTIAL_MISSING,
    PROVIDER_OK,
    MarketDataRecord,
    ProviderResult,
    REQUIRED_BENCHMARK_CODES,
    REQUIRED_SECURITY_CODES,
)
from scripts.run_boj_live_replay import (
    ACCEPTED,
    EXIT_CREDENTIAL_MISSING,
    EXIT_INPUT_INVALID,
    EXIT_OK,
    NOT_ACCEPTED,
    _input_error_payload,
    _persist_result,
    run_live_replay,
)


class StaticProvider:
    def __init__(self, result: ProviderResult) -> None:
        self.result = result

    def fetch(self, market_date: date, instrument_codes: tuple[str, ...]) -> ProviderResult:
        return self.result


def _record(code: str, kind: str, close: float, previous_close: float, basis: str) -> MarketDataRecord:
    return MarketDataRecord(
        instrument_code=code,
        instrument_kind=kind,
        market_date=date(2026, 8, 14),
        source="LIVE_TEST_PROVIDER",
        source_timestamp="2026-08-15T08:00:00+09:00",
        open=close - 1.0,
        high=close + 1.0,
        low=close - 2.0,
        close=close,
        volume=1000.0 if kind == "security" else None,
        adjustment_basis=basis,
        previous_close=previous_close,
        previous_market_date=date(2026, 8, 13),
    )


def _valid_records() -> tuple[MarketDataRecord, ...]:
    securities = tuple(
        _record(code, "security", 101.0 + index, 100.0 + index, "split_adjusted")
        for index, code in enumerate(REQUIRED_SECURITY_CODES)
    )
    benchmarks = (
        _record("TOPIX", "benchmark", 3030.0, 3000.0, "index_raw"),
        _record("TSE_GROWTH_250", "benchmark", 805.0, 800.0, "index_raw"),
    )
    return (*securities, *benchmarks)


def test_invalid_market_date_payload_is_fail_closed() -> None:
    payload = _input_error_payload("not-a-date", "2026-08-14-policy-step-002")

    assert payload["exit_code"] == EXIT_INPUT_INVALID
    assert payload["acceptance_status"] == NOT_ACCEPTED
    assert payload["provider_status"] == "NOT_RUN"
    assert payload["market_truth_promoted"] is False
    assert payload["provider_reasons"] == ["invalid_market_date"]


def test_output_write_failure_is_caught(monkeypatch) -> None:
    def fail_write(path: Path, payload: dict[str, object]) -> None:
        raise OSError("synthetic write failure")

    monkeypatch.setattr("scripts.run_boj_live_replay._write_json", fail_write)

    assert _persist_result(Path("result.json"), {"market_truth_promoted": False}) is False


def test_credential_missing_is_not_promoted_to_market_truth() -> None:
    code, payload = run_live_replay(
        provider=StaticProvider(
            ProviderResult(PROVIDER_CREDENTIAL_MISSING, reasons=("JQUANTS_API_KEY",))
        ),
        market_date=date(2026, 8, 14),
        policy_transaction_id="2026-08-14-policy-step-002",
    )

    assert code == EXIT_CREDENTIAL_MISSING
    assert payload["acceptance_status"] == NOT_ACCEPTED
    assert payload["provider_status"] == PROVIDER_CREDENTIAL_MISSING
    assert payload["market_truth_promoted"] is False
    assert "equity_reaction_transaction" not in payload


def test_valid_live_records_generate_append_only_equity_reaction() -> None:
    code, payload = run_live_replay(
        provider=StaticProvider(ProviderResult(PROVIDER_OK, _valid_records(), ())),
        market_date=date(2026, 8, 14),
        policy_transaction_id="2026-08-14-policy-step-002",
    )

    assert code == EXIT_OK
    assert payload["acceptance_status"] == ACCEPTED
    assert payload["market_truth_promoted"] is True
    assert payload["freshness_status"] == "VERIFIED_T_PLUS_1"

    transaction = payload["equity_reaction_transaction"]
    assert transaction["transaction_type"] == "equity-reaction"
    assert transaction["policy_transaction_id"] == "2026-08-14-policy-step-002"
    assert transaction["decision"] is None
    assert len(transaction["records"]) == 7
    assert len(transaction["metrics"]) == 5

    ai_robotics = next(
        metric for metric in transaction["metrics"] if metric["security_code"] == "247A"
    )
    assert "EARNINGS_CONFOUND" in ai_robotics["confounds"]
