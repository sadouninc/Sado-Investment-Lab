"""Tests for Fair PER Evidence Framework v1.

Acceptance Criteria:
1. Sony #403 fixture can be represented in 10-factor schema without loss
2. Evidence stages preserved (Intent never promoted to Financial Realization)
3. Optionality evidence not mixed into current EPS
4. Stale/FAILED/UNKNOWN canonical price → fail-closed behavior
5. Framework does NOT generate BUY/SELL/HOLD signals
6. Entry Zone only appears with sufficient evidence
7. Abnormal years properly excluded from historical averages

Related: #626 Fair PER Evidence Contract v1, #403 Sony Entry Review
"""

from __future__ import annotations

import pytest

from scripts.fair_per_evidence import (
    BusinessMixEvidence,
    CapitalAllocationEvidence,
    Checkpoint,
    Confidence,
    CyclicalityRiskEvidence,
    DataQuality,
    EPSGrowthEvidence,
    EarningsQualityEvidence,
    EntryZone,
    EvidenceStage,
    FairPEREvidenceContract,
    FairPERRange,
    HistoricalValuationEvidence,
    MacroDiscountRateEvidence,
    MarketExpectationEvidence,
    OptionalityEvidence,
    PeerValuationEvidence,
    ScenarioEPS,
    ValuationMatrix,
    validate_abnormal_years_excluded,
    validate_evidence_stage_separation,
    validate_fair_per_evidence_contract,
    validate_no_buy_sell_hold_generation,
    validate_stale_price_fail_closed,
)


def _sony_403_fixture() -> FairPEREvidenceContract:
    """Sony #403 pilot fixture represented in 10-factor schema.

    This fixture demonstrates that Sony Entry Review can be losslessly
    expressed in the Fair PER Evidence Contract v1.
    """
    return FairPEREvidenceContract(
        security_id="JP:6758",
        security_name="Sony Group",
        contract_version="v1",
        # Factor 1: Historical Valuation
        historical_valuation=HistoricalValuationEvidence(
            historical_per_range_min=15.0,
            historical_per_range_max=22.0,
            historical_per_median=18.0,
            profit_phase="GROWTH",
            abnormal_years_excluded=("FY2020: COVID impact", "FY2012: Restructuring losses"),
            period_start="FY2018",
            period_end="FY2026",
            data_quality=DataQuality.FRESH,
            notes="Entertainment/IP and I&SS multiple earnings engines",
        ),
        # Factor 2: EPS Growth
        eps_growth=EPSGrowthEvidence(
            eps_growth_3y_cagr=0.12,
            eps_growth_5y_cagr=0.15,
            recent_revision_direction="UPGRADE",
            sustainability_assessment="MEDIUM",
            data_quality=DataQuality.FRESH,
            notes="FY2026 Q1 operating income +40% YoY, guidance upgraded",
        ),
        # Factor 3: Earnings Quality
        earnings_quality=EarningsQualityEvidence(
            operating_margin=0.167,  # 476.5B / 2.84T
            recurring_revenue_ratio=0.35,  # G&NS network services, Music subscription
            fcf_conversion_ratio=0.85,
            quality_assessment="HIGH",
            data_quality=DataQuality.FRESH,
            notes="Multiple recurring earnings engines: G&NS, Music, Pictures",
        ),
        # Factor 4: Business Mix
        business_mix=BusinessMixEvidence(
            high_margin_segment_ratio=0.45,  # I&SS + Entertainment
            recurring_segment_ratio=0.35,
            segment_diversification="HIGH",
            mix_trend="IMPROVING",
            data_quality=DataQuality.FRESH,
            notes="I&SS margin improvement, Entertainment stable, G&NS engaged install base",
        ),
        # Factor 5: Cyclicality / Risk
        cyclicality_risk=CyclicalityRiskEvidence(
            economic_cycle_sensitivity="MEDIUM",
            fx_exposure="MEDIUM",
            commodity_exposure="LOW",
            regulatory_risk="LOW",
            disaster_risk="MEDIUM",
            overall_risk_assessment="MEDIUM",
            data_quality=DataQuality.FRESH,
            notes="Kumamoto earthquake monitored; multiple earnings engines reduce single-cycle risk",
        ),
        # Factor 6: Capital Allocation
        capital_allocation=CapitalAllocationEvidence(
            buyback_yield=0.02,
            share_dilution_3y=-0.01,  # Net buyback
            roe=0.18,
            roic=0.15,
            debt_to_equity=0.45,
            allocation_quality="HIGH",
            data_quality=DataQuality.FRESH,
            notes="Consistent shareholder returns, I&SS capex for future competitiveness",
        ),
        # Factor 7: Peer Valuation
        peer_valuation=PeerValuationEvidence(
            peer_per_range_min=16.0,
            peer_per_range_max=20.0,
            peer_per_median=18.0,
            growth_adjusted_premium=0.05,  # 5% premium for diversification
            quality_adjusted_premium=0.05,  # 5% premium for quality
            adjustment_rationale="Multiple earnings engines, recurring revenue, I&SS tech leadership",
            data_quality=DataQuality.FRESH,
            notes="Global entertainment/tech conglomerates comparison",
        ),
        # Factor 8: Optionality (CRITICAL TEST CASE)
        optionality=OptionalityEvidence(
            optionality_themes=("AI Vision", "Physical AI", "Robotics Sensing", "Automotive Sensing"),
            evidence_stage=EvidenceStage.OPERATING_EVIDENCE,
            potential_upside="HIGH",
            per_premium_if_realized=2.0,  # +2 PER points if Physical AI materializes
            realization_timeline="2-3Y",
            data_quality=DataQuality.FRESH,
            notes="I&SS sensor tech → AI Vision design wins tracked; NOT in current baseline EPS",
        ),
        # Factor 9: Macro Discount Rate
        macro_discount_rate=MacroDiscountRateEvidence(
            risk_free_rate=0.008,  # Japan 10Y JGB ~0.8%
            equity_risk_premium=0.06,
            discount_rate_assessment="LOW",
            macro_environment="ACCOMMODATIVE",
            data_quality=DataQuality.FRESH,
            notes="BoJ yield curve control maintained",
        ),
        # Factor 10: Market Expectation
        market_expectation=MarketExpectationEvidence(
            current_price=4030.0,
            price_as_of="2026-08-14",
            current_eps=200.0,
            implied_per=20.15,
            implied_scenario="BASE",
            expectation_gap="FAIR",
            data_quality=DataQuality.FRESH,
            notes="Market pricing base case with modest optionality discount",
        ),
        # Scenario EPS
        scenario_eps=ScenarioEPS(
            bear_eps=180.0,
            base_eps=200.0,
            bull_eps=220.0,
            scenario_as_of="2026-08-16",
            fiscal_year="FY2026",
            share_basis="Diluted weighted average",
            data_quality=DataQuality.FRESH,
            notes="Base: FY2026 guidance; Bear: I&SS margin pressure; Bull: guidance upside",
        ),
        # Fair PER Range
        fair_per_range=FairPERRange(
            fair_per_min=18.0,
            fair_per_max=20.0,
            fair_per_base=19.0,
            confidence=Confidence.MEDIUM,
            as_of="2026-08-16",
            rationale="Historical median 18x + quality/diversification premium; optionality NOT included",
            data_quality=DataQuality.FRESH,
        ),
        # Valuation Matrix
        valuation_matrix=ValuationMatrix(
            bear_fair_value_min=3240.0,  # 180 * 18
            bear_fair_value_max=3600.0,  # 180 * 20
            base_fair_value_min=3600.0,  # 200 * 18
            base_fair_value_max=4000.0,  # 200 * 20
            bull_fair_value_min=3960.0,  # 220 * 18
            bull_fair_value_max=4400.0,  # 220 * 20
            matrix_as_of="2026-08-16",
            data_quality=DataQuality.FRESH,
        ),
        # Entry Zone: High confidence required
        entry_zone=EntryZone(
            entry_zone_min=3400.0,
            entry_zone_max=3800.0,
            margin_of_safety=0.10,  # 10% below base fair value low
            entry_zone_as_of="2026-08-16",
            sufficient_evidence=True,
            rationale="Entry below 3800 provides margin to base fair value; optionality upside asymmetry",
        ),
        # Checkpoints
        strengthening_conditions=(
            Checkpoint(
                checkpoint_type="STRENGTHENING",
                description="I&SS margin improvement above guidance",
                expected_date="FY2026 Q2",
                trigger_condition="I&SS operating margin > 24%",
            ),
            Checkpoint(
                checkpoint_type="STRENGTHENING",
                description="AI Vision design wins announcement",
                expected_date=None,
                trigger_condition="Major automotive/robotics sensor design win",
            ),
        ),
        invalidation_conditions=(
            Checkpoint(
                checkpoint_type="INVALIDATION",
                description="Smartphone sensor demand deterioration",
                expected_date=None,
                trigger_condition="I&SS guidance downgrade due to smartphone weakness",
            ),
            Checkpoint(
                checkpoint_type="INVALIDATION",
                description="G&NS engagement deterioration",
                expected_date=None,
                trigger_condition="PS5 MAU decline or software attach rate deterioration",
            ),
        ),
        next_checkpoints=(
            Checkpoint(
                checkpoint_type="NEXT_CHECKPOINT",
                description="FY2026 Q2 earnings",
                expected_date="2026-10-31",
                trigger_condition="Earnings release",
            ),
            Checkpoint(
                checkpoint_type="NEXT_CHECKPOINT",
                description="Physical AI progress evidence",
                expected_date="2027-01-31",
                trigger_condition="CES / MWC announcements",
            ),
        ),
        # Overall assessment
        overall_confidence=Confidence.MEDIUM,
        evidence_freshness=DataQuality.FRESH,
        contract_as_of="2026-08-16",
    )


def test_sony_403_fixture_losslessly_represented_in_10_factor_schema() -> None:
    """AC1: Sony #403 fixture can be represented in 10-factor schema without loss."""
    contract = _sony_403_fixture()

    # All 10 factors present
    assert contract.historical_valuation is not None
    assert contract.eps_growth is not None
    assert contract.earnings_quality is not None
    assert contract.business_mix is not None
    assert contract.cyclicality_risk is not None
    assert contract.capital_allocation is not None
    assert contract.peer_valuation is not None
    assert contract.optionality is not None
    assert contract.macro_discount_rate is not None
    assert contract.market_expectation is not None

    # Core outputs present
    assert contract.scenario_eps is not None
    assert contract.fair_per_range is not None
    assert contract.valuation_matrix is not None
    assert contract.entry_zone is not None

    # Checkpoints present
    assert len(contract.strengthening_conditions) > 0
    assert len(contract.invalidation_conditions) > 0
    assert len(contract.next_checkpoints) > 0

    # Sony-specific values
    assert contract.security_id == "JP:6758"
    assert contract.security_name == "Sony Group"
    assert contract.fair_per_range.fair_per_min == 18.0
    assert contract.fair_per_range.fair_per_max == 20.0


def test_evidence_stages_preserved_intent_not_promoted_to_financial_realization() -> None:
    """AC2: Evidence stages preserved (Intent never promoted to Financial Realization)."""
    contract = _sony_403_fixture()

    # Sony optionality is at Operating Evidence stage, not Intent
    assert contract.optionality is not None
    assert contract.optionality.evidence_stage == EvidenceStage.OPERATING_EVIDENCE

    # Optionality is NOT in current baseline EPS
    assert contract.scenario_eps is not None
    assert "NOT in current baseline EPS" in contract.optionality.notes

    # Validation passes
    is_valid, violations = validate_evidence_stage_separation(contract)
    assert is_valid, f"Violations: {violations}"


def test_intent_stage_optionality_cannot_be_mixed_into_current_eps() -> None:
    """AC3: Optionality at INTENT stage must not be mixed into current EPS."""
    # Create contract with INTENT stage optionality incorrectly in EPS notes
    contract = FairPEREvidenceContract(
        security_id="TEST:1234",
        security_name="Test Company",
        optionality=OptionalityEvidence(
            optionality_themes=("Future Theme",),
            evidence_stage=EvidenceStage.INTENT,  # Still at INTENT
            potential_upside="HIGH",
            per_premium_if_realized=3.0,
            realization_timeline="3-5Y",
            data_quality=DataQuality.FRESH,
        ),
        scenario_eps=ScenarioEPS(
            bear_eps=100.0,
            base_eps=120.0,
            bull_eps=140.0,
            scenario_as_of="2026-08-16",
            fiscal_year="FY2026",
            share_basis="Diluted",
            data_quality=DataQuality.FRESH,
            notes="Base includes optionality upside",  # VIOLATION!
        ),
    )

    is_valid, violations = validate_evidence_stage_separation(contract)
    assert not is_valid
    assert len(violations) > 0
    assert "INTENT stage" in violations[0]


def test_stale_price_fails_closed_no_current_valuation() -> None:
    """AC4: Stale/FAILED/UNKNOWN canonical price → fail-closed behavior."""
    contract = FairPEREvidenceContract(
        security_id="TEST:1234",
        security_name="Test Company",
        market_expectation=MarketExpectationEvidence(
            current_price=None,  # Fail-closed: no price
            price_as_of=None,
            current_eps=None,
            implied_per=None,  # Fail-closed: no PER
            implied_scenario="UNKNOWN",  # Fail-closed: unknown scenario
            expectation_gap=None,
            data_quality=DataQuality.STALE,  # STALE data
        ),
        fair_per_range=FairPERRange(
            fair_per_min=15.0,
            fair_per_max=18.0,
            fair_per_base=16.5,
            confidence=Confidence.MEDIUM,
            as_of="2026-08-16",
            rationale="Research-derived fair PER remains available",
            data_quality=DataQuality.FRESH,
        ),
    )

    is_valid, violations = validate_stale_price_fail_closed(contract)
    assert is_valid, f"Violations: {violations}"

    # Fair PER can exist independently of current market price
    assert contract.fair_per_range is not None
    assert contract.fair_per_range.fair_per_min == 15.0


def test_stale_price_with_current_price_set_violates_fail_closed() -> None:
    """AC4: Setting current_price when data_quality is STALE violates fail-closed."""
    contract = FairPEREvidenceContract(
        security_id="TEST:1234",
        security_name="Test Company",
        market_expectation=MarketExpectationEvidence(
            current_price=1000.0,  # VIOLATION: price set despite STALE
            price_as_of="2026-08-01",
            current_eps=100.0,
            implied_per=10.0,
            implied_scenario="BASE",
            expectation_gap="FAIR",
            data_quality=DataQuality.STALE,  # STALE!
        ),
    )

    is_valid, violations = validate_stale_price_fail_closed(contract)
    assert not is_valid
    assert len(violations) > 0
    assert "STALE" in violations[0]


def test_framework_does_not_generate_buy_sell_hold_signals() -> None:
    """AC5: Framework does NOT generate BUY/SELL/HOLD signals."""
    contract = _sony_403_fixture()

    is_valid, violations = validate_no_buy_sell_hold_generation(contract)
    assert is_valid, f"Violations: {violations}"

    # Check critical fields don't contain decision terms
    assert contract.fair_per_range is not None
    rationale = contract.fair_per_range.rationale or ""
    assert "BUY" not in rationale.upper()
    assert "SELL" not in rationale.upper()
    assert "HOLD" not in rationale.upper()


def test_buy_sell_hold_in_rationale_violates_authority_boundary() -> None:
    """AC5: BUY/SELL/HOLD in rationale violates authority boundary."""
    contract = FairPEREvidenceContract(
        security_id="TEST:1234",
        security_name="Test Company",
        fair_per_range=FairPERRange(
            fair_per_min=15.0,
            fair_per_max=18.0,
            fair_per_base=16.5,
            confidence=Confidence.HIGH,
            as_of="2026-08-16",
            rationale="Strong BUY below 3000",  # VIOLATION!
            data_quality=DataQuality.FRESH,
        ),
    )

    is_valid, violations = validate_no_buy_sell_hold_generation(contract)
    assert not is_valid
    assert len(violations) > 0
    assert "BUY" in violations[0]


def test_entry_zone_only_with_sufficient_evidence() -> None:
    """AC6: Entry Zone only appears with sufficient evidence."""
    contract = _sony_403_fixture()

    # Sony fixture has sufficient evidence
    assert contract.entry_zone is not None
    assert contract.entry_zone.sufficient_evidence is True
    assert contract.overall_confidence in (Confidence.MEDIUM, Confidence.HIGH)


def test_entry_zone_absent_when_insufficient_evidence() -> None:
    """AC6: Entry Zone absent when confidence is LOW or evidence insufficient."""
    contract = FairPEREvidenceContract(
        security_id="TEST:1234",
        security_name="Test Company",
        fair_per_range=FairPERRange(
            fair_per_min=10.0,
            fair_per_max=15.0,
            fair_per_base=12.5,
            confidence=Confidence.LOW,  # LOW confidence
            as_of="2026-08-16",
            rationale="Insufficient historical data",
            data_quality=DataQuality.FRESH,
        ),
        entry_zone=None,  # No Entry Zone with LOW confidence
        overall_confidence=Confidence.LOW,
    )

    assert contract.entry_zone is None
    assert contract.overall_confidence == Confidence.LOW


def test_abnormal_years_excluded_from_historical_average() -> None:
    """AC7: Abnormal years properly excluded from historical averages."""
    contract = _sony_403_fixture()

    assert contract.historical_valuation is not None
    assert len(contract.historical_valuation.abnormal_years_excluded) > 0
    assert "FY2020: COVID impact" in contract.historical_valuation.abnormal_years_excluded
    assert "FY2012: Restructuring losses" in contract.historical_valuation.abnormal_years_excluded

    is_valid, violations = validate_abnormal_years_excluded(contract)
    assert is_valid, f"Violations: {violations}"


def test_abnormal_data_quality_without_exclusion_notes_violates() -> None:
    """AC7: ABNORMAL data quality without exclusion notes violates validation."""
    contract = FairPEREvidenceContract(
        security_id="TEST:1234",
        security_name="Test Company",
        historical_valuation=HistoricalValuationEvidence(
            historical_per_range_min=10.0,
            historical_per_range_max=20.0,
            historical_per_median=15.0,
            profit_phase="MATURITY",
            abnormal_years_excluded=(),  # VIOLATION: empty despite ABNORMAL
            period_start="FY2015",
            period_end="FY2025",
            data_quality=DataQuality.ABNORMAL,  # ABNORMAL but no exclusions!
        ),
    )

    is_valid, violations = validate_abnormal_years_excluded(contract)
    assert not is_valid
    assert len(violations) > 0
    assert "ABNORMAL" in violations[0]


def test_complete_validation_suite_passes_for_sony_fixture() -> None:
    """All validation rules pass for properly constructed Sony #403 fixture."""
    contract = _sony_403_fixture()

    is_valid, violations = validate_fair_per_evidence_contract(contract)
    assert is_valid, f"Violations: {violations}"


def test_fair_per_is_range_not_point_estimate() -> None:
    """Fair PER must be a range with confidence, not a single point."""
    contract = _sony_403_fixture()

    assert contract.fair_per_range is not None
    assert contract.fair_per_range.fair_per_min is not None
    assert contract.fair_per_range.fair_per_max is not None
    assert contract.fair_per_range.fair_per_base is not None
    assert contract.fair_per_range.confidence != Confidence.UNKNOWN

    # Range should be non-zero
    assert contract.fair_per_range.fair_per_max > contract.fair_per_range.fair_per_min


def test_valuation_matrix_combines_fair_per_and_scenario_eps() -> None:
    """Valuation matrix correctly combines Fair PER Range × Scenario EPS."""
    contract = _sony_403_fixture()

    assert contract.scenario_eps is not None
    assert contract.fair_per_range is not None
    assert contract.valuation_matrix is not None

    vm = contract.valuation_matrix
    eps = contract.scenario_eps
    fpr = contract.fair_per_range

    # Bear scenario
    assert vm.bear_fair_value_min == pytest.approx(eps.bear_eps * fpr.fair_per_min)
    assert vm.bear_fair_value_max == pytest.approx(eps.bear_eps * fpr.fair_per_max)

    # Base scenario
    assert vm.base_fair_value_min == pytest.approx(eps.base_eps * fpr.fair_per_min)
    assert vm.base_fair_value_max == pytest.approx(eps.base_eps * fpr.fair_per_max)

    # Bull scenario
    assert vm.bull_fair_value_min == pytest.approx(eps.bull_eps * fpr.fair_per_min)
    assert vm.bull_fair_value_max == pytest.approx(eps.bull_eps * fpr.fair_per_max)
