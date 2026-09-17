from __future__ import annotations

from src.sado_investment_lab.domain.boj_early_warning import (
    BOJEvidenceInput,
    BOJEvidenceRef,
    BOJMarketFactorsInput,
    BOJSignalInput,
    BOJSignalResult,
    BOJSignalState,
    EvidenceStatus,
    EvidenceType,
    _parse_market_factors_input,
    classify_boj_signal,
)
from scripts.boj_portfolio_impact_gate import evaluate_boj_signal


def test_market_implied_probability_alone_never_classifies_red():
    """Market-implied probability alone must NEVER classify RED."""
    input_data = BOJSignalInput(
        primary_evidence=BOJEvidenceInput(
            primary_evidence_present=False,
            evidence_status=EvidenceStatus.MISSING,
        ),
        market_factors=BOJMarketFactorsInput(
            market_implied_probability=0.95,
            market_probability_only=True,
            market_prob_rising=True,
        ),
        raw_requested_state="RED",
    )
    result = classify_boj_signal(input_data)
    assert result.effective_state != BOJSignalState.RED.value
    assert result.effective_state == BOJSignalState.ORANGE.value
    assert "market-implied probability alone must never classify RED" in result.reason or "CAPPED_AT_ORANGE" in result.reason
    assert result.probability_only is True


def test_valid_primary_evidence_near_term_tightening_classifies_red():
    """Current valid primary BOJ evidence explicitly indicating near-term tightening may classify RED."""
    ref = BOJEvidenceRef(
        ref_id="boj-stmt-202608",
        source_title="BOJ Outlook Statement",
        evidence_type=EvidenceType.STATEMENT.value,
        url_or_path="06_Research/boj_evidence/boj_anticipation_window_512.md",
        as_of="2026-08-13",
    )
    input_data = BOJSignalInput(
        primary_evidence=BOJEvidenceInput(
            primary_evidence_present=True,
            evidence_status=EvidenceStatus.VALID,
            evidence_type=EvidenceType.STATEMENT,
            indicates_near_term_tightening=True,
            evidence_refs=[ref],
        ),
        as_of="2026-08-13",
    )
    result = classify_boj_signal(input_data)
    assert result.effective_state == BOJSignalState.RED.value
    assert result.primary_evidence_present is True
    assert result.probability_only is False
    assert len(result.evidence_refs) == 1
    assert result.evidence_refs[0]["ref_id"] == "boj-stmt-202608"


def test_actual_rate_hike_decision_classifies_red():
    """Actual BOJ rate-hike decision may classify RED."""
    input_data = BOJSignalInput(
        primary_evidence=BOJEvidenceInput(
            primary_evidence_present=True,
            evidence_status=EvidenceStatus.VALID,
            evidence_type=EvidenceType.OFFICIAL_RATE_HIKE,
            actual_rate_hike_decision=True,
        ),
    )
    result = classify_boj_signal(input_data)
    assert result.effective_state == BOJSignalState.RED.value
    assert result.primary_evidence_present is True


def test_stale_primary_evidence_blocked_from_red():
    """Stale primary evidence must not become RED and must preserve UNKNOWN / insufficient-evidence semantics."""
    input_data = BOJSignalInput(
        primary_evidence=BOJEvidenceInput(
            primary_evidence_present=True,
            evidence_status=EvidenceStatus.STALE,
            indicates_near_term_tightening=True,
            is_stale=True,
        ),
        market_factors=BOJMarketFactorsInput(
            inflation_upside=False,
            hawkish_breadth_expanding=False,
        ),
    )
    result = classify_boj_signal(input_data)
    assert result.effective_state != BOJSignalState.RED.value
    assert result.effective_state == BOJSignalState.UNKNOWN.value
    assert "stale" in result.reason.lower() or "FAIL_CLOSED" in result.reason


def test_ambiguous_primary_evidence_fails_closed():
    """Ambiguous primary evidence must not become RED."""
    input_data = BOJSignalInput(
        primary_evidence=BOJEvidenceInput(
            primary_evidence_present=True,
            evidence_status=EvidenceStatus.AMBIGUOUS,
            indicates_near_term_tightening=True,
        ),
        market_factors=BOJMarketFactorsInput(),
    )
    result = classify_boj_signal(input_data)
    assert result.effective_state != BOJSignalState.RED.value
    assert result.effective_state == BOJSignalState.UNKNOWN.value


def test_missing_primary_evidence_without_multifactor_risk_fails_closed():
    """Missing primary evidence with requested RED and no multi-factor context fails closed."""
    input_data = BOJSignalInput(
        primary_evidence=BOJEvidenceInput(
            primary_evidence_present=False,
            evidence_status=EvidenceStatus.MISSING,
            indicates_near_term_tightening=True,
        ),
        market_factors=BOJMarketFactorsInput(
            inflation_upside=False,
            hawkish_breadth_expanding=False,
        ),
    )
    result = classify_boj_signal(input_data)
    assert result.effective_state != BOJSignalState.RED.value
    assert result.effective_state == BOJSignalState.UNKNOWN.value


def test_orange_represents_multi_factor_risk():
    """ORANGE represents elevated multi-factor risk without asserting a near-term policy decision."""
    input_data = BOJSignalInput(
        primary_evidence=BOJEvidenceInput(
            primary_evidence_present=False,
            evidence_status=EvidenceStatus.MISSING,
        ),
        market_factors=BOJMarketFactorsInput(
            inflation_upside=True,
            hawkish_breadth_expanding=True,
            market_prob_rising=True,
            macro_pressures=True,
        ),
    )
    result = classify_boj_signal(input_data)
    assert result.effective_state == BOJSignalState.ORANGE.value
    assert "Elevated multi-factor risk" in result.reason


def test_green_baseline_signal():
    """GREEN baseline state when primary evidence and multi-factor risk are low."""
    input_data = BOJSignalInput(
        primary_evidence=BOJEvidenceInput(
            primary_evidence_present=False,
            evidence_status=EvidenceStatus.MISSING,
        ),
        market_factors=BOJMarketFactorsInput(
            inflation_upside=False,
            hawkish_breadth_expanding=False,
            market_prob_rising=False,
            macro_pressures=False,
        ),
    )
    result = classify_boj_signal(input_data)
    assert result.effective_state == BOJSignalState.GREEN.value


def test_none_or_unparseable_input_fails_closed_to_unknown():
    """None or invalid input type fails closed to UNKNOWN."""
    result_none = classify_boj_signal(None)
    assert result_none.effective_state == BOJSignalState.UNKNOWN.value

    result_invalid = classify_boj_signal(12345)  # type: ignore
    assert result_invalid.effective_state == BOJSignalState.UNKNOWN.value


def test_dict_input_support_and_determinism():
    """Dict input produces deterministic, identical result to dataclass input."""
    dict_input = {
        "primary_evidence": {
            "primary_evidence_present": True,
            "evidence_status": "VALID",
            "evidence_type": "STATEMENT",
            "indicates_near_term_tightening": True,
            "evidence_refs": [
                {
                    "ref_id": "ref-1",
                    "source_title": "BOJ Minutes",
                    "evidence_type": "SUMMARY_OF_OPINIONS",
                    "url_or_path": "06_Research/boj_evidence/boj_anticipation_baseline_2026-08-13.md",
                    "as_of": "2026-08-13",
                }
            ],
        },
        "market_factors": {
            "inflation_upside": True,
            "market_implied_probability": 0.8,
        },
        "as_of": "2026-08-13",
    }

    res1 = classify_boj_signal(dict_input)
    res2 = classify_boj_signal(dict_input)

    assert res1 == res2
    assert res1.effective_state == BOJSignalState.RED.value
    assert res1.to_dict()["effective_state"] == BOJSignalState.RED.value


def test_output_contains_provenance_and_no_trading_recommendation():
    """Classifier output contains machine-readable provenance and no trading recommendations (BUY/SELL/HOLD)."""
    input_data = BOJSignalInput(
        primary_evidence=BOJEvidenceInput(
            primary_evidence_present=True,
            evidence_status=EvidenceStatus.VALID,
            indicates_near_term_tightening=True,
        ),
    )
    result = classify_boj_signal(input_data)
    data_dict = result.to_dict()

    assert "provenance" in data_dict
    assert "evidence_refs" in data_dict

    # Verify no trading actions or recommendations in keys
    forbidden_keys = {"buy", "sell", "hold", "action", "recommendation", "portfolio_action"}
    assert not (forbidden_keys & set(data_dict.keys()))


def test_market_probability_only_flag_alone_does_not_elevate_to_orange():
    """market_probability_only=True with no/low probability and no other risk factors does not elevate to ORANGE."""
    input_data = BOJSignalInput(
        primary_evidence=BOJEvidenceInput(
            primary_evidence_present=False,
            evidence_status=EvidenceStatus.MISSING,
        ),
        market_factors=BOJMarketFactorsInput(
            market_implied_probability=0.2,
            market_probability_only=True,
            inflation_upside=False,
            hawkish_breadth_expanding=False,
            market_prob_rising=False,
            macro_pressures=False,
        ),
    )
    result = classify_boj_signal(input_data)
    assert result.effective_state == BOJSignalState.GREEN.value


def test_parse_market_factors_robustness():
    """Test robust parsing of market_implied_probability strings (malformed, signed, scientific)."""
    mf1 = _parse_market_factors_input({"market_implied_probability": "+0.8"})
    assert mf1.market_implied_probability == 0.8

    mf2 = _parse_market_factors_input({"market_implied_probability": "1e-2"})
    assert mf2.market_implied_probability == 0.01

    mf3 = _parse_market_factors_input({"market_implied_probability": "invalid_number"})
    assert mf3.market_implied_probability is None

    mf4 = _parse_market_factors_input({"market_implied_probability": ["list"]})
    assert mf4.market_implied_probability is None


def test_portfolio_impact_gate_delegates_to_canonical_domain_classifier():
    """Test that scripts/boj_portfolio_impact_gate.py::evaluate_boj_signal delegates to classify_boj_signal."""
    dict_input = {
        "signal_state": "RED",
        "primary_evidence_present": False,
        "market_probability_only": True,
        "market_factors": {
            "inflation_upside": True,
            "hawkish_breadth_expanding": True,
        },
    }

    gate_eval = evaluate_boj_signal(dict_input)
    domain_eval = classify_boj_signal(dict_input)

    assert gate_eval["effective_state"] == domain_eval.effective_state
    assert gate_eval["effective_state"] == "ORANGE"  # Capped at ORANGE due to missing primary evidence
    assert gate_eval["probability_only"] == domain_eval.probability_only
    assert gate_eval["reason"] == domain_eval.reason
