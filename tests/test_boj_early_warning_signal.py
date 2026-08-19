#!/usr/bin/env python3
"""Tests for BOJ Early Warning Signal Engine"""
import pytest
from scripts.boj_early_warning_signal import (
    BOJEarlyWarningEngine,
    PrimaryEvidence,
    MarketImpliedEvidence,
    MacroIndicators,
    SignalState
)


class TestSignalStateLogic:
    """Test signal state determination logic"""
    
    def setup_method(self):
        self.engine = BOJEarlyWarningEngine()
    
    def test_green_state_no_evidence(self):
        """GREEN: No significant evidence"""
        primary = []
        market = MarketImpliedEvidence(
            next_meeting_hike_probability=0.3,
            as_of_date="2026-08-13"
        )
        
        result = self.engine.determine_signal_state(primary, market)
        assert result.signal_state == "GREEN"
        assert "No significant evidence" in result.state_transition_rationale
    
    def test_orange_market_probability_alone(self):
        """ORANGE: Market probability elevated but no primary evidence"""
        primary = []
        market = MarketImpliedEvidence(
            next_meeting_hike_probability=0.76,
            as_of_date="2026-08-13"
        )
        macro = MacroIndicators(ppi_yoy=7.2, import_price_yoy=29.1)
        
        result = self.engine.determine_signal_state(primary, market, macro)
        assert result.signal_state == "ORANGE"
        assert "Market-implied hike probability" in result.state_transition_rationale
    
    def test_orange_cannot_become_red_from_probability_alone(self):
        """CRITICAL: Market probability alone CANNOT trigger RED"""
        primary = []
        market = MarketImpliedEvidence(
            next_meeting_hike_probability=0.95,  # Very high probability
            as_of_date="2026-08-13"
        )
        macro = MacroIndicators(ppi_yoy=10.0, import_price_yoy=35.0)
        
        result = self.engine.determine_signal_state(primary, market, macro)
        # Should be ORANGE, not RED, despite 95% probability
        assert result.signal_state == "ORANGE"
    
    def test_red_with_explicitly_imminent_evidence(self):
        """RED: Primary evidence explicitly signals imminent hike"""
        primary = [
            PrimaryEvidence(
                type="speech",
                date="2026-08-10",
                summary="Governor signals rate hike at next meeting",
                hawkishness="explicitly_imminent"
            )
        ]
        market = MarketImpliedEvidence(
            next_meeting_hike_probability=0.80,
            as_of_date="2026-08-13"
        )
        
        result = self.engine.determine_signal_state(primary, market)
        assert result.signal_state == "RED"
        assert "PRIMARY EVIDENCE" in result.state_transition_rationale
        assert "explicitly signal imminent" in result.state_transition_rationale
    
    def test_red_with_policy_decision(self):
        """RED: Actual policy decision"""
        primary = [
            PrimaryEvidence(
                type="policy_decision",
                date="2026-09-18",
                summary="BOJ raises policy rate to 0.50%",
                hawkishness="hawkish"
            )
        ]
        market = MarketImpliedEvidence(
            next_meeting_hike_probability=0.85,
            as_of_date="2026-09-18"
        )
        
        result = self.engine.determine_signal_state(primary, market)
        assert result.signal_state == "RED"
        assert "policy decision" in result.state_transition_rationale.lower()
    
    def test_orange_multiple_hawkish_signals(self):
        """ORANGE: Multiple hawkish communications"""
        primary = [
            PrimaryEvidence(
                type="speech",
                date="2026-08-05",
                summary="Board member discusses normalization",
                hawkishness="moderately_hawkish"
            ),
            PrimaryEvidence(
                type="minutes",
                date="2026-07-31",
                summary="Several members supported faster pace",
                hawkishness="hawkish"
            )
        ]
        market = MarketImpliedEvidence(
            next_meeting_hike_probability=0.65,
            as_of_date="2026-08-13"
        )
        
        result = self.engine.determine_signal_state(primary, market)
        assert result.signal_state == "ORANGE"
        assert "hawkish BOJ communications" in result.state_transition_rationale
    
    def test_contract_compliance(self):
        """Test output matches JSON schema contract"""
        primary = [
            PrimaryEvidence(
                type="statement",
                date="2026-07-31",
                summary="BOJ maintains policy",
                hawkishness="neutral"
            )
        ]
        market = MarketImpliedEvidence(
            next_meeting_hike_probability=0.40,
            as_of_date="2026-08-13",
            jgb_2y_yield=0.35,
            usdjpy_spot=148.5
        )
        
        result = self.engine.determine_signal_state(
            primary, market, next_mpm_date="2026-09-17"
        )
        
        # Check required fields from schema
        assert result.version == "1.0.0"
        assert result.signal_state in ["GREEN", "ORANGE", "RED"]
        assert "timestamp" in result.timestamp
        assert result.next_mpm_date == "2026-09-17"
        assert "primary" in result.evidence
        assert "market_implied" in result.evidence
        assert isinstance(result.state_transition_rationale, str)
        assert len(result.state_transition_rationale) > 0

