from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import os
from typing import Callable, Sequence

from scripts.boj_market_data import (
    PROVIDER_CREDENTIAL_MISSING,
    PROVIDER_OK,
    PROVIDER_UNAVAILABLE,
    MarketDataRecord,
    ProviderResult,
    REQUIRED_BENCHMARK_CODES,
    REQUIRED_SECURITY_CODES,
)


DEFAULT_GROWTH250_INDEX_CODE = "154"


class JQuantsV2MarketDataProvider:
    """Credential-ready adapter for J-Quants API V2.

    The adapter uses the official ``jquantsapi.ClientV2`` boundary when a custom
    client factory is not supplied. It retrieves a short history window so the
    current observation and a common previous trading-day close can be emitted
    together. No fixture/fallback values are fabricated on provider failure.

    ``growth250_index_code`` defaults to JPX's public vendor code 154 and can be
    overridden with ``JQUANTS_GROWTH250_CODE`` if the subscribed J-Quants plan
    exposes a different index identifier.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        growth250_index_code: str | None = None,
        client_factory: Callable[[str], object] | None = None,
        clock: Callable[[], datetime] | None = None,
        history_days: int = 7,
    ) -> None:
        self.api_key = api_key or os.environ.get("JQUANTS_API_KEY")
        self.growth250_index_code = (
            growth250_index_code
            or os.environ.get("JQUANTS_GROWTH250_CODE")
            or DEFAULT_GROWTH250_INDEX_CODE
        )
        self.client_factory = client_factory
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.history_days = history_days

    def _make_client(self) -> object:
        if self.client_factory is not None:
            return self.client_factory(self.api_key or "")
        import jquantsapi  # type: ignore[import-not-found]

        return jquantsapi.ClientV2(api_key=self.api_key)

    @staticmethod
    def _rows(frame: object) -> list[dict[str, object]]:
        if frame is None:
            return []
        to_dict = getattr(frame, "to_dict", None)
        if callable(to_dict):
            rows = to_dict("records")
            return [dict(row) for row in rows]
        if isinstance(frame, list):
            return [dict(row) for row in frame]
        raise TypeError("unsupported J-Quants response type")

    @staticmethod
    def _row_date(row: dict[str, object]) -> date:
        value = row.get("Date")
        if hasattr(value, "date") and not isinstance(value, date):
            return value.date()  # type: ignore[no-any-return]
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])

    @staticmethod
    def _float(row: dict[str, object], *keys: str) -> float:
        for key in keys:
            value = row.get(key)
            if value is not None:
                return float(value)
        raise KeyError(keys[0])

    @staticmethod
    def _security_matches(requested: str, returned: object) -> bool:
        code = str(returned)
        return code == requested or code.rstrip("0") == requested or code.startswith(requested)

    def _history_by_code(
        self,
        rows: list[dict[str, object]],
        requested_codes: Sequence[str],
    ) -> dict[str, dict[date, dict[str, object]]]:
        history: dict[str, dict[date, dict[str, object]]] = {code: {} for code in requested_codes}
        for row in rows:
            returned = row.get("Code")
            for requested in requested_codes:
                if self._security_matches(requested, returned):
                    history[requested][self._row_date(row)] = row
                    break
        return history

    @staticmethod
    def _single_history(rows: list[dict[str, object]]) -> dict[date, dict[str, object]]:
        return {JQuantsV2MarketDataProvider._row_date(row): row for row in rows}

    @staticmethod
    def _common_previous_date(
        market_date: date,
        histories: Sequence[dict[date, dict[str, object]]],
    ) -> date | None:
        common: set[date] | None = None
        for history in histories:
            dates = {value for value in history if value < market_date}
            common = dates if common is None else common & dates
        return max(common) if common else None

    def fetch(self, market_date: date, instrument_codes: Sequence[str]) -> ProviderResult:
        required = set(REQUIRED_SECURITY_CODES) | set(REQUIRED_BENCHMARK_CODES)
        requested = set(instrument_codes)
        unknown = sorted(requested - required)
        if unknown:
            return ProviderResult(PROVIDER_UNAVAILABLE, reasons=("unsupported:" + ",".join(unknown),))
        if not self.api_key:
            return ProviderResult(PROVIDER_CREDENTIAL_MISSING, reasons=("JQUANTS_API_KEY",))

        start = market_date - timedelta(days=self.history_days)
        start_text = start.isoformat()
        end_text = market_date.isoformat()
        try:
            client = self._make_client()
            security_rows = self._rows(
                client.get_eq_bars_daily(  # type: ignore[attr-defined]
                    from_yyyymmdd=start_text,
                    to_yyyymmdd=end_text,
                )
            )
            topix_rows = self._rows(
                client.get_idx_bars_daily_topix(  # type: ignore[attr-defined]
                    from_yyyymmdd=start_text,
                    to_yyyymmdd=end_text,
                )
            )
            growth_rows = self._rows(
                client.get_idx_bars_daily(  # type: ignore[attr-defined]
                    code=self.growth250_index_code,
                    from_yyyymmdd=start_text,
                    to_yyyymmdd=end_text,
                )
            )
        except (ImportError, AttributeError, KeyError, TypeError, ValueError) as exc:
            return ProviderResult(PROVIDER_UNAVAILABLE, reasons=(f"adapter_error:{type(exc).__name__}",))
        except Exception as exc:  # provider/network errors fail closed
            return ProviderResult(PROVIDER_UNAVAILABLE, reasons=(f"provider_error:{type(exc).__name__}",))

        security_history = self._history_by_code(security_rows, REQUIRED_SECURITY_CODES)
        topix_history = self._single_history(topix_rows)
        growth_history = self._single_history(growth_rows)
        all_histories = [*security_history.values(), topix_history, growth_history]

        if any(market_date not in history for history in all_histories):
            return ProviderResult(PROVIDER_UNAVAILABLE, reasons=("market_date_incomplete",))

        previous_date = self._common_previous_date(market_date, all_histories)
        if previous_date is None:
            return ProviderResult(PROVIDER_UNAVAILABLE, reasons=("common_previous_market_date_missing",))

        acquired_at = self.clock().astimezone(timezone.utc).isoformat()
        records: list[MarketDataRecord] = []

        for code in REQUIRED_SECURITY_CODES:
            current = security_history[code][market_date]
            previous = security_history[code][previous_date]
            records.append(
                MarketDataRecord(
                    instrument_code=code,
                    instrument_kind="security",
                    market_date=market_date,
                    source="JQUANTS_V2_EQ_BARS_DAILY",
                    source_timestamp=acquired_at,
                    open=self._float(current, "AdjO", "O"),
                    high=self._float(current, "AdjH", "H"),
                    low=self._float(current, "AdjL", "L"),
                    close=self._float(current, "AdjC", "C"),
                    volume=self._float(current, "AdjVo", "Vo"),
                    adjustment_basis="split_adjusted",
                    previous_close=self._float(previous, "AdjC", "C"),
                    previous_market_date=previous_date,
                )
            )

        for code, history, source in (
            ("TOPIX", topix_history, "JQUANTS_V2_IDX_TOPIX"),
            ("TSE_GROWTH_250", growth_history, "JQUANTS_V2_IDX_BARS_DAILY"),
        ):
            current = history[market_date]
            previous = history[previous_date]
            records.append(
                MarketDataRecord(
                    instrument_code=code,
                    instrument_kind="benchmark",
                    market_date=market_date,
                    source=source,
                    source_timestamp=acquired_at,
                    open=self._float(current, "O"),
                    high=self._float(current, "H"),
                    low=self._float(current, "L"),
                    close=self._float(current, "C"),
                    volume=None,
                    adjustment_basis="index_raw",
                    previous_close=self._float(previous, "C"),
                    previous_market_date=previous_date,
                )
            )

        selected = tuple(record for record in records if record.instrument_code in requested)
        return ProviderResult(PROVIDER_OK, selected, ())
