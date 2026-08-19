#!/usr/bin/env python3
"""Tests for BOJ Portfolio Sensitivity Mapper"""
import pytest
import json
from pathlib import Path
import tempfile
import shutil
from scripts.boj_portfolio_sensitivity import PortfolioSensitivityEngine


class TestPortfolioSensitivityMapper:
    """Test portfolio sensitivity mapping"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.setup_test_portfolio()
        self.setup_test_sensitivities()
        self.engine = PortfolioSensitivityEngine(self.test_dir)
    
    def teardown_method(self):
        """Cleanup"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def setup_test_portfolio(self):
        """Create test portfolio file"""
        portfolio_dir = self.test_dir / "data" / "portfolio"
        portfolio_dir.mkdir(parents=True)
        
        portfolio = {
            "holdings": [
                {"ticker": "3778", "name": "さくらインターネット", "position_type": "LONG"},
                {"ticker": "9166", "name": "GENDA", "position_type": "LONG"},
                {"ticker": "4063", "name": "信越化学", "position_type": "LONG"},
                {"ticker": "3291", "name": "飯田GHD", "position_type": "SHORT"},
                {"ticker": "9999", "name": "Unknown Co", "position_type": "LONG"}
            ]
        }
        
        with open(portfolio_dir / "current.json", 'w', encoding='utf-8') as f:
            json.dump(portfolio, f, ensure_ascii=False)
    
    def setup_test_sensitivities(self):
        """Create test sensitivity files"""
        sens_dir = self.test_dir / "data" / "research" / "boj_sensitivity"
        sens_dir.mkdir(parents=True)
        
        # High sensitivity company
        sens_3778 = {
            "ticker": "3778",
            "name": "さくらインターネット",
            "rate_sensitivity": "HIGH",
            "yen_sensitivity": "MIXED",
            "energy_input_sensitivity": "MEDIUM",
            "valuation_duration": "HIGH",
            "balance_sheet_rate_risk": "HIGH",
            "boj_risk_action": "WATCH",
            "evidence_refs": ["test"],
            "confidence": "HIGH",
            "position_type": "LONG"
        }
        
        # Medium sensitivity company
        sens_9166 = {
            "ticker": "9166",
            "name": "GENDA",
            "rate_sensitivity": "HIGH",
            "yen_sensitivity": "MIXED",
            "energy_input_sensitivity": "LOW",
            "valuation_duration": "MEDIUM",
            "balance_sheet_rate_risk": "HIGH",
            "boj_risk_action": "WATCH",
            "evidence_refs": ["test"],
            "confidence": "HIGH",
            "position_type": "LONG"
        }
        
        # Low sensitivity company
        sens_4063 = {
            "ticker": "4063",
            "name": "信越化学",
            "rate_sensitivity": "LOW",
            "yen_sensitivity": "BENEFIT",
            "energy_input_sensitivity": "MEDIUM",
            "valuation_duration": "LOW",
            "balance_sheet_rate_risk": "LOW",
            "boj_risk_action": "HOLD",
            "evidence_refs": ["test"],
            "confidence": "HIGH",
            "position_type": "LONG"
        }
        
        # SHORT position
        sens_3291 = {
            "ticker": "3291",
            "name": "飯田GHD",
            "rate_sensitivity": "HIGH",
            "yen_sensitivity": "HEADWIND",
            "energy_input_sensitivity": "MEDIUM",
            "valuation_duration": "MEDIUM",
            "balance_sheet_rate_risk": "MEDIUM",
            "boj_risk_action": "HOLD",
            "evidence_refs": ["test"],
            "confidence": "MEDIUM",
            "position_type": "SHORT"
        }
        
        for ticker, data in [("3778", sens_3778), ("9166", sens_9166), 
                             ("4063", sens_4063), ("3291", sens_3291)]:
            with open(sens_dir / f"{ticker}.json", 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
    
    def test_load_canonical_holdings(self):
        """Test loading canonical holdings"""
        holdings = self.engine.get_holdings()
        assert len(holdings) == 5
        assert holdings[0]["ticker"] == "3778"
    
    def test_unknown_company_returns_unknown_profile(self):
        """CRITICAL: Unknown company gets UNKNOWN profile (fail-closed)"""
        result = self.engine.process_portfolio("ORANGE")
        
        unknown = [h for h in result["holdings"] if h["ticker"] == "9999"][0]
        assert unknown["rate_sensitivity"] == "UNKNOWN"
        assert unknown["boj_risk_action"] == "HOLD"
        assert unknown["confidence"] == "LOW"
        assert result["summary"]["unknown_count"] == 1
    
    def test_green_state_no_action(self):
        """GREEN: No action from BOJ factor"""
        result = self.engine.process_portfolio("GREEN")
        
        for holding in result["holdings"]:
            assert holding["boj_risk_action"] == "HOLD"
    
    def test_orange_state_high_sensitivity_watch(self):
        """ORANGE: HIGH sensitivity → WATCH"""
        result = self.engine.process_portfolio("ORANGE")
        
        sakura = [h for h in result["holdings"] if h["ticker"] == "3778"][0]
        assert sakura["boj_risk_action"] == "WATCH"
        assert result["summary"]["watch_count"] >= 1
    
    def test_red_state_high_sensitivity_reduce_candidate(self):
        """RED: HIGH sensitivity → REDUCE_CANDIDATE"""
        result = self.engine.process_portfolio("RED")
        
        sakura = [h for h in result["holdings"] if h["ticker"] == "3778"][0]
        assert sakura["boj_risk_action"] == "REDUCE_CANDIDATE"
        assert result["summary"]["reduce_candidate_count"] >= 1
    
    def test_short_position_handled_differently(self):
        """SHORT positions get separate treatment"""
        result = self.engine.process_portfolio("RED")
        
        short = [h for h in result["holdings"] if h["ticker"] == "3291"][0]
        # SHORT with medium sensitivities should not automatically go to REDUCE_CANDIDATE
        assert short["boj_risk_action"] in ["HOLD", "WATCH", "SHORT_THESIS_REVIEW"]
    
    def test_summary_statistics(self):
        """Test summary statistics calculation"""
        result = self.engine.process_portfolio("ORANGE")
        summary = result["summary"]
        
        assert summary["total_holdings"] == 5
        assert summary["high_sensitivity_count"] >= 2
        assert summary["unknown_count"] == 1
        assert isinstance(summary["watch_count"], int)
    
    def test_extract_candidates(self):
        """Test review candidates extraction"""
        candidates = self.engine.extract_candidates("RED")
        
        # Should have at least REDUCE_CANDIDATE items
        assert len(candidates) > 0
        
        # Should be sorted by priority
        actions = [c["boj_risk_action"] for c in candidates]
        
        # REDUCE_CANDIDATE should come before WATCH
        if "REDUCE_CANDIDATE" in actions and "WATCH" in actions:
            reduce_idx = actions.index("REDUCE_CANDIDATE")
            watch_idx = actions.index("WATCH")
            assert reduce_idx < watch_idx
    
    def test_fail_closed_no_exit_review_for_unknown(self):
        """CRITICAL: UNKNOWN companies cannot reach EXIT_REVIEW"""
        result = self.engine.process_portfolio("RED")
        unknown = [h for h in result["holdings"] if h["ticker"] == "9999"][0]
        assert unknown["boj_risk_action"] != "EXIT_REVIEW"

