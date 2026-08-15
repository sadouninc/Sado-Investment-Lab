from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Iterable, Protocol, Sequence


FRESHNESS_VERIFIED_SAME_DAY = "VERIFIED_SAME_DAY"
FRESHNESS_VERIFIED_T_PLUS_1 = "VERIFIED_T_PLUS_1"
FRESHNESS_STALE_SOURCE = "STALE_SOURCE"
FRESHNESS_SOURCE_CONFLICT = "SOURCE_CONFLICT"
FRESHNESS_UNKNOWN = "UNKNOWN"

REQUIRED_SECURITY_CODES = ("3778", "247A", "9166", "3110", "4063")
REQUIRED_BENCHMARK_CODES = ("TOPIX", "TSE_GROWTH_250")


@dataclass(frozen=True)
class MarketDataRecord:
    instrument_code: str
    instrument_kind: str
    market_date: date
    source: str
    source_timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None
    adjustment_basis: str


@dataclass(frozen=True)
class ValidationResult:
    freshness_status: str
    records: tuple[MarketDataRecord, ...]
    reasons: tuple[str, ...]

    @property
    def usable(self) -> bool:
        return self.freshness_status == FRESHNESS_VERIFIED_SAME_DAY


class MarketDataProvider(Protocol):
    """Provider boundary for structured primary and explicit fallback sources."""

    def fetch(self, market_date: date, instrument_codes: Sequence[str]) -> Sequence[MarketDataRecord]:
        ...


def _record_identity(record: MarketDataRecord) -> tuple[object, ...]:
    return (
        record.instrument_code,
        record.instrument_kind,
        record.market_date,
        record.open,
        record.high,
        record.low,
        record.close,
        record.volume,
        record.adjustment_basis,
    )


def validate_aligned_market_data(
    records: Iterable[MarketDataRecord],
    *,
    market_date: date,
    required_security_codes: Sequence[str] = REQUIRED_SECURITY_CODES,
    required_benchmark_codes: Sequence[str] = REQUIRED_BENCHMARK_CODES,
) -> ValidationResult:
    """Fail closed unless every required instrument is present on one exact basis.

    Provider freshness and source selection stay outside this function. This validator
    only accepts exact-market-date data, rejects conflicting duplicates, and requires
    one adjustment basis for all security records. It never interpolates or carries
    forward stale observations.
    """

    materialized = tuple(records)
    if not materialized:
        return ValidationResult(FRESHNESS_UNKNOWN, (), ("no_records",))

    required = set(required_security_codes) | set(required_benchmark_codes)
    by_code: dict[str, list[MarketDataRecord]] = {}
    reasons: list[str] = []

    for record in materialized:
        if record.instrument_code not in required:
            continue
        by_code.setdefault(record.instrument_code, []).append(record)

    missing = sorted(required - set(by_code))
    if missing:
        reasons.append("missing:" + ",".join(missing))

    stale_codes = sorted(
        code
        for code, rows in by_code.items()
        if any(row.market_date != market_date for row in rows)
    )
    if stale_codes:
        reasons.append("market_date_mismatch:" + ",".join(stale_codes))

    conflict_codes: list[str] = []
    for code, rows in by_code.items():
        exact_rows = [row for row in rows if row.market_date == market_date]
        if len({_record_identity(row) for row in exact_rows}) > 1:
            conflict_codes.append(code)
    if conflict_codes:
        reasons.append("source_conflict:" + ",".join(sorted(conflict_codes)))

    security_bases = {
        row.adjustment_basis
        for code in required_security_codes
        for row in by_code.get(code, [])
        if row.market_date == market_date
    }
    if len(security_bases) > 1:
        reasons.append("adjustment_basis_mismatch:" + ",".join(sorted(security_bases)))

    if conflict_codes:
        status = FRESHNESS_SOURCE_CONFLICT
    elif stale_codes:
        status = FRESHNESS_STALE_SOURCE
    elif missing or len(security_bases) != 1:
        status = FRESHNESS_UNKNOWN
    else:
        status = FRESHNESS_VERIFIED_SAME_DAY

    accepted: list[MarketDataRecord] = []
    if status == FRESHNESS_VERIFIED_SAME_DAY:
        for code in (*required_security_codes, *required_benchmark_codes):
            rows = [row for row in by_code[code] if row.market_date == market_date]
            # Equivalent duplicate observations are deterministic and harmless.
            accepted.append(rows[0])

    return ValidationResult(status, tuple(accepted), tuple(reasons))


def build_equity_reaction_transaction(
    *,
    policy_transaction_id: str,
    market_date: date,
    validation: ValidationResult,
) -> dict[str, object]:
    """Create an append-only #512-compatible envelope from validated observations.

    This function never mutates or re-emits the policy observation. It records only a
    reference to the immutable policy transaction plus the separately observed market
    data. BUY/SELL output is intentionally outside this contract.
    """

    if not validation.usable:
        raise ValueError(f"market data is not usable: {validation.freshness_status}")

    return {
        "transaction_type": "equity-reaction",
        "policy_transaction_id": policy_transaction_id,
        "market_date": market_date.isoformat(),
        "freshness_status": validation.freshness_status,
        "records": [
            {
                **asdict(record),
                "market_date": record.market_date.isoformat(),
            }
            for record in validation.records
        ],
        "decision": None,
        "guardrails": {
            "policy_record_immutable": True,
            "missing_or_conflict_fail_closed": True,
            "buy_sell_generation": False,
        },
    }
