"""Fair PER Evidence Contract v1 (Issue #626).

Promotes the Sony (#403) Fair PER research pattern into a machine-readable,
security-agnostic evidence contract. This module is a *research boundary*:
it defines how the 10 required valuation factors, the Bear/Base/Bull EPS
scenarios and the current-price valuation gate are represented and
validated. It never computes a canonical Fair PER number, an Entry Zone or
a BUY/SELL/HOLD decision — those remain Owner Authority / Research
Authority elsewhere.

Fail-closed guardrails enforced here:

- Historical PER anchors must not silently average abnormal/loss years or
  mix incompatible accounting bases.
- Optionality evidence (factor 8) cannot be promoted from ``INTENT`` to
  ``FINANCIAL_REALIZATION`` without an explicit realized financial metric,
  and unrealized optionality can never be blended into current EPS.
- Current-price valuation fields (current price / current PER / implied
  expectation gap) stay ``UNKNOWN`` unless the canonical price gate reports
  ``VERIFIED`` / ``FRESH`` / ``OK`` / ``not_market_truth is False``.
- This contract never produces ``entry_zone`` or ``decision_action``; both
  fields are frozen to ``None`` and cannot be overridden by callers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

CONFIDENCE_LOW = "LOW"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_LEVELS = (CONFIDENCE_LOW, CONFIDENCE_MEDIUM, CONFIDENCE_HIGH)

# Evidence Stage ladder for forward-looking / optionality evidence. Evidence
# must climb this ladder with explicit, checkable proof at each step; it can
# never be assumed to have already arrived at the top.
STAGE_INTENT = "INTENT"
STAGE_OPERATING_EVIDENCE = "OPERATING_EVIDENCE"
STAGE_FINANCIAL_REALIZATION = "FINANCIAL_REALIZATION"
EVIDENCE_STAGES = (STAGE_INTENT, STAGE_OPERATING_EVIDENCE, STAGE_FINANCIAL_REALIZATION)
_STAGE_ORDER = {stage: index for index, stage in enumerate(EVIDENCE_STAGES)}

# The 10 Required Factors from Issue #626.
FACTOR_HISTORICAL_VALUATION = "historical_valuation"
FACTOR_EPS_GROWTH = "eps_growth"
FACTOR_EARNINGS_QUALITY = "earnings_quality"
FACTOR_BUSINESS_MIX = "business_mix"
FACTOR_CYCLICALITY_RISK = "cyclicality_risk"
FACTOR_CAPITAL_ALLOCATION = "capital_allocation"
FACTOR_PEER_VALUATION = "peer_valuation"
FACTOR_OPTIONALITY = "optionality"
FACTOR_MACRO_DISCOUNT_RATE = "macro_discount_rate"
FACTOR_MARKET_EXPECTATION = "market_expectation"

REQUIRED_FACTORS = (
    FACTOR_HISTORICAL_VALUATION,
    FACTOR_EPS_GROWTH,
    FACTOR_EARNINGS_QUALITY,
    FACTOR_BUSINESS_MIX,
    FACTOR_CYCLICALITY_RISK,
    FACTOR_CAPITAL_ALLOCATION,
    FACTOR_PEER_VALUATION,
    FACTOR_OPTIONALITY,
    FACTOR_MACRO_DISCOUNT_RATE,
    FACTOR_MARKET_EXPECTATION,
)

IDENTITY_VERIFIED = "VERIFIED"
IDENTITY_FAILED = "FAILED"
IDENTITY_UNKNOWN = "UNKNOWN"
FRESHNESS_FRESH = "FRESH"
FRESHNESS_STALE = "STALE"
FRESHNESS_UNKNOWN = "UNKNOWN"
PROVIDER_OK = "OK"

CURRENT_VALUATION_AVAILABLE = "AVAILABLE"
CURRENT_VALUATION_UNKNOWN = "UNKNOWN"


class FairPEREvidenceError(ValueError):
    """Raised when a Fair PER evidence input violates the v1 contract."""


def _non_empty_text(value: object, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise FairPEREvidenceError(f"{field_name} is required")
    return text


def _confidence(value: object, field_name: str) -> str:
    text = str(value or "").strip().upper()
    if text not in CONFIDENCE_LEVELS:
        raise FairPEREvidenceError(f"{field_name} must be one of {CONFIDENCE_LEVELS}")
    return text


@dataclass(frozen=True)
class FactorEvidence:
    """One Evidence-schema record for a single required factor.

    ``stage`` is mandatory only for the optionality factor (it tracks the
    Intent -> Operating Evidence -> Financial Realization ladder). Realized
    factors (e.g. historical valuation, earnings quality) leave ``stage`` as
    ``None`` because they are, by definition, already financial-realization
    grade evidence.
    """

    factor: str
    summary: str
    as_of: str
    confidence: str
    source_ref: str
    stage: str | None = None
    realized_revenue: float | None = None
    realized_profit: float | None = None
    excluded_periods: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        factor = _non_empty_text(self.factor, "factor")
        if factor not in REQUIRED_FACTORS:
            raise FairPEREvidenceError(f"unknown factor: {factor}")
        _non_empty_text(self.summary, "summary")
        _non_empty_text(self.as_of, "as_of")
        _non_empty_text(self.source_ref, "source_ref")
        _confidence(self.confidence, "confidence")

        if factor == FACTOR_OPTIONALITY:
            if self.stage is None or self.stage not in EVIDENCE_STAGES:
                raise FairPEREvidenceError(
                    "optionality factor evidence must declare a stage in "
                    f"{EVIDENCE_STAGES}"
                )
            _validate_stage_realization_consistency(
                self.stage, self.realized_revenue, self.realized_profit
            )
        elif self.stage is not None:
            raise FairPEREvidenceError(
                "only the optionality factor uses an evidence stage"
            )


def _validate_stage_realization_consistency(
    stage: str,
    realized_revenue: float | None,
    realized_profit: float | None,
) -> None:
    has_realized_metric = realized_revenue is not None or realized_profit is not None
    if stage == STAGE_FINANCIAL_REALIZATION and not has_realized_metric:
        raise FairPEREvidenceError(
            "FINANCIAL_REALIZATION stage requires an explicit realized_revenue "
            "or realized_profit metric; Intent/Operating Evidence cannot be "
            "auto-promoted"
        )
    if stage != STAGE_FINANCIAL_REALIZATION and has_realized_metric:
        raise FairPEREvidenceError(
            "realized_revenue/realized_profit may only be set once stage is "
            "FINANCIAL_REALIZATION"
        )


def promote_evidence_stage(
    current_stage: str,
    target_stage: str,
    *,
    realized_revenue: float | None = None,
    realized_profit: float | None = None,
) -> str:
    """Advance an optionality evidence stage by exactly one rung at a time.

    Skipping straight from ``INTENT`` to ``FINANCIAL_REALIZATION`` is
    rejected even when a realized metric is supplied, because optionality
    evidence must pass through Operating Evidence (design win / order) and
    be explicitly checked at every step; this keeps the promotion path
    auditable rather than inferred.
    """

    if current_stage not in EVIDENCE_STAGES or target_stage not in EVIDENCE_STAGES:
        raise FairPEREvidenceError(f"stage must be one of {EVIDENCE_STAGES}")
    if _STAGE_ORDER[target_stage] < _STAGE_ORDER[current_stage]:
        raise FairPEREvidenceError("evidence stage cannot be demoted implicitly")
    if _STAGE_ORDER[target_stage] - _STAGE_ORDER[current_stage] > 1:
        raise FairPEREvidenceError(
            "evidence stage may only advance one rung at a time "
            "(INTENT -> OPERATING_EVIDENCE -> FINANCIAL_REALIZATION)"
        )
    _validate_stage_realization_consistency(target_stage, realized_revenue, realized_profit)
    return target_stage


@dataclass(frozen=True)
class HistoricalPERObservation:
    """One fiscal-period historical PER data point."""

    period: str
    per: float | None
    accounting_basis: str
    is_abnormal_year: bool = False
    is_loss_year: bool = False
    exclusion_reason: str | None = None

    def __post_init__(self) -> None:
        _non_empty_text(self.period, "period")
        _non_empty_text(self.accounting_basis, "accounting_basis")
        if self.is_loss_year and self.per is not None:
            raise FairPEREvidenceError(
                f"{self.period}: loss-year observations must not carry a PER value"
            )
        if not self.is_loss_year and self.per is None:
            raise FairPEREvidenceError(
                f"{self.period}: non-loss-year observations require a PER value"
            )
        if (self.is_abnormal_year or self.is_loss_year) and not _non_empty_text_or_none(
            self.exclusion_reason
        ):
            raise FairPEREvidenceError(
                f"{self.period}: abnormal/loss year requires an exclusion_reason"
            )


def _non_empty_text_or_none(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


@dataclass(frozen=True)
class HistoricalValuationAnchor:
    """Result of aggregating historical PER observations into an anchor.

    This is deliberately an *anchor*, not a Fair PER: Issue #626 explicitly
    forbids treating a historical average as Fair PER.
    """

    anchor_low: float
    anchor_high: float
    accounting_basis: str
    included_periods: tuple[str, ...]
    excluded_periods: tuple[str, ...]


def build_historical_valuation_anchor(
    observations: Sequence[HistoricalPERObservation],
) -> HistoricalValuationAnchor:
    """Build an anchor while machine-averaging abnormal/loss years is refused.

    Guardrails:
    - Abnormal years, loss years, and observations without a usable PER are
      excluded from the aggregation (never silently averaged in).
    - All periods included in the aggregation must share one accounting
      basis; mixed bases raise instead of being blended.
    """

    if not observations:
        raise FairPEREvidenceError("historical valuation requires at least one observation")

    included = [
        obs for obs in observations if not (obs.is_abnormal_year or obs.is_loss_year)
    ]
    excluded = [obs for obs in observations if obs.is_abnormal_year or obs.is_loss_year]

    if not included:
        raise FairPEREvidenceError(
            "historical valuation anchor requires at least one non-abnormal, "
            "non-loss period"
        )

    bases = {obs.accounting_basis for obs in included}
    if len(bases) > 1:
        raise FairPEREvidenceError(
            f"historical valuation observations mix accounting bases: {sorted(bases)}"
        )

    values = [obs.per for obs in included if obs.per is not None]
    return HistoricalValuationAnchor(
        anchor_low=min(values),
        anchor_high=max(values),
        accounting_basis=bases.pop(),
        included_periods=tuple(obs.period for obs in included),
        excluded_periods=tuple(obs.period for obs in excluded),
    )


@dataclass(frozen=True)
class EPSScenario:
    """Bear / Base / Bull EPS scenario inputs.

    ``UNKNOWN`` scenarios are represented as ``None`` rather than a
    fabricated placeholder value.
    """

    bear_eps: float | None
    base_eps: float | None
    bull_eps: float | None
    scenario_as_of: str | None
    optionality_included: bool = False


@dataclass(frozen=True)
class FairPERRange:
    fair_per_low: float
    fair_per_high: float
    confidence: str

    def __post_init__(self) -> None:
        _confidence(self.confidence, "confidence")
        if self.fair_per_low > self.fair_per_high:
            raise FairPEREvidenceError("fair_per_low must be <= fair_per_high")


@dataclass(frozen=True)
class CanonicalPriceGate:
    """Mirrors the shared Canonical Market Data / Price Identity Gate.

    A record built from this gate is the only legitimate source of current
    price / current PER inputs; this module never fetches or substitutes a
    price independently (see #633).
    """

    identity_status: str
    freshness_status: str
    provider_status: str
    not_market_truth: bool
    price: float | None
    price_as_of: str | None

    @property
    def usable_for_current_valuation(self) -> bool:
        return (
            self.identity_status == IDENTITY_VERIFIED
            and self.freshness_status == FRESHNESS_FRESH
            and self.provider_status == PROVIDER_OK
            and not self.not_market_truth
            and self.price is not None
            and self.price_as_of is not None
        )


@dataclass(frozen=True)
class ImpliedExpectation:
    """Market-implied EPS/PER back-calculation.

    ``implied_scenario`` names which Bear/Base/Bull scenario the current
    price is closest to; ``expectation_gap`` records the difference between
    the current PER and the Fair PER range (positive = priced above the
    range, negative = priced below it).
    """

    current_per: float | None
    implied_scenario: str | None
    expectation_gap_to_low: float | None
    expectation_gap_to_high: float | None


def compute_implied_expectation(
    canonical_price: CanonicalPriceGate,
    eps_scenario: EPSScenario,
    fair_per_range: FairPERRange,
) -> ImpliedExpectation:
    """Fail-closed implied-PER/expectation-gap calculation.

    Returns an all-``UNKNOWN`` result whenever the canonical price gate is
    not usable; stale, previous-period or provider-failure prices never
    fall back into a current-valuation figure.
    """

    if not canonical_price.usable_for_current_valuation:
        return ImpliedExpectation(
            current_per=None,
            implied_scenario=None,
            expectation_gap_to_low=None,
            expectation_gap_to_high=None,
        )

    price = canonical_price.price
    assert price is not None  # narrowed by usable_for_current_valuation

    scenarios = {
        "BEAR": eps_scenario.bear_eps,
        "BASE": eps_scenario.base_eps,
        "BULL": eps_scenario.bull_eps,
    }
    known_scenarios = {name: eps for name, eps in scenarios.items() if eps and eps > 0}

    base_eps = eps_scenario.base_eps
    current_per = price / base_eps if base_eps and base_eps > 0 else None

    implied_scenario = None
    if current_per is not None and known_scenarios:
        best_name = min(
            known_scenarios,
            key=lambda name: abs(price / known_scenarios[name] - current_per),
        )
        implied_scenario = best_name

    gap_to_low = current_per - fair_per_range.fair_per_low if current_per is not None else None
    gap_to_high = current_per - fair_per_range.fair_per_high if current_per is not None else None

    return ImpliedExpectation(
        current_per=current_per,
        implied_scenario=implied_scenario,
        expectation_gap_to_low=gap_to_low,
        expectation_gap_to_high=gap_to_high,
    )


@dataclass(frozen=True)
class FairPEREvidenceRecord:
    """Top-level, security-agnostic Fair PER Evidence Contract v1 record.

    ``entry_zone`` and ``decision_action`` are frozen to ``None``: this
    contract is a research/evidence artifact and never generates Entry Zone
    or BUY/SELL/HOLD. Pages / Decision Board must consume Fair PER Range +
    Confidence from here and must not derive an independent Fair PER.
    """

    security_id: str
    symbol: str
    exchange: str
    factors: Mapping[str, FactorEvidence]
    historical_valuation_anchor: HistoricalValuationAnchor
    eps_scenario: EPSScenario
    fair_per_range: FairPERRange
    canonical_price: CanonicalPriceGate
    strengthening: tuple[str, ...] = ()
    invalidation: tuple[str, ...] = ()
    next_checkpoint: tuple[str, ...] = ()
    entry_zone: None = field(default=None, init=False)
    decision_action: None = field(default=None, init=False)

    def __post_init__(self) -> None:
        _non_empty_text(self.security_id, "security_id")
        _non_empty_text(self.symbol, "symbol")
        _non_empty_text(self.exchange, "exchange")

        missing = [key for key in REQUIRED_FACTORS if key not in self.factors]
        if missing:
            raise FairPEREvidenceError(f"missing required factor evidence: {missing}")
        for key, evidence in self.factors.items():
            if key != evidence.factor:
                raise FairPEREvidenceError(
                    f"factor evidence key/factor mismatch: {key} != {evidence.factor}"
                )

        optionality_evidence = self.factors[FACTOR_OPTIONALITY]
        if self.eps_scenario.optionality_included and optionality_evidence.stage != STAGE_FINANCIAL_REALIZATION:
            raise FairPEREvidenceError(
                "optionality evidence cannot be blended into EPS scenarios unless "
                "its stage is FINANCIAL_REALIZATION"
            )

    @property
    def current_valuation_status(self) -> str:
        return (
            CURRENT_VALUATION_AVAILABLE
            if self.canonical_price.usable_for_current_valuation
            else CURRENT_VALUATION_UNKNOWN
        )

    @property
    def current_price(self) -> float | None:
        return self.canonical_price.price if self.canonical_price.usable_for_current_valuation else None

    @property
    def price_as_of(self) -> str | None:
        return self.canonical_price.price_as_of if self.canonical_price.usable_for_current_valuation else None

    @property
    def scenario_as_of(self) -> str | None:
        return self.eps_scenario.scenario_as_of

    @property
    def implied_expectation(self) -> ImpliedExpectation:
        return compute_implied_expectation(self.canonical_price, self.eps_scenario, self.fair_per_range)


def build_fair_per_evidence_record(
    *,
    security_id: str,
    symbol: str,
    exchange: str,
    factors: Sequence[FactorEvidence],
    historical_valuation_anchor: HistoricalValuationAnchor,
    eps_scenario: EPSScenario,
    fair_per_range: FairPERRange,
    canonical_price: CanonicalPriceGate,
    strengthening: Sequence[str] = (),
    invalidation: Sequence[str] = (),
    next_checkpoint: Sequence[str] = (),
) -> FairPEREvidenceRecord:
    """Convenience constructor keyed by ``FactorEvidence.factor``."""

    factor_map = {evidence.factor: evidence for evidence in factors}
    if len(factor_map) != len(factors):
        raise FairPEREvidenceError("duplicate factor evidence supplied")

    return FairPEREvidenceRecord(
        security_id=security_id,
        symbol=symbol,
        exchange=exchange,
        factors=factor_map,
        historical_valuation_anchor=historical_valuation_anchor,
        eps_scenario=eps_scenario,
        fair_per_range=fair_per_range,
        canonical_price=canonical_price,
        strengthening=tuple(strengthening),
        invalidation=tuple(invalidation),
        next_checkpoint=tuple(next_checkpoint),
    )
