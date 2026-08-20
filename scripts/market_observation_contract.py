"""Canonical Market Observation Contract v1 (#460).

Provider-independent observation schema and validation invariants for Sado Investment OS.
Enforces strict semantic separation between best_bid, best_ask, and indicative_open,
and explicit separation between OS observed_at and provider source_timestamp.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class ObservationStatus(str, Enum):
    """Observation capability / completeness status."""
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class BestBid:
    """Highest buy order quote."""
    price: Optional[float] = None
    size: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"price": self.price, "size": self.size}


@dataclass
class BestAsk:
    """Lowest sell order quote."""
    price: Optional[float] = None
    size: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"price": self.price, "size": self.size}


@dataclass
class IndicativeOpen:
    """Expected opening price quote (provider-calculated or order-matching indicator)."""
    price: Optional[float] = None
    special_quote_flag: Optional[str] = None  # e.g., "SPECIAL_BUY", "SPECIAL_SELL"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "price": self.price,
            "special_quote_flag": self.special_quote_flag,
        }


@dataclass
class SymbolObservation:
    """Per-symbol canonical observation quote."""
    symbol: str
    source_timestamp: Optional[str] = None  # Provider emission timestamp
    last_price: Optional[float] = None
    previous_close: Optional[float] = None
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    volume: Optional[float] = None
    best_bid: Optional[BestBid] = None
    best_ask: Optional[BestAsk] = None
    indicative_open: Optional[IndicativeOpen] = None
    status: ObservationStatus = ObservationStatus.UNKNOWN
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "source_timestamp": self.source_timestamp,
            "last_price": self.last_price,
            "previous_close": self.previous_close,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "volume": self.volume,
            "best_bid": self.best_bid.to_dict() if self.best_bid else None,
            "best_ask": self.best_ask.to_dict() if self.best_ask else None,
            "indicative_open": self.indicative_open.to_dict() if self.indicative_open else None,
            "status": self.status.value,
            "metadata": self.metadata,
        }


@dataclass
class MarketObservationSnapshot:
    """Canonical Market Observation Snapshot."""
    provider_id: str
    observed_at: str  # OS recording timestamp
    symbols: Dict[str, SymbolObservation] = field(default_factory=dict)
    status: ObservationStatus = ObservationStatus.UNKNOWN
    market_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "observed_at": self.observed_at,
            "status": self.status.value,
            "market_context": self.market_context,
            "symbols": {sym: obs.to_dict() for sym, obs in self.symbols.items()},
        }


@dataclass
class ValidationResult:
    """Deterministic validation output for a MarketObservationSnapshot."""
    is_valid: bool
    status: ObservationStatus
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "status": self.status.value,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def parse_iso_timestamp(ts_str: str) -> bool:
    """Check if string is valid ISO timestamp."""
    if not ts_str or not isinstance(ts_str, str):
        return False
    try:
        # ISO format parsing
        datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return True
    except (ValueError, TypeError):
        return False


def validate_observation_snapshot(snapshot_dict: Dict[str, Any]) -> ValidationResult:
    """Deterministically validate an observation snapshot against canonical contract invariants.

    Invariants enforced:
    1. Mandatory header fields: provider_id, observed_at must be valid non-empty strings.
    2. OS timestamp (observed_at) and provider source_timestamp must be independent and valid ISO strings when provided.
    3. Distinct field semantics: best_bid, best_ask, and indicative_open must be separate objects.
       If values are copied or inferred across fields (e.g., indicative_open price identical to best_bid price
       while missing best_bid size or flagged as synthesized), or if synthesis is attempted, fail validation.
    4. Unavailable pre-open capability must fail closed as PARTIAL or UNKNOWN rather than synthesizing LIVE data.
    5. Same input dictionary produces identical, deterministic ValidationResult.
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(snapshot_dict, dict):
        return ValidationResult(
            is_valid=False,
            status=ObservationStatus.UNAVAILABLE,
            errors=["Snapshot must be a dictionary"],
        )

    provider_id = snapshot_dict.get("provider_id")
    if not provider_id or not isinstance(provider_id, str):
        errors.append("Header 'provider_id' must be a non-empty string.")

    observed_at = snapshot_dict.get("observed_at")
    if not observed_at or not parse_iso_timestamp(str(observed_at)):
        errors.append("Header 'observed_at' must be a valid ISO timestamp string.")

    symbols = snapshot_dict.get("symbols")
    if symbols is None or not isinstance(symbols, dict):
        errors.append("Snapshot must contain a 'symbols' dictionary.")
        symbols = {}

    has_partial_symbol = False
    has_unknown_symbol = False
    has_valid_symbol = False

    for symbol, sym_data in symbols.items():
        if not isinstance(sym_data, dict):
            errors.append(f"Symbol '{symbol}' data must be a dictionary.")
            continue

        # Check source_timestamp vs observed_at separation
        src_ts = sym_data.get("source_timestamp")
        if src_ts is not None:
            if not parse_iso_timestamp(str(src_ts)):
                errors.append(f"Symbol '{symbol}' has invalid source_timestamp '{src_ts}'.")
            if src_ts == observed_at:
                warnings.append(
                    f"Symbol '{symbol}' source_timestamp matches OS observed_at exactly; confirm independent source clock."
                )

        # Invariant: Synthesis detection / cross-field inference forbidden
        best_bid = sym_data.get("best_bid")
        best_ask = sym_data.get("best_ask")
        indicative_open = sym_data.get("indicative_open")
        metadata = sym_data.get("metadata") or {}

        if metadata.get("synthesized") is True or metadata.get("inferred") is True:
            errors.append(f"Symbol '{symbol}' contains forbidden synthesized or inferred market data.")

        # Best Bid validation
        if best_bid is not None:
            if not isinstance(best_bid, dict):
                errors.append(f"Symbol '{symbol}' best_bid must be a dictionary.")
            elif best_bid.get("price") is not None and not isinstance(best_bid.get("price"), (int, float)):
                errors.append(f"Symbol '{symbol}' best_bid.price must be numeric.")

        # Best Ask validation
        if best_ask is not None:
            if not isinstance(best_ask, dict):
                errors.append(f"Symbol '{symbol}' best_ask must be a dictionary.")
            elif best_ask.get("price") is not None and not isinstance(best_ask.get("price"), (int, float)):
                errors.append(f"Symbol '{symbol}' best_ask.price must be numeric.")

        # Indicative Open validation
        if indicative_open is not None:
            if not isinstance(indicative_open, dict):
                errors.append(f"Symbol '{symbol}' indicative_open must be a dictionary.")
            elif indicative_open.get("price") is not None and not isinstance(indicative_open.get("price"), (int, float)):
                errors.append(f"Symbol '{symbol}' indicative_open.price must be numeric.")

        # Cross-field inference sanity check:
        # Check if indicative_open claims to be present but is marked as copied from bid/ask/last
        if indicative_open and isinstance(indicative_open, dict):
            if indicative_open.get("derived_from") in ("best_bid", "best_ask", "last_price", "previous_close"):
                errors.append(
                    f"Symbol '{symbol}' indicative_open cannot be derived/inferred from {indicative_open.get('derived_from')}."
                )

        # Status checks for symbol
        sym_status_str = sym_data.get("status", ObservationStatus.UNKNOWN.value)
        if sym_status_str == ObservationStatus.PARTIAL.value:
            has_partial_symbol = True
        elif sym_status_str == ObservationStatus.UNKNOWN.value:
            has_unknown_symbol = True
        elif sym_status_str == ObservationStatus.FULL.value:
            has_valid_symbol = True

        # Pre-open capability requirement check:
        # If pre-open indicative_open is missing and best_bid/best_ask are partially missing, status must not be FULL
        is_preopen = metadata.get("preopen") is True or metadata.get("session") in ("PREOPEN_EARLY", "PREOPEN_MID", "PREOPEN_LATE")
        if is_preopen:
            if not indicative_open and not (best_bid and best_ask):
                if sym_status_str == ObservationStatus.FULL.value:
                    errors.append(
                        f"Symbol '{symbol}' marked FULL during pre-open session despite missing indicative_open and quotes."
                    )

    if errors:
        final_status = ObservationStatus.UNAVAILABLE
        is_valid = False
    elif has_partial_symbol:
        final_status = ObservationStatus.PARTIAL
        is_valid = True
    elif has_unknown_symbol and not has_valid_symbol:
        final_status = ObservationStatus.UNKNOWN
        is_valid = True
    else:
        declared_status = snapshot_dict.get("status", ObservationStatus.FULL.value)
        try:
            final_status = ObservationStatus(declared_status)
        except ValueError:
            final_status = ObservationStatus.PARTIAL
        is_valid = True

    return ValidationResult(
        is_valid=is_valid,
        status=final_status,
        errors=errors,
        warnings=warnings,
    )
