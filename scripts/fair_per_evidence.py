"""Fair PER Evidence Framework v1 — Machine-readable research boundary contract.

This framework establishes a common, reusable Fair PER estimation contract for all
stocks in Sado Investment Lab. It promotes the methodology from Sony #403 to a
shared framework that separates "good company" from "good entry price."

Core Principles:
- Fair PER is a RANGE with CONFIDENCE, not a single point estimate
- Evidence is staged: Intent → Operating Evidence → Financial Realization
- Optionality evidence is NEVER mixed into current EPS
- Fail-closed: UNKNOWN/STALE data → UNKNOWN outputs
- Framework provides evidence; it does NOT generate BUY/SELL/HOLD signals

Related: #626 Fair PER Evidence Contract v1, #403 Sony Entry Review
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Literal


class Confidence(str, Enum):
    """Evidence confidence level for Fair PER estimation."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class EvidenceStage(str, Enum):
    """Evidence maturity stage — Intent must NOT be promoted to Financial Realization.

    Intent: Plans, announcements, intentions (e.g., "AI Vision strategy announced")
    Operating Evidence: Design wins, orders, contracts, partnerships
    Financial Realization: Revenue, profit, margin contribution in actual results
    """

    INTENT = "INTENT"
    OPERATING_EVIDENCE = "OPERATING_EVIDENCE"
    FINANCIAL_REALIZATION = "FINANCIAL_REALIZATION"
    UNKNOWN = "UNKNOWN"


class DataQuality(str, Enum):
    """Data quality flag for evidence fields."""

    FRESH = "FRESH"
    STALE = "STALE"
    ABNORMAL = "ABNORMAL"  # Red ink, accounting basis change, extraordinary event
    UNKNOWN = "UNKNOWN"
    FAILED = "FAILED"


@dataclass(frozen=True)
class HistoricalValuationEvidence:
    """Factor 1: Historical self-comparison — own past PER and profit phase.

    Guardrails:
    - Do NOT use simple historical average as Fair PER
    - Exclude abnormal years (red ink, basis changes, one-time events)
    - Account for profit phase context (growth → maturity → decline)
    """

    historical_per_range_min: float | None
    historical_per_range_max: float | None
    historical_per_median: float | None
    profit_phase: str | None  # "GROWTH" / "MATURITY" / "DECLINE" / "TURNAROUND" / "UNKNOWN"
    abnormal_years_excluded: tuple[str, ...]  # Years excluded and why
    period_start: str | None
    period_end: str | None
    data_quality: DataQuality
    notes: str | None = None


@dataclass(frozen=True)
class EPSGrowthEvidence:
    """Factor 2: EPS growth — rate, revision direction, sustainability.

    Growth rate + revision direction + sustainability evidence.
    """

    eps_growth_3y_cagr: float | None
    eps_growth_5y_cagr: float | None
    recent_revision_direction: str | None  # "UPGRADE" / "DOWNGRADE" / "STABLE" / "UNKNOWN"
    sustainability_assessment: str | None  # "HIGH" / "MEDIUM" / "LOW" / "UNKNOWN"
    data_quality: DataQuality
    notes: str | None = None


@dataclass(frozen=True)
class EarningsQualityEvidence:
    """Factor 3: Earnings quality — margin, recurring nature, FCF conversion."""

    operating_margin: float | None
    recurring_revenue_ratio: float | None  # Subscription, maintenance, etc.
    fcf_conversion_ratio: float | None  # FCF / Net Income
    quality_assessment: str | None  # "HIGH" / "MEDIUM" / "LOW" / "UNKNOWN"
    data_quality: DataQuality
    notes: str | None = None


@dataclass(frozen=True)
class BusinessMixEvidence:
    """Factor 4: Business mix — high-profit, recurring segment composition."""

    high_margin_segment_ratio: float | None
    recurring_segment_ratio: float | None
    segment_diversification: str | None  # "HIGH" / "MEDIUM" / "LOW" / "UNKNOWN"
    mix_trend: str | None  # "IMPROVING" / "STABLE" / "DETERIORATING" / "UNKNOWN"
    data_quality: DataQuality
    notes: str | None = None


@dataclass(frozen=True)
class CyclicalityRiskEvidence:
    """Factor 5: Cyclicality / Risk — economic cycle, FX, commodity, disaster, regulation.

    Business exposure to external cycles and structural risks.
    """

    economic_cycle_sensitivity: str | None  # "HIGH" / "MEDIUM" / "LOW" / "UNKNOWN"
    fx_exposure: str | None  # "HIGH" / "MEDIUM" / "LOW" / "UNKNOWN"
    commodity_exposure: str | None
    regulatory_risk: str | None
    disaster_risk: str | None
    overall_risk_assessment: str | None  # "HIGH" / "MEDIUM" / "LOW" / "UNKNOWN"
    data_quality: DataQuality
    notes: str | None = None


@dataclass(frozen=True)
class CapitalAllocationEvidence:
    """Factor 6: Capital allocation — buyback, dilution, ROE, ROIC, balance sheet.

    Shareholder value creation through capital deployment.
    """

    buyback_yield: float | None
    share_dilution_3y: float | None
    roe: float | None
    roic: float | None
    debt_to_equity: float | None
    allocation_quality: str | None  # "HIGH" / "MEDIUM" / "LOW" / "UNKNOWN"
    data_quality: DataQuality
    notes: str | None = None


@dataclass(frozen=True)
class PeerValuationEvidence:
    """Factor 7: Peer / market relative valuation.

    Guardrails:
    - Do NOT do simple peer comparison without adjusting for:
      - Growth rate differences
      - Margin differences
      - Business quality differences
    """

    peer_per_range_min: float | None
    peer_per_range_max: float | None
    peer_per_median: float | None
    growth_adjusted_premium: float | None  # Expected premium/discount vs peers
    quality_adjusted_premium: float | None
    adjustment_rationale: str | None
    data_quality: DataQuality
    notes: str | None = None


@dataclass(frozen=True)
class OptionalityEvidence:
    """Factor 8: Optionality evidence — future themes and new business potential.

    CRITICAL GUARDRAIL:
    - Optionality is option value ONLY
    - NEVER add unrealized optionality to current EPS
    - Track evidence stage: Intent → Operating Evidence → Financial Realization
    - Only Financial Realization enters valuation baseline

    Example: Sony Physical AI / AI Vision
    - Intent: AI Vision strategy announcement
    - Operating Evidence: Design wins, partnerships
    - Financial Realization: Actual revenue and profit in results
    """

    optionality_themes: tuple[str, ...]
    evidence_stage: EvidenceStage
    potential_upside: str | None  # "HIGH" / "MEDIUM" / "LOW" / "UNKNOWN"
    per_premium_if_realized: float | None  # Potential PER premium if realized
    realization_timeline: str | None  # "1Y" / "2-3Y" / "3-5Y" / "UNKNOWN"
    data_quality: DataQuality
    notes: str | None = None


@dataclass(frozen=True)
class MacroDiscountRateEvidence:
    """Factor 9: Macro discount rate — interest rate, ERP (equity risk premium)."""

    risk_free_rate: float | None
    equity_risk_premium: float | None
    discount_rate_assessment: str | None  # "LOW" / "NORMAL" / "HIGH" / "UNKNOWN"
    macro_environment: str | None  # "ACCOMMODATIVE" / "NEUTRAL" / "RESTRICTIVE"
    data_quality: DataQuality
    notes: str | None = None


@dataclass(frozen=True)
class MarketExpectationEvidence:
    """Factor 10: Market expectation — implied PER, implied earnings from current price.

    Reverse-engineer what the market is pricing in.
    """

    current_price: float | None
    price_as_of: str | None
    current_eps: float | None
    implied_per: float | None
    implied_scenario: str | None  # "BEAR" / "BASE" / "BULL" / "BEYOND_BULL" / "UNKNOWN"
    expectation_gap: str | None  # "MARKET_TOO_OPTIMISTIC" / "FAIR" / "MARKET_TOO_PESSIMISTIC"
    data_quality: DataQuality
    notes: str | None = None


@dataclass(frozen=True)
class ScenarioEPS:
    """Bear / Base / Bull EPS scenarios.

    These drive the valuation matrix when combined with Fair PER Range.
    """

    bear_eps: float | None
    base_eps: float | None
    bull_eps: float | None
    scenario_as_of: str | None
    fiscal_year: str | None
    share_basis: str | None  # Diluted weighted average or other
    data_quality: DataQuality
    notes: str | None = None


@dataclass(frozen=True)
class FairPERRange:
    """Fair PER estimation output — always a RANGE, not a point estimate.

    Confidence indicates evidence sufficiency and stability.
    """

    fair_per_min: float | None
    fair_per_max: float | None
    fair_per_base: float | None  # Center of range, not necessarily midpoint
    confidence: Confidence
    as_of: str | None
    rationale: str | None
    data_quality: DataQuality


@dataclass(frozen=True)
class ValuationMatrix:
    """Valuation matrix: Fair PER Range × Scenario EPS → Fair Value Range.

    Example:
    - Bear EPS 180 × Fair PER 18-20 = 3240-3600
    - Base EPS 200 × Fair PER 18-20 = 3600-4000
    - Bull EPS 220 × Fair PER 18-20 = 3960-4400
    """

    bear_fair_value_min: float | None
    bear_fair_value_max: float | None
    base_fair_value_min: float | None
    base_fair_value_max: float | None
    bull_fair_value_min: float | None
    bull_fair_value_max: float | None
    matrix_as_of: str | None
    data_quality: DataQuality


@dataclass(frozen=True)
class EntryZone:
    """Entry Zone — ONLY generated when evidence is sufficient and confidence is HIGH.

    Entry Zone ≠ Fair Value Range
    Entry Zone requires:
    - High confidence in Fair PER
    - High confidence in EPS scenarios
    - Fresh market price
    - Clear margin of safety rationale

    This framework does NOT generate BUY/SELL/HOLD signals.
    """

    entry_zone_min: float | None
    entry_zone_max: float | None
    margin_of_safety: float | None  # e.g., 0.20 for 20% MOS
    entry_zone_as_of: str | None
    sufficient_evidence: bool
    rationale: str | None


@dataclass(frozen=True)
class Checkpoint:
    """Next evidence checkpoint or invalidation condition."""

    checkpoint_type: Literal["STRENGTHENING", "INVALIDATION", "NEXT_CHECKPOINT"]
    description: str
    expected_date: str | None
    trigger_condition: str | None


@dataclass(frozen=True)
class FairPEREvidenceContract:
    """Complete Fair PER Evidence Contract v1.

    This is the canonical output of Fair PER research for any stock.
    It provides evidence and ranges; it does NOT make investment decisions.

    Authority Boundary:
    - Framework provides Fair PER Range + Confidence + Evidence
    - Owner Authority decides BUY/SELL/HOLD
    - Pages / Decision Board display evidence; they do NOT generate independent Fair PER
    """

    security_id: str
    security_name: str
    contract_version: str = "v1"

    # 10 Evidence Factors
    historical_valuation: HistoricalValuationEvidence | None = None
    eps_growth: EPSGrowthEvidence | None = None
    earnings_quality: EarningsQualityEvidence | None = None
    business_mix: BusinessMixEvidence | None = None
    cyclicality_risk: CyclicalityRiskEvidence | None = None
    capital_allocation: CapitalAllocationEvidence | None = None
    peer_valuation: PeerValuationEvidence | None = None
    optionality: OptionalityEvidence | None = None
    macro_discount_rate: MacroDiscountRateEvidence | None = None
    market_expectation: MarketExpectationEvidence | None = None

    # Scenario EPS
    scenario_eps: ScenarioEPS | None = None

    # Fair PER Range
    fair_per_range: FairPERRange | None = None

    # Valuation Matrix
    valuation_matrix: ValuationMatrix | None = None

    # Entry Zone (only if sufficient evidence)
    entry_zone: EntryZone | None = None

    # Checkpoints
    strengthening_conditions: tuple[Checkpoint, ...] = ()
    invalidation_conditions: tuple[Checkpoint, ...] = ()
    next_checkpoints: tuple[Checkpoint, ...] = ()

    # Overall assessment
    overall_confidence: Confidence = Confidence.UNKNOWN
    evidence_freshness: DataQuality = DataQuality.UNKNOWN
    contract_as_of: str | None = None


def validate_evidence_stage_separation(contract: FairPEREvidenceContract) -> tuple[bool, list[str]]:
    """Validate that Intent evidence is not promoted to Financial Realization.

    Returns:
        (is_valid, list of violation messages)
    """
    violations = []

    # Check optionality evidence stage
    if contract.optionality is not None:
        if contract.optionality.evidence_stage == EvidenceStage.INTENT:
            # Intent stage optionality should NOT contribute to current EPS scenarios
            if contract.scenario_eps is not None:
                if contract.scenario_eps.notes and "optionality" in contract.scenario_eps.notes.lower():
                    violations.append(
                        "Optionality at INTENT stage appears to be mixed into current EPS scenarios"
                    )

    return len(violations) == 0, violations


def validate_stale_price_fail_closed(contract: FairPEREvidenceContract) -> tuple[bool, list[str]]:
    """Validate fail-closed behavior: STALE/FAILED/UNKNOWN price → UNKNOWN valuation fields.

    Returns:
        (is_valid, list of violation messages)
    """
    violations = []

    if contract.market_expectation is None:
        return True, []

    me = contract.market_expectation

    # If price data quality is not FRESH, current valuation fields must be UNKNOWN/None
    if me.data_quality in (DataQuality.STALE, DataQuality.FAILED, DataQuality.UNKNOWN):
        if me.current_price is not None:
            violations.append(
                f"Price data quality is {me.data_quality.value} but current_price is set"
            )
        if me.implied_per is not None:
            violations.append(
                f"Price data quality is {me.data_quality.value} but implied_per is set"
            )
        if me.implied_scenario is not None and me.implied_scenario != "UNKNOWN":
            violations.append(
                f"Price data quality is {me.data_quality.value} but implied_scenario is set"
            )

    return len(violations) == 0, violations


def validate_abnormal_years_excluded(contract: FairPEREvidenceContract) -> tuple[bool, list[str]]:
    """Validate that abnormal years are explicitly excluded from historical average.

    Returns:
        (is_valid, list of violation messages)
    """
    violations = []

    if contract.historical_valuation is None:
        return True, []

    hv = contract.historical_valuation

    # If data quality is ABNORMAL or there are abnormal years, they should be documented
    if hv.data_quality == DataQuality.ABNORMAL:
        if not hv.abnormal_years_excluded:
            violations.append(
                "Historical valuation data_quality is ABNORMAL but no abnormal_years_excluded specified"
            )

    return len(violations) == 0, violations


def validate_no_buy_sell_hold_generation(contract: FairPEREvidenceContract) -> tuple[bool, list[str]]:
    """Validate that the framework does NOT generate BUY/SELL/HOLD signals.

    Returns:
        (is_valid, list of violation messages)
    """
    violations = []

    # Check for any BUY/SELL/HOLD language in critical fields
    forbidden_terms = ["BUY", "SELL", "HOLD", "STRONG BUY", "STRONG SELL"]

    fields_to_check = []

    if contract.fair_per_range and contract.fair_per_range.rationale:
        fields_to_check.append(("fair_per_range.rationale", contract.fair_per_range.rationale))

    if contract.entry_zone and contract.entry_zone.rationale:
        fields_to_check.append(("entry_zone.rationale", contract.entry_zone.rationale))

    for checkpoint in contract.strengthening_conditions:
        fields_to_check.append(("strengthening_condition", checkpoint.description))

    for field_name, text in fields_to_check:
        text_upper = text.upper()
        for term in forbidden_terms:
            if term in text_upper:
                violations.append(
                    f"Field '{field_name}' contains forbidden decision term '{term}'"
                )

    return len(violations) == 0, violations


def validate_fair_per_evidence_contract(contract: FairPEREvidenceContract) -> tuple[bool, list[str]]:
    """Run all validation rules on a Fair PER Evidence Contract.

    Returns:
        (is_valid, list of all violation messages)
    """
    all_violations = []

    validators = [
        validate_evidence_stage_separation,
        validate_stale_price_fail_closed,
        validate_abnormal_years_excluded,
        validate_no_buy_sell_hold_generation,
    ]

    for validator in validators:
        is_valid, violations = validator(contract)
        all_violations.extend(violations)

    return len(all_violations) == 0, all_violations
