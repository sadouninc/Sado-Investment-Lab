from __future__ import annotations

import pytest

from scripts.fair_per_evidence import (
    CanonicalPriceGate,
    EPSScenario,
    FactorEvidence,
    FairPEREvidenceError,
    FairPERRange,
    HistoricalPERObservation,
    STAGE_FINANCIAL_REALIZATION,
    STAGE_INTENT,
    STAGE_OPERATING_EVIDENCE,
    build_fair_per_evidence_record,
    build_historical_valuation_anchor,
    compute_implied_expectation,
    promote_evidence_stage,
    CURRENT_VALUATION_AVAILABLE,
    CURRENT_VALUATION_UNKNOWN,
    FRESHNESS_FRESH,
    FRESHNESS_STALE,
    FRESHNESS_UNKNOWN,
    IDENTITY_FAILED,
    IDENTITY_UNKNOWN,
    IDENTITY_VERIFIED,
    PROVIDER_OK,
    REQUIRED_FACTORS,
)


def _sony_factor_evidence(factor: str, *, stage: str | None = None, **extra) -> FactorEvidence:
    return FactorEvidence(
        factor=factor,
        summary=f"Sony {factor} evidence from FY2026 Q1 IR materials",
        as_of="2026-07-31",
        confidence="MEDIUM",
        source_ref="sony-fy2026-q1-ir",
        stage=stage,
        **extra,
    )


def _sony_factors(*, optionality_stage: str = STAGE_OPERATING_EVIDENCE, **optionality_extra) -> list[FactorEvidence]:
    factors = [
        _sony_factor_evidence(factor)
        for factor in REQUIRED_FACTORS
        if factor != "optionality"
    ]
    factors.append(
        _sony_factor_evidence("optionality", stage=optionality_stage, **optionality_extra)
    )
    return factors


def _sony_historical_anchor():
    observations = [
        HistoricalPERObservation(period="FY2022", per=12.0, accounting_basis="JGAAP-IFRS"),
        HistoricalPERObservation(period="FY2023", per=14.5, accounting_basis="JGAAP-IFRS"),
        HistoricalPERObservation(
            period="FY2020",
            per=None,
            accounting_basis="JGAAP-IFRS",
            is_loss_year=True,
            exclusion_reason="COVID-19 impairment year, not representative of normal earnings power",
        ),
        HistoricalPERObservation(
            period="FY2024",
            per=45.0,
            accounting_basis="JGAAP-IFRS",
            is_abnormal_year=True,
            exclusion_reason="One-off gain on asset sale distorts reported PER",
        ),
    ]
    return build_historical_valuation_anchor(observations)


def _fresh_canonical_price(price: float = 4200.0) -> CanonicalPriceGate:
    return CanonicalPriceGate(
        identity_status=IDENTITY_VERIFIED,
        freshness_status=FRESHNESS_FRESH,
        provider_status=PROVIDER_OK,
        not_market_truth=False,
        price=price,
        price_as_of="2026-08-14T15:00:00+09:00",
    )


def _stale_canonical_price() -> CanonicalPriceGate:
    return CanonicalPriceGate(
        identity_status=IDENTITY_VERIFIED,
        freshness_status=FRESHNESS_STALE,
        provider_status=PROVIDER_OK,
        not_market_truth=False,
        price=3900.0,
        price_as_of="2026-08-01T15:00:00+09:00",
    )


def _unknown_canonical_price() -> CanonicalPriceGate:
    return CanonicalPriceGate(
        identity_status=IDENTITY_UNKNOWN,
        freshness_status=FRESHNESS_UNKNOWN,
        provider_status=PROVIDER_OK,
        not_market_truth=True,
        price=None,
        price_as_of=None,
    )


def _failed_canonical_price() -> CanonicalPriceGate:
    return CanonicalPriceGate(
        identity_status=IDENTITY_FAILED,
        freshness_status=FRESHNESS_UNKNOWN,
        provider_status=PROVIDER_OK,
        not_market_truth=True,
        price=None,
        price_as_of=None,
    )


def _build_sony_record(*, canonical_price: CanonicalPriceGate, optionality_included: bool = False):
    return build_fair_per_evidence_record(
        security_id="JP:6758",
        symbol="6758",
        exchange="TSE",
        factors=_sony_factors(),
        historical_valuation_anchor=_sony_historical_anchor(),
        eps_scenario=EPSScenario(
            bear_eps=180.0,
            base_eps=220.0,
            bull_eps=270.0,
            scenario_as_of="2026-07-31",
            optionality_included=optionality_included,
        ),
        fair_per_range=FairPERRange(fair_per_low=15.0, fair_per_high=20.0, confidence="MEDIUM"),
        canonical_price=canonical_price,
        strengthening=("I&SS margin improvement", "AI Vision design wins"),
        invalidation=("Smartphone sensor demand deterioration",),
        next_checkpoint=("Next earnings revision",),
    )


# ---------------------------------------------------------------------------
# Sony (#403) pilot fixture: lossless 10-factor representation
# ---------------------------------------------------------------------------


def test_sony_403_fixture_maps_losslessly_to_ten_factor_schema():
    record = _build_sony_record(canonical_price=_fresh_canonical_price())

    assert set(record.factors) == set(REQUIRED_FACTORS)
    assert len(record.factors) == 10
    for factor in REQUIRED_FACTORS:
        assert record.factors[factor].factor == factor

    assert record.security_id == "JP:6758"
    assert record.eps_scenario.bear_eps == 180.0
    assert record.eps_scenario.base_eps == 220.0
    assert record.eps_scenario.bull_eps == 270.0
    assert record.fair_per_range.fair_per_low == 15.0
    assert record.fair_per_range.fair_per_high == 20.0


def test_sony_403_current_valuation_available_when_canonical_price_fresh():
    record = _build_sony_record(canonical_price=_fresh_canonical_price(price=4200.0))

    assert record.current_valuation_status == CURRENT_VALUATION_AVAILABLE
    assert record.current_price == 4200.0
    assert record.price_as_of == "2026-08-14T15:00:00+09:00"

    implied = record.implied_expectation
    assert implied.current_per == pytest.approx(4200.0 / 220.0)
    assert implied.expectation_gap_to_low is not None
    assert implied.expectation_gap_to_high is not None


# ---------------------------------------------------------------------------
# Evidence Stage: Intent / Operating Evidence / Financial Realization
# ---------------------------------------------------------------------------


def test_optionality_intent_stage_cannot_carry_realized_metrics():
    with pytest.raises(FairPEREvidenceError):
        _sony_factor_evidence(
            "optionality", stage=STAGE_INTENT, realized_revenue=1_000_000.0
        )


def test_optionality_financial_realization_requires_realized_metric():
    with pytest.raises(FairPEREvidenceError):
        _sony_factor_evidence("optionality", stage=STAGE_FINANCIAL_REALIZATION)


def test_optionality_financial_realization_accepted_with_realized_metric():
    evidence = _sony_factor_evidence(
        "optionality", stage=STAGE_FINANCIAL_REALIZATION, realized_profit=5_000_000.0
    )
    assert evidence.stage == STAGE_FINANCIAL_REALIZATION


def test_promote_evidence_stage_rejects_intent_to_financial_realization_skip():
    with pytest.raises(FairPEREvidenceError):
        promote_evidence_stage(
            STAGE_INTENT, STAGE_FINANCIAL_REALIZATION, realized_profit=1.0
        )


def test_promote_evidence_stage_allows_one_rung_advance():
    assert promote_evidence_stage(STAGE_INTENT, STAGE_OPERATING_EVIDENCE) == STAGE_OPERATING_EVIDENCE
    assert (
        promote_evidence_stage(
            STAGE_OPERATING_EVIDENCE, STAGE_FINANCIAL_REALIZATION, realized_profit=1.0
        )
        == STAGE_FINANCIAL_REALIZATION
    )


def test_optionality_not_mixed_into_eps_unless_financial_realization():
    with pytest.raises(FairPEREvidenceError):
        _build_sony_record(canonical_price=_fresh_canonical_price(), optionality_included=True)


def test_optionality_allowed_in_eps_scenario_when_financial_realization():
    factors = _sony_factors(
        optionality_stage=STAGE_FINANCIAL_REALIZATION, realized_profit=5_000_000.0
    )
    record = build_fair_per_evidence_record(
        security_id="JP:6758",
        symbol="6758",
        exchange="TSE",
        factors=factors,
        historical_valuation_anchor=_sony_historical_anchor(),
        eps_scenario=EPSScenario(
            bear_eps=180.0,
            base_eps=220.0,
            bull_eps=270.0,
            scenario_as_of="2026-07-31",
            optionality_included=True,
        ),
        fair_per_range=FairPERRange(fair_per_low=15.0, fair_per_high=20.0, confidence="MEDIUM"),
        canonical_price=_fresh_canonical_price(),
    )
    assert record.eps_scenario.optionality_included is True


# ---------------------------------------------------------------------------
# Canonical price fail-closed rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "canonical_price_factory",
    [_stale_canonical_price, _unknown_canonical_price, _failed_canonical_price],
)
def test_current_valuation_fields_unknown_when_price_not_usable(canonical_price_factory):
    record = _build_sony_record(canonical_price=canonical_price_factory())

    assert record.current_valuation_status == CURRENT_VALUATION_UNKNOWN
    assert record.current_price is None
    assert record.price_as_of is None

    implied = record.implied_expectation
    assert implied.current_per is None
    assert implied.implied_scenario is None
    assert implied.expectation_gap_to_low is None
    assert implied.expectation_gap_to_high is None


def test_compute_implied_expectation_is_pure_and_fail_closed():
    fair_range = FairPERRange(fair_per_low=15.0, fair_per_high=20.0, confidence="MEDIUM")
    scenario = EPSScenario(bear_eps=180.0, base_eps=220.0, bull_eps=270.0, scenario_as_of="2026-07-31")

    implied = compute_implied_expectation(_unknown_canonical_price(), scenario, fair_range)
    assert implied.current_per is None

    implied = compute_implied_expectation(_fresh_canonical_price(price=4400.0), scenario, fair_range)
    assert implied.current_per == pytest.approx(20.0)
    assert implied.expectation_gap_to_high == pytest.approx(0.0)


# ---------------------------------------------------------------------------
def test_implied_scenario_none_when_base_eps_invalid():
    fair_range = FairPERRange(fair_per_low=15.0, fair_per_high=20.0, confidence="MEDIUM")
    scenario = EPSScenario(bear_eps=180.0, base_eps=None, bull_eps=270.0, scenario_as_of="2026-07-31")

    implied = compute_implied_expectation(_fresh_canonical_price(price=4400.0), scenario, fair_range)
    assert implied.current_per is None
    assert implied.implied_scenario is None

    scenario_zero = EPSScenario(bear_eps=180.0, base_eps=0.0, bull_eps=270.0, scenario_as_of="2026-07-31")
    implied_zero = compute_implied_expectation(_fresh_canonical_price(price=4400.0), scenario_zero, fair_range)
    assert implied_zero.current_per is None
    assert implied_zero.implied_scenario is None

# Historical valuation anchor guardrails
# ---------------------------------------------------------------------------


def test_historical_anchor_excludes_abnormal_and_loss_years():
    anchor = _sony_historical_anchor()
    assert anchor.included_periods == ("FY2022", "FY2023")
    assert set(anchor.excluded_periods) == {"FY2020", "FY2024"}
    assert anchor.anchor_low == 12.0
    assert anchor.anchor_high == 14.5


def test_historical_anchor_rejects_mixed_accounting_basis():
    observations = [
        HistoricalPERObservation(period="FY2022", per=12.0, accounting_basis="JGAAP-IFRS"),
        HistoricalPERObservation(period="FY2023", per=14.5, accounting_basis="US-GAAP"),
    ]
    with pytest.raises(FairPEREvidenceError):
        build_historical_valuation_anchor(observations)


def test_historical_anchor_requires_exclusion_reason_for_abnormal_year():
    with pytest.raises(FairPEREvidenceError):
        HistoricalPERObservation(
            period="FY2024", per=45.0, accounting_basis="JGAAP-IFRS", is_abnormal_year=True
        )


def test_historical_anchor_requires_at_least_one_usable_period():
    observations = [
        HistoricalPERObservation(
            period="FY2020",
            per=None,
            accounting_basis="JGAAP-IFRS",
            is_loss_year=True,
            exclusion_reason="loss year",
        )
    ]
    with pytest.raises(FairPEREvidenceError):
        build_historical_valuation_anchor(observations)


# ---------------------------------------------------------------------------
# Authority boundary: no Entry Zone / BUY-SELL-HOLD from this contract
# ---------------------------------------------------------------------------


def test_record_never_carries_entry_zone_or_decision_action():
    record = _build_sony_record(canonical_price=_fresh_canonical_price())
    assert record.entry_zone is None
    assert record.decision_action is None

    with pytest.raises(TypeError):
        build_fair_per_evidence_record(
            security_id="JP:6758",
            symbol="6758",
            exchange="TSE",
            factors=_sony_factors(),
            historical_valuation_anchor=_sony_historical_anchor(),
            eps_scenario=EPSScenario(
                bear_eps=180.0, base_eps=220.0, bull_eps=270.0, scenario_as_of="2026-07-31"
            ),
            fair_per_range=FairPERRange(fair_per_low=15.0, fair_per_high=20.0, confidence="MEDIUM"),
            canonical_price=_fresh_canonical_price(),
            entry_zone="ENTRY",  # type: ignore[call-arg]
        )


def test_missing_required_factor_fails_closed():
    factors = [f for f in _sony_factors() if f.factor != "peer_valuation"]
    with pytest.raises(FairPEREvidenceError):
        build_fair_per_evidence_record(
            security_id="JP:6758",
            symbol="6758",
            exchange="TSE",
            factors=factors,
            historical_valuation_anchor=_sony_historical_anchor(),
            eps_scenario=EPSScenario(
                bear_eps=180.0, base_eps=220.0, bull_eps=270.0, scenario_as_of="2026-07-31"
            ),
            fair_per_range=FairPERRange(fair_per_low=15.0, fair_per_high=20.0, confidence="MEDIUM"),
            canonical_price=_fresh_canonical_price(),
        )


# ---------------------------------------------------------------------------
# Reproducibility on a second security (Daihen, 6622) — different industry,
# different cyclicality/capital-allocation profile from Sony
# ---------------------------------------------------------------------------


def _daihen_factor_evidence(factor: str, *, stage: str | None = None, **extra) -> FactorEvidence:
    return FactorEvidence(
        factor=factor,
        summary=f"Daihen {factor} evidence from latest annual securities report",
        as_of="2026-05-15",
        confidence="LOW",
        source_ref="daihen-fy2026-yuho",
        stage=stage,
        **extra,
    )


def _daihen_factors() -> list[FactorEvidence]:
    factors = [
        _daihen_factor_evidence(factor)
        for factor in REQUIRED_FACTORS
        if factor != "optionality"
    ]
    factors.append(_daihen_factor_evidence("optionality", stage=STAGE_INTENT))
    return factors


def _daihen_historical_anchor():
    observations = [
        HistoricalPERObservation(period="FY2023", per=9.0, accounting_basis="JGAAP"),
        HistoricalPERObservation(period="FY2024", per=11.0, accounting_basis="JGAAP"),
        HistoricalPERObservation(period="FY2025", per=10.2, accounting_basis="JGAAP"),
    ]
    return build_historical_valuation_anchor(observations)


def test_daihen_second_company_reproduces_ten_factor_schema():
    record = build_fair_per_evidence_record(
        security_id="JP:6622",
        symbol="6622",
        exchange="TSE",
        factors=_daihen_factors(),
        historical_valuation_anchor=_daihen_historical_anchor(),
        eps_scenario=EPSScenario(
            bear_eps=150.0, base_eps=190.0, bull_eps=230.0, scenario_as_of="2026-05-15"
        ),
        fair_per_range=FairPERRange(fair_per_low=9.0, fair_per_high=11.0, confidence="LOW"),
        canonical_price=_unknown_canonical_price(),
    )

    assert set(record.factors) == set(REQUIRED_FACTORS)
    assert record.factors["optionality"].stage == STAGE_INTENT
    assert record.current_valuation_status == CURRENT_VALUATION_UNKNOWN
    assert record.current_price is None
    assert record.historical_valuation_anchor.included_periods == (
        "FY2023",
        "FY2024",
        "FY2025",
    )
