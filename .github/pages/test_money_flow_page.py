from __future__ import annotations

import sys
from pathlib import Path

import pytest

PAGES = Path(__file__).resolve().parent
ROOT = PAGES.parent.parent

if str(PAGES) not in sys.path:
    sys.path.insert(0, str(PAGES))

import build_money_flow_page as money_flow


def test_render_page_with_no_data():
    """Page must render gracefully when no data is available."""
    page = money_flow.render_page(sector_snapshot=None, intraday_flows=[])
    assert "Money Flow" in page
    assert "Medium-term regime: UNAVAILABLE" in page
    assert "Intraday flow: UNAVAILABLE" in page
    assert "fail-closed" in page


def test_render_page_preserves_medium_term_and_intraday_separation():
    """Page must show medium-term and intraday as separate sections, not overwriting each other."""
    sector_snapshot = {
        "observed_at": "2026-08-14T09:00:00+09:00",
        "sectors": [
            {
                "name": "Pharmaceutical",
                "signal": "COLD",
                "explanation": "5d/20d/60d relative weakness",
            }
        ],
    }
    intraday_flows = [
        {
            "schema_version": 1,
            "observed_at": "2026-08-14T10:30:00+09:00",
            "source": "test",
            "freshness": "FRESH",
            "data_completeness": "COMPLETE",
            "benchmark": "TOPIX",
            "sector": {
                "id": "sector:pharmaceutical",
                "label": "Pharmaceutical",
                "medium_term_regime": "COLD",
            },
            "subsector": {
                "id": "subsector:biotechnology",
                "label": "Biotechnology",
                "taxonomy_version": "test-v1",
                "as_of": "2026-08-14",
                "source_or_authority": "test",
            },
            "observations": {
                "intraday_return": 0.036,
                "benchmark_return": 0.009,
                "relative_return": 0.027,
                "rising_count": 4,
                "constituent_count": 5,
                "breadth": 0.8,
                "median_constituent_return": 0.03,
                "turnover_ratio": 1.8,
                "concentration_top1": 0.28,
            },
            "leaders": [
                {"security_code": "4588", "name": "Oncolys Bio", "intraday_return": 0.077}
            ],
            "flow_state": "STRONG_INFLOW",
            "acceleration_state": "UNKNOWN",
        }
    ]
    page = money_flow.render_page(sector_snapshot, intraday_flows)

    # Check medium-term section exists and shows COLD
    assert "MEDIUM-TERM SECTOR REGIME" in page
    assert "Pharmaceutical" in page
    assert "COLD" in page

    # Check intraday section exists and shows STRONG_INFLOW
    assert "INTRADAY SUBSECTOR / THEME FLOW" in page
    assert "Biotechnology" in page
    assert "STRONG_INFLOW" in page

    # Check that medium-term regime is shown within subsector card
    assert "Medium-term regime:" in page
    assert page.index("Medium-term regime:") < page.index("Intraday flow:")

    # Check that both COLD (medium-term) and STRONG_INFLOW (intraday) appear
    cold_index = page.index("COLD")
    inflow_index = page.index("STRONG_INFLOW")
    assert cold_index < inflow_index  # COLD appears before STRONG_INFLOW in the page


def test_render_intraday_flow_card_shows_hierarchy():
    """Intraday flow card must show Sector → Subsector → Leaders hierarchy."""
    flow = {
        "schema_version": 1,
        "observed_at": "2026-08-14T10:30:00+09:00",
        "source": "test",
        "freshness": "FRESH",
        "data_completeness": "COMPLETE",
        "benchmark": "TOPIX",
        "sector": {
            "id": "sector:pharmaceutical",
            "label": "Pharmaceutical",
            "medium_term_regime": "COLD",
        },
        "subsector": {
            "id": "subsector:biotechnology",
            "label": "Biotechnology",
            "taxonomy_version": "test-v1",
            "as_of": "2026-08-14",
            "source_or_authority": "test",
        },
        "observations": {
            "intraday_return": 0.036,
            "benchmark_return": 0.009,
            "relative_return": 0.027,
            "rising_count": 4,
            "constituent_count": 5,
            "breadth": 0.8,
            "median_constituent_return": 0.03,
            "turnover_ratio": 1.8,
            "concentration_top1": 0.28,
        },
        "leaders": [
            {"security_code": "4588", "name": "Oncolys Bio", "intraday_return": 0.077},
            {"security_code": "4592", "name": "SanBio", "intraday_return": 0.041},
        ],
        "flow_state": "STRONG_INFLOW",
        "acceleration_state": "UNKNOWN",
    }
    card = money_flow._render_intraday_flow_card(flow)

    # Check Sector shown as parent
    assert "Parent Sector: Pharmaceutical" in card

    # Check Subsector shown as title
    assert "<h3>Biotechnology</h3>" in card

    # Check Leaders section
    assert "Leaders" in card
    assert "4588" in card
    assert "Oncolys Bio" in card
    assert "4592" in card
    assert "SanBio" in card


def test_render_intraday_flow_card_shows_observations():
    """Intraday flow card must display key observations: return, relative, breadth, concentration."""
    flow = {
        "schema_version": 1,
        "observed_at": "2026-08-14T10:30:00+09:00",
        "source": "test",
        "freshness": "FRESH",
        "data_completeness": "COMPLETE",
        "benchmark": "TOPIX",
        "sector": {
            "id": "sector:test",
            "label": "Test Sector",
            "medium_term_regime": "NEUTRAL",
        },
        "subsector": {
            "id": "subsector:test",
            "label": "Test Subsector",
            "taxonomy_version": "test-v1",
            "as_of": "2026-08-14",
            "source_or_authority": "test",
        },
        "observations": {
            "intraday_return": 0.036,
            "benchmark_return": 0.009,
            "relative_return": 0.027,
            "rising_count": 4,
            "constituent_count": 5,
            "breadth": 0.8,
            "median_constituent_return": 0.03,
            "turnover_ratio": 1.8,
            "concentration_top1": 0.28,
        },
        "leaders": [],
        "flow_state": "INFLOW",
        "acceleration_state": "STABLE",
    }
    card = money_flow._render_intraday_flow_card(flow)

    assert "Subsector return:" in card
    assert "+3.6%" in card
    assert "vs Benchmark:" in card
    assert "+2.7pt" in card
    assert "Breadth:" in card
    assert "80%" in card
    assert "Turnover ratio:" in card
    assert "1.8x" in card
    assert "Top-1 concentration:" in card
    assert "28%" in card


def test_render_page_shows_interpretation_guidance():
    """Page must include interpretation guidance explaining two-tier structure and non-directive use."""
    page = money_flow.render_page(sector_snapshot=None, intraday_flows=[])

    assert "INTERPRETATION" in page
    assert "Two Time Scales, Two Signals" in page
    assert "Medium-term Sector Regime" in page
    assert "Intraday Subsector Flow" in page
    assert "NOT a contradiction" in page
    assert "Non-Directive Guardrail" in page
    assert "NOT an automatic BUY/SELL command" in page
    assert "evidence signal" in page


def test_flow_state_and_acceleration_icons_displayed():
    """Flow state and acceleration state must be displayed with icons."""
    flow = {
        "sector": {"id": "test", "label": "Test", "medium_term_regime": "NEUTRAL"},
        "subsector": {"id": "test", "label": "Test", "taxonomy_version": "v1", "as_of": "2026-08-14", "source_or_authority": "test"},
        "observed_at": "2026-08-14T10:00:00+09:00",
        "freshness": "FRESH",
        "data_completeness": "COMPLETE",
        "observations": {"intraday_return": 0.01, "benchmark_return": 0.005, "relative_return": 0.005, "rising_count": 5, "constituent_count": 10, "breadth": 0.5, "median_constituent_return": 0.01, "turnover_ratio": 1.0, "concentration_top1": 0.2},
        "leaders": [],
        "flow_state": "STRONG_INFLOW",
        "acceleration_state": "ACCELERATING",
    }
    card = money_flow._render_intraday_flow_card(flow)
    assert "🔥" in card  # STRONG_INFLOW icon
    assert "⚡" in card  # ACCELERATING icon
