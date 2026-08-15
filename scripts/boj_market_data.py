from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from typing import Iterable, Protocol, Sequence
from zoneinfo import ZoneInfo


FRESHNESS_VERIFIED_SAME_DAY = "VERIFIED_SAME_DAY"
FRESHNESS_VERIFIED_T_PLUS_1 = "VERIFIED_T_PLUS_1"
FRESHNESS_STALE_SOURCE = "STALE_SOURCE"
FRESHNESS_SOURCE_CONFLICT = "SOURCE_CONFLICT"
FRESHNESS_UNKNOWN = "UNKNOWN"

PROVIDER_OK = "OK"
PROVIDER_CREDENTIAL_MISSING = "CREDENTIAL_MISSING"
PROVIDER_UNAVAILABLE = "UNAVAILABLE"

REQUIRED_SECURITY_CODES = ("3778", "247A", "9166", "3110", "4063")
REQUIRED_BENCHMARK_CODES = ("TOPIX", "TSE_GROWTH_250")
PRIMARY_BENCHMARK_BY_SECURITY = {
    "3778": "TOPIX",
    "247A": "TSE_GROWTH_250",
    "9166": "TSE_GROWTH_250",
    "3110": "TOPIX",
    "4063": "TOPIX",
}
REPLAY_REQUIRED_CONFOUNDS = {
    date(2026, 8, 14): {"247A": ("EARNINGS_CONFOUND",)},
}
TOKYO_TZ = ZoneInfo("Asia/Tokyo")


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
    previous_close: float | None = None
    previous_market_date: date | None = None


@dataclass(frozen=True)
class ProviderResult:
    status: str
    records: tuple[MarketDataRecord, ...] = ()
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationResult:
    freshness_status: str
    records: tuple[MarketDataRecord, ...]
    reasons: tuple[str, ...]

    @property
    def usable(self) -> bool:
        return self.freshness_status in {
            FRESHNESS_VERIFIED_SAME_DAY,
            FRESHNESS_VERIFIED_T_PLUS_1,
        }


class MarketDataProvider(Protocol):
    """Boundary for J-Quants/JPX primary data and explicit fallback adapters.

    Adapters must return CREDENTIAL_MISSING rather than fabricate records when a
    credential is absent. Provider responses become usable only after validation.
    """

    def fetch(self, market_date: date, instrument_codes: Sequence[str]) -> ProviderResult:
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
        record.previous_close,
        record.previous_market_date,
    )


def _observation_freshness(record: MarketDataRecord, market_date: date) -> str:
    try:
        observed = datetime.fromisoformat(record.source_timestamp)
    except ValueError:
        return FRESHNESS_UNKNOWN

    if observed.tzinfo is None or observed.utcoffset() is None:
        return FRESHNESS_UNKNOWN

    observed_tokyo = observed.astimezone(TOKYO_TZ)
    if observed_tokyo.date() == market_date:
        return FRESHNESS_VERIFIED_SAME_DAY

    if (
        observed_tokyo.date() == market_date + timedelta(days=1)
        and observed_tokyo.timetz().replace(tzinfo=None) <= time(12, 0)
    ):
        return FRESHNESS_VERIFIED_T_PLUS_1

    return FRESHNESS_STALE_SOURCE


def validate_aligned_market_data(
    records: Iterable[MarketDataRecord],
    *,
    market_date: date,
    required_security_codes: Sequence[str] = REQUIRED_SECURITY_CODES,
    required_benchmark_codes: Sequence[str] = REQUIRED_BENCHMARK_CODES,
) -> ValidationResult:
    """Fail closed unless all required instruments share one exact market basis."""

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

    missing_previous = sorted(
        code
        for code in required
        for row in by_code.get(code, [])[:1]
        if row.previous_close is None or row.previous_market_date is None
    )
    if missing_previous:
        reasons.append("previous_close_missing:" + ",".join(missing_previous))

    previous_dates = {
        row.previous_market_date
        for code in required
        for row in by_code.get(code, [])[:1]
        if row.previous_market_date is not None
    }
    if len(previous_dates) > 1:
        reasons.append("previous_market_date_mismatch")
    elif previous_dates and next(iter(previous_dates)) >= market_date:
        reasons.append("previous_market_date_invalid")

    observation_states = {
        _observation_freshness(row, market_date)
        for code in required
        for row in by_code.get(code, [])[:1]
        if row.market_date == market_date
    }
    if FRESHNESS_UNKNOWN in observation_states:
        reasons.append("source_timestamp_unknown")
    if FRESHNESS_STALE_SOURCE in observation_states:
        reasons.append("source_timestamp_stale")

    if conflict_codes:
        status = FRESHNESS_SOURCE_CONFLICT
    elif stale_codes or FRESHNESS_STALE_SOURCE in observation_states:
        status = FRESHNESS_STALE_SOURCE
    elif (
        missing
        or len(security_bases) != 1
        or missing_previous
        or len(previous_dates) != 1
        or "previous_market_date_invalid" in reasons
        or FRESHNESS_UNKNOWN in observation_states
    ):
        status = FRESHNESS_UNKNOWN
    elif FRESHNESS_VERIFIED_T_PLUS_1 in observation_states:
        status = FRESHNESS_VERIFIED_T_PLUS_1
    else:
        status = FRESHNESS_VERIFIED_SAME_DAY

    accepted: list[MarketDataRecord] = []
    if status in {FRESHNESS_VERIFIED_SAME_DAY, FRESHNESS_VERIFIED_T_PLUS_1}:
        for code in (*required_security_codes, *required_benchmark_codes):
            rows = [row for row in by_code[code] if row.market_date == market_date]
            accepted.append(rows[0])

    return ValidationResult(status, tuple(accepted), tuple(reasons))


def _return_pct(record: MarketDataRecord) -> float:
    if record.previous_close is None or record.previous_close == 0:
        raise ValueError(f"previous_close unavailable for {record.instrument_code}")
    return (record.close / record.previous_close - 1.0) * 100.0


def build_equity_reaction_metrics(validation: ValidationResult) -> list[dict[str, object]]:
    """Generate #512 primary-benchmark close-to-close excess-return metrics."""

    if not validation.usable:
        raise ValueError(f"market data is not usable: {validation.freshness_status}")

    by_code = {record.instrument_code: record for record in validation.records}
    metrics: list[dict[str, object]] = []
    for security_code in REQUIRED_SECURITY_CODES:
        benchmark_code = PRIMARY_BENCHMARK_BY_SECURITY[security_code]
        security = by_code[security_code]
        benchmark = by_code[benchmark_code]
        stock_return = _return_pct(security)
        benchmark_return = _return_pct(benchmark)
        metrics.append(
            {
                "security_code": security_code,
                "benchmark_code": benchmark_code,
                "stock_return_pct": stock_return,
                "benchmark_return_pct": benchmark_return,
                "excess_return_pt": stock_return - benchmark_return,
                "return_basis": "close_to_close",
                "adjustment_basis": security.adjustment_basis,
                "previous_market_date": security.previous_market_date.isoformat()
                if security.previous_market_date
                else None,
            }
        )
    return metrics


def build_equity_reaction_transaction(
    *,
    policy_transaction_id: str,
    market_date: date,
    validation: ValidationResult,
    confounds_by_security: dict[str, Sequence[str]] | None = None,
) -> dict[str, object]:
    """Create an append-only #512-compatible reaction record from validated data."""

    if not validation.usable:
        raise ValueError(f"market data is not usable: {validation.freshness_status}")

    merged_confounds: dict[str, list[str]] = {}
    for security_code, values in REPLAY_REQUIRED_CONFOUNDS.get(market_date, {}).items():
        merged_confounds[security_code] = list(values)
    for security_code, values in (confounds_by_security or {}).items():
        merged_confounds.setdefault(security_code, [])
        for value in values:
            if value not in merged_confounds[security_code]:
                merged_confounds[security_code].append(value)

    metrics = build_equity_reaction_metrics(validation)
    for metric in metrics:
        metric["confounds"] = merged_confounds.get(str(metric["security_code"]), [])

    return {
        "transaction_type": "equity-reaction",
        "policy_transaction_id": policy_transaction_id,
        "market_date": market_date.isoformat(),
        "freshness_status": validation.freshness_status,
        "records": [
            {
                **asdict(record),
                "market_date": record.market_date.isoformat(),
                "previous_market_date": record.previous_market_date.isoformat()
                if record.previous_market_date
                else None,
            }
            for record in validation.records
        ],
        "metrics": metrics,
        "decision": None,
        "guardrails": {
            "policy_record_immutable": True,
            "missing_or_conflict_fail_closed": True,
            "partial_success_rejected": True,
            "buy_sell_generation": False,
        },
    }
