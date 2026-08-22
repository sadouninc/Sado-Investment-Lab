"""Test Market Compass v0.1 page builder."""
from pathlib import Path

import pytest

from build_market_compass import (
    PortfolioPosition,
    ReentryCandidate,
    compute_compass_state,
    load_portfolio,
    load_reentry_watch,
    render_boj_status,
    render_current_holdings,
    render_reentry_watch,
    build_market_compass_page,
)


def test_compute_compass_state_avoid_on_fail():
    """Test AVOID state for FAIL fundamental integrity."""
    result = compute_compass_state(
        fundamental_integrity="FAIL",
        excess_decline=15.0,
        valuation_reset=10.0,
        fundamental_strength=20.0,
        risk_stabilization=20.0,
        confidence="HIGH",
    )
    assert result == "AVOID"


def test_compute_compass_state_avoid_on_unknown():
    """Test AVOID state for UNKNOWN fundamental integrity."""
    result = compute_compass_state(
        fundamental_integrity="UNKNOWN",
        excess_decline=15.0,
        valuation_reset=10.0,
        fundamental_strength=20.0,
        risk_stabilization=20.0,
        confidence="HIGH",
    )
    assert result == "AVOID"


def test_compute_compass_state_watch_missing_scores():
    """Test WATCH state when scores are missing."""
    result = compute_compass_state(
        fundamental_integrity="PASS",
        excess_decline=None,
        valuation_reset=None,
        fundamental_strength=None,
        risk_stabilization=None,
        confidence="MEDIUM",
    )
    assert result == "WATCH"


def test_compute_compass_state_watch_low_total():
    """Test WATCH state when total < 50."""
    result = compute_compass_state(
        fundamental_integrity="PASS",
        excess_decline=10.0,
        valuation_reset=10.0,
        fundamental_strength=10.0,
        risk_stabilization=5.0,
        confidence="MEDIUM",
    )
    assert result == "WATCH"  # total = 35


def test_compute_compass_state_buy_watch():
    """Test BUY_WATCH state meeting criteria."""
    result = compute_compass_state(
        fundamental_integrity="PASS",
        excess_decline=15.0,
        valuation_reset=10.0,
        fundamental_strength=15.0,
        risk_stabilization=12.0,
        confidence="MEDIUM",
    )
    assert result == "BUY_WATCH"  # total = 52


def test_compute_compass_state_reentry_ready():
    """Test RE_ENTRY_READY state meeting all criteria."""
    result = compute_compass_state(
        fundamental_integrity="PASS",
        excess_decline=20.0,
        valuation_reset=15.0,
        fundamental_strength=20.0,
        risk_stabilization=18.0,
        confidence="HIGH",
    )
    assert result == "RE_ENTRY_READY"  # total = 73


def test_compute_compass_state_not_reentry_ready_low_confidence():
    """Test RE_ENTRY_READY blocked by LOW confidence."""
    result = compute_compass_state(
        fundamental_integrity="PASS",
        excess_decline=20.0,
        valuation_reset=15.0,
        fundamental_strength=20.0,
        risk_stabilization=18.0,
        confidence="LOW",
    )
    assert result == "BUY_WATCH"  # total = 73 but confidence is LOW


def test_render_boj_status_red():
    """Test BOJ RED status rendering."""
    html = render_boj_status("RED")
    assert 'data-state="critical"' in html
    assert "BOJ active observation" in html
    assert "BOJ RED ≠ all stocks AVOID" in html


def test_render_boj_status_green():
    """Test BOJ GREEN status rendering."""
    html = render_boj_status("GREEN")
    assert 'data-state="supportive"' in html
    assert "BOJ re-entry observation inactive" in html


def test_build_market_compass_page_structure():
    """Test that market compass page builds with required sections."""
    page = build_market_compass_page()
    
    assert "Market Compass v0.1" in page
    assert "Macro Risk Status" in page
    assert "Current Holdings" in page
    assert "Re-entry Watch" in page or "Re-entry Watch: No confirmed exits" in page
    assert "Data Quality" in page
