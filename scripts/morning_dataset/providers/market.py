from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from typing import Any, Callable
from urllib.parse import quote
from urllib.request import Request, urlopen

from .base import ProviderResult

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"

# Public market proxies used by the morning pipeline. Growth 250 is represented
# by the listed ETF because a stable public index symbol is not consistently
# available from this endpoint; the proxy is explicit in the output.
MARKET_SYMBOLS: dict[str, dict[str, Any]] = {
    "nikkei_225": {"symbol": "^N225", "kind": "index"},
    "topix": {
        "symbol": "1306.T",
        "kind": "etf_proxy",
        "proxy_for": "TOPIX",
    },
    "growth_250_proxy": {"symbol": "2516.T", "kind": "etf_proxy", "proxy_for": "TSE Growth Market 250"},
    "sp500": {"symbol": "^GSPC", "kind": "index"},
    "nasdaq": {"symbol": "^IXIC", "kind": "index"},
    "dow": {"symbol": "^DJI", "kind": "index"},
    "sox": {"symbol": "^SOX", "kind": "index"},
    "vix": {"symbol": "^VIX", "kind": "index"},
    "usdjpy": {"symbol": "JPY=X", "kind": "fx"},
    "us_10y": {"symbol": "^TNX", "kind": "yield", "scale": 0.1},
    "wti": {"symbol": "CL=F", "kind": "commodity"},
}

Fetcher = Callable[[str], dict[str, Any]]


def _is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _validated_series(chart: dict[str, Any], symbol: str) -> list[tuple[int | float, int | float | None]]:
    """Return (timestamp, close) pairs after validating the chart series.

    The timestamp and close arrays must have equal length, timestamps must be
    finite numbers in strictly increasing order, and every non-null close must
    be a finite number. ``None`` closes are kept as missing (not fabricated).
    Any violation raises ValueError so the symbol is reported as failed rather
    than silently producing a misleading quote.
    """

    timestamps = chart.get("timestamp")
    indicators = chart.get("indicators") or {}
    quotes = indicators.get("quote") if isinstance(indicators, dict) else None
    if timestamps is None:
        timestamps = []
    if not isinstance(timestamps, list):
        raise ValueError(f"timestamp series for {symbol} is not a list")
    if not isinstance(quotes, list) or not quotes or not isinstance(quotes[0], dict):
        closes: Any = []
    else:
        closes = quotes[0].get("close")
        if closes is None:
            closes = []
    if not isinstance(closes, list):
        raise ValueError(f"close series for {symbol} is not a list")
    if len(timestamps) != len(closes):
        raise ValueError(
            f"timestamp/close length mismatch for {symbol}: {len(timestamps)} != {len(closes)}"
        )

    previous_ts: int | float | None = None
    pairs: list[tuple[int | float, int | float | None]] = []
    for ts, close in zip(timestamps, closes):
        if not _is_finite_number(ts):
            raise ValueError(f"invalid timestamp in series for {symbol}")
        if previous_ts is not None and ts <= previous_ts:
            raise ValueError(f"timestamps for {symbol} are not strictly increasing")
        previous_ts = ts
        if close is not None and not _is_finite_number(close):
            raise ValueError(f"invalid close value in series for {symbol}")
        pairs.append((ts, close))
    return pairs


def _latest_quote(payload: dict[str, Any], symbol: str) -> dict[str, Any]:
    result = ((payload.get("chart") or {}).get("result") or [])
    if not result:
        error = (payload.get("chart") or {}).get("error")
        raise ValueError(f"no chart result for {symbol}: {error}")
    chart = result[0]
    if not isinstance(chart, dict):
        raise ValueError(f"chart result for {symbol} is not an object")
    pairs = [(ts, close) for ts, close in _validated_series(chart, symbol) if close is not None]
    if not pairs:
        raise ValueError(f"no close values for {symbol}")
    ts, close = pairs[-1]
    previous = pairs[-2][1] if len(pairs) > 1 else None
    change = close - previous if previous not in (None, 0) else None
    change_pct = (change / previous * 100) if change is not None and previous not in (None, 0) else None
    for label, value in (("change", change), ("change_pct", change_pct)):
        if value is not None and not math.isfinite(value):
            raise ValueError(f"computed {label} for {symbol} is not finite")
    return {
        "value": close,
        "previous_close": previous,
        "change": change,
        "change_pct": change_pct,
        "as_of": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds"),
    }


def fetch_yahoo_chart(symbol: str, *, timeout: int = 15) -> dict[str, Any]:
    url = YAHOO_CHART.format(symbol=quote(symbol, safe=""))
    request = Request(url, headers={"User-Agent": "Sado-Investment-Lab/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class MarketProvider:
    """Collect a compact public-market snapshot without AI inference."""

    name = "market"

    def __init__(self, fetcher: Fetcher | None = None) -> None:
        self.fetcher = fetcher or fetch_yahoo_chart

    def collect(self) -> ProviderResult:
        items: dict[str, Any] = {}
        failures: list[str] = []
        newest_as_of: str | None = None

        for key, spec in MARKET_SYMBOLS.items():
            symbol = str(spec["symbol"])
            try:
                quote_data = _latest_quote(self.fetcher(symbol), symbol)
                scale = float(spec.get("scale", 1.0))
                if scale != 1.0:
                    for field in ("value", "previous_close", "change"):
                        if quote_data.get(field) is not None:
                            quote_data[field] = quote_data[field] * scale
                            if not math.isfinite(quote_data[field]):
                                raise ValueError(f"scaled {field} for {symbol} is not finite")
                quote_data.update({k: v for k, v in spec.items() if k not in {"scale"}})
                quote_data["source"] = "Yahoo Finance chart endpoint"
                items[key] = quote_data
                newest_as_of = max(newest_as_of or quote_data["as_of"], quote_data["as_of"])
            except Exception as exc:  # Individual sources must not break the morning run.
                failures.append(f"{key}({symbol}): {exc.__class__.__name__}")

        if not items:
            return ProviderResult.unavailable(
                self.name,
                reason="all public market quote requests failed",
                source_reference="Yahoo Finance chart endpoint",
            )

        data = {
            "phase": None,
            "indices": {k: v for k, v in items.items() if v.get("kind") in {"index", "etf_proxy"}},
            "macro": {k: v for k, v in items.items() if v.get("kind") in {"fx", "yield", "commodity"}},
            "breadth": None,
            "sentiment": None,
            "risk_state": None,
            "coverage": {
                "available": len(items),
                "requested": len(MARKET_SYMBOLS),
                "missing": failures,
            },
        }
        source_reference = "https://query1.finance.yahoo.com/v8/finance/chart/"
        if failures:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                data=data,
                as_of=newest_as_of,
                source_reference=source_reference,
                reason=f"{len(failures)} of {len(MARKET_SYMBOLS)} market series unavailable",
            )
        return ProviderResult.ok(
            self.name,
            data,
            as_of=newest_as_of,
            source_reference=source_reference,
        )
