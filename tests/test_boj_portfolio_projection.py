#!/usr/bin/env python3
"""Tests for BOJ Portfolio Check Projection"""
import pytest
import json
from pathlib import Path
import tempfile
import shutil
from scripts.boj_portfolio_projection import CheckProjector


class TestPortfolioCheckProjection:
    """Test read-only projection to Portfolio Check"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.setup_test_data()
        self.projector = CheckProjector(self.test_dir)
    
    def teardown_method(self):
        """Cleanup"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def setup_test_data(self):
        """Create test data files"""
        data_dir = self.test_dir / "data" / "boj"
        data_dir.mkdir(parents=True)
        
        # Signal state
        signal = {"signal_state": "RED", "timestamp": "2026-08-13T12:00:00Z"}
        with open(data_dir / "signal_state.json", 'w') as f:
            json.dump(signal, f)
        
        # Portfolio sensitivity
        sensitivity = {
            "boj_signal_state": "RED",
            "timestamp": "2026-08-13T12:00:00Z",
            "holdings": [
                {
                    "ticker": "3778",
                    "name": "さくら",
                    "rate_sensitivity": "HIGH",
                    "valuation_duration": "HIGH",
                    "boj_risk_action": "REDUCE_CANDIDATE",
                    "position_type": "LONG"
                },
                {
                    "ticker": "9166",
                    "name": "GENDA",
                    "rate_sensitivity": "HIGH",
                    "valuation_duration": "MEDIUM",
                    "boj_risk_action": "WATCH",
                    "position_type": "LONG"
                },
                {
                    "ticker": "4063",
                    "name": "信越",
                    "rate_sensitivity": "LOW",
                    "valuation_duration": "LOW",
                    "boj_risk_action": "HOLD",
                    "position_type": "LONG"
                },
                {
                    "ticker": "3291",
                    "name": "飯田",
                    "rate_sensitivity": "HIGH",
                    "valuation_duration": "MEDIUM",
                    "boj_risk_action": "SHORT_THESIS_REVIEW",
                    "position_type": "SHORT"
                }
            ]
        }
        with open(data_dir / "portfolio_sensitivity.json", 'w', encoding='utf-8') as f:
            json.dump(sensitivity, f, ensure_ascii=False)
    
    def test_projection_available(self):
        """Test projection is available when data exists"""
        result = self.projector.build_output()
        assert result["available"] is True
        assert result["signal"] == "RED"
    
    def test_tier_a_immediate_review(self):
        """Test Tier A: Immediate review on RED"""
        result = self.projector.build_output()
        tier_a = result["tiers"]["a"]
        
        assert tier_a["count"] == 1
        assert tier_a["items"][0]["ticker"] == "3778"
        assert tier_a["desc"] == "Immediate review"
    
    def test_tier_b_watch(self):
        """Test Tier B: Watch"""
        result = self.projector.build_output()
        tier_b = result["tiers"]["b"]
        
        assert tier_b["count"] == 1
        assert tier_b["items"][0]["ticker"] == "9166"
    
    def test_tier_c_monitor(self):
        """Test Tier C: Monitor"""
        result = self.projector.build_output()
        tier_c = result["tiers"]["c"]
        
        assert tier_c["count"] == 1
        assert tier_c["items"][0]["ticker"] == "4063"
    
    def test_short_lane_separate(self):
        """Test SHORT positions in separate lane"""
        result = self.projector.build_output()
        short_lane = result["tiers"]["short"]
        
        assert short_lane["count"] == 1
        assert short_lane["items"][0]["ticker"] == "3291"
        assert short_lane["items"][0]["position_type"] == "SHORT"
    
    def test_read_only_notice(self):
        """CRITICAL: Output includes READ-ONLY notice"""
        result = self.projector.build_output()
        assert "notice" in result
        assert "READ-ONLY" in result["notice"]
        assert "No auto-trades" in result["notice"]
    
    def test_missing_data_graceful(self):
        """Test graceful handling when no data available"""
        # Remove data files
        (self.test_dir / "data" / "boj" / "portfolio_sensitivity.json").unlink()
        
        result = self.projector.build_output()
        assert result["available"] is False
        assert "reason" in result

