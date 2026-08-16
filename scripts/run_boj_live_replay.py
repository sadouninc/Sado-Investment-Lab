from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any

from scripts.boj_jquants_adapter import JQuantsV2MarketDataProvider
from scripts.boj_market_data import (
    PROVIDER_CREDENTIAL_MISSING,
    PROVIDER_OK,
    REQUIRED_BENCHMARK_CODES,
    REQUIRED_SECURITY_CODES,
    MarketDataProvider,
    build_equity_reaction_transaction,
    validate_aligned_market_data,
)


ACCEPTED = "ACCEPTED"
NOT_ACCEPTED = "NOT_ACCEPTED"
EXIT_OK = 0
EXIT_INPUT_INVALID = 1
EXIT_CREDENTIAL_MISSING = 2
EXIT_PROVIDER_UNAVAILABLE = 3
EXIT_VALIDATION_REJECTED = 4
EXIT_OUTPUT_WRITE_FAILED = 5


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _input_error_payload(raw_market_date: str, policy_transaction_id: str) -> dict[str, Any]:
    return {
        "run_type": "boj-live-market-replay",
        "market_date": raw_market_date,
        "policy_transaction_id": policy_transaction_id,
        "acceptance_status": NOT_ACCEPTED,
        "provider_status": "NOT_RUN",
        "provider_reasons": ["invalid_market_date"],
        "market_truth_promoted": False,
        "exit_code": EXIT_INPUT_INVALID,
    }


def run_live_replay(
    *,
    provider: MarketDataProvider,
    market_date: date,
    policy_transaction_id: str,
) -> tuple[int, dict[str, Any]]:
    required_codes = (*REQUIRED_SECURITY_CODES, *REQUIRED_BENCHMARK_CODES)
    provider_result = provider.fetch(market_date, required_codes)

    envelope: dict[str, Any] = {
        "run_type": "boj-live-market-replay",
        "market_date": market_date.isoformat(),
        "policy_transaction_id": policy_transaction_id,
        "acceptance_status": NOT_ACCEPTED,
        "provider_status": provider_result.status,
        "provider_reasons": list(provider_result.reasons),
        "market_truth_promoted": False,
    }

    if provider_result.status != PROVIDER_OK:
        exit_code = (
            EXIT_CREDENTIAL_MISSING
            if provider_result.status == PROVIDER_CREDENTIAL_MISSING
            else EXIT_PROVIDER_UNAVAILABLE
        )
        envelope["exit_code"] = exit_code
        return exit_code, envelope

    validation = validate_aligned_market_data(provider_result.records, market_date=market_date)
    envelope["freshness_status"] = validation.freshness_status
    envelope["validation_reasons"] = list(validation.reasons)

    if not validation.usable:
        envelope["exit_code"] = EXIT_VALIDATION_REJECTED
        return EXIT_VALIDATION_REJECTED, envelope

    transaction = build_equity_reaction_transaction(
        policy_transaction_id=policy_transaction_id,
        market_date=market_date,
        validation=validation,
    )
    envelope.update(
        {
            "acceptance_status": ACCEPTED,
            "market_truth_promoted": True,
            "equity_reaction_transaction": transaction,
            "exit_code": EXIT_OK,
        }
    )
    return EXIT_OK, envelope


def _persist_result(output: Path, payload: dict[str, Any]) -> bool:
    try:
        _write_json(output, payload)
    except OSError:
        # Keep failure output intentionally generic: exception text can contain
        # environment/path details and is not needed for the acceptance decision.
        print(json.dumps({"error": "output_write_failed"}, ensure_ascii=False))
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Run fail-closed BOJ live J-Quants replay")
    parser.add_argument("--market-date", required=True, help="Market date in YYYY-MM-DD")
    parser.add_argument("--policy-transaction-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        market_date = date.fromisoformat(args.market_date)
    except ValueError:
        payload = _input_error_payload(args.market_date, args.policy_transaction_id)
        if not _persist_result(args.output, payload):
            return EXIT_OUTPUT_WRITE_FAILED
        print(
            json.dumps(
                {
                    "acceptance_status": NOT_ACCEPTED,
                    "provider_status": "NOT_RUN",
                    "error": "invalid_market_date",
                    "expected": "YYYY-MM-DD",
                    "output": str(args.output),
                    "exit_code": EXIT_INPUT_INVALID,
                },
                ensure_ascii=False,
            )
        )
        return EXIT_INPUT_INVALID

    exit_code, payload = run_live_replay(
        provider=JQuantsV2MarketDataProvider(),
        market_date=market_date,
        policy_transaction_id=args.policy_transaction_id,
    )
    if not _persist_result(args.output, payload):
        return EXIT_OUTPUT_WRITE_FAILED

    print(
        json.dumps(
            {
                "acceptance_status": payload["acceptance_status"],
                "provider_status": payload["provider_status"],
                "freshness_status": payload.get("freshness_status"),
                "output": str(args.output),
                "exit_code": exit_code,
            },
            ensure_ascii=False,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
