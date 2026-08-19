#!/usr/bin/env python3
"""
BOJ Early Warning Signal State Engine

Determines BOJ policy risk signal state (GREEN / ORANGE / RED) based on:
1. Primary BOJ policy evidence (statements, minutes, speeches)
2. Market-implied probabilities (JGB, OIS, FX)
3. Macro indicators (CPI, PPI, import prices)

CRITICAL: Market probability alone CANNOT trigger RED.
RED requires primary BOJ evidence of imminent rate hike.

Owner: 🌅アサヒ (Asahi)
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class SignalState(Enum):
    """BOJ early warning signal states"""
    GREEN = "GREEN"
    ORANGE = "ORANGE"
    RED = "RED"


class HawkishnessLevel(Enum):
    """Classification of BOJ communication hawkishness"""
    DOVISH = "dovish"
    NEUTRAL = "neutral"
    MODERATELY_HAWKISH = "moderately_hawkish"
    HAWKISH = "hawkish"
    EXPLICITLY_IMMINENT = "explicitly_imminent"


@dataclass
class PrimaryEvidence:
    """Primary BOJ policy evidence"""
    type: str  # statement, minutes, speech, outlook_report, policy_decision
    date: str
    summary: str
    hawkishness: str
    source_url: Optional[str] = None


@dataclass
class MarketImpliedEvidence:
    """Market-implied rate hike expectations"""
    next_meeting_hike_probability: float
    as_of_date: str
    jgb_2y_yield: Optional[float] = None
    jgb_5y_yield: Optional[float] = None
    ois_rate: Optional[float] = None
    usdjpy_spot: Optional[float] = None


@dataclass
class MacroIndicators:
    """Supporting macro indicators"""
    cpi_yoy: Optional[float] = None
    ppi_yoy: Optional[float] = None
    import_price_yoy: Optional[float] = None


@dataclass
class BOJSignalState:
    """Complete BOJ early warning signal state"""
    version: str
    timestamp: str
    signal_state: str
    evidence: Dict[str, Any]
    state_transition_rationale: str
    next_mpm_date: str
    portfolio_impact: Optional[Dict[str, int]] = None


class BOJEarlyWarningEngine:
    """
    BOJ Early Warning Signal State Engine
    
    State transition rules:
    - GREEN: Weak evidence of imminent rate hike
    - ORANGE: Multiple indicators (inflation, hawkish breadth, market pricing, FX/JGB)
    - RED: PRIMARY evidence of imminent hike OR actual policy decision
    
    CRITICAL: Market probability alone CANNOT promote to RED.
    """
    
    # Thresholds for state determination
    ORANGE_MARKET_PROB_THRESHOLD = 0.50  # 50% market-implied probability
    RED_MARKET_PROB_THRESHOLD = 0.70  # 70% - still not sufficient alone for RED
    
    def __init__(self):
        self.version = "1.0.0"
    
    def determine_signal_state(
        self,
        primary_evidence: List[PrimaryEvidence],
        market_evidence: MarketImpliedEvidence,
        macro_indicators: Optional[MacroIndicators] = None,
        next_mpm_date: Optional[str] = None
    ) -> BOJSignalState:
        """
        Determine current BOJ signal state from evidence.
        
        Returns complete signal state with rationale.
        """
        # Check for RED conditions first (most restrictive)
        red_check = self._check_red_conditions(primary_evidence, market_evidence)
        if red_check["is_red"]:
            state = SignalState.RED.value
            rationale = red_check["rationale"]
        else:
            # Check for ORANGE conditions
            orange_check = self._check_orange_conditions(
                primary_evidence, market_evidence, macro_indicators
            )
            if orange_check["is_orange"]:
                state = SignalState.ORANGE.value
                rationale = orange_check["rationale"]
            else:
                state = SignalState.GREEN.value
                rationale = "No significant evidence of imminent BOJ rate hike"
        
        # Package evidence
        evidence_dict = {
            "primary": [asdict(ev) for ev in primary_evidence],
            "market_implied": asdict(market_evidence)
        }
        if macro_indicators:
            evidence_dict["macro_indicators"] = asdict(macro_indicators)
        
        return BOJSignalState(
            version=self.version,
            timestamp=datetime.utcnow().isoformat() + "Z",
            signal_state=state,
            evidence=evidence_dict,
            state_transition_rationale=rationale,
            next_mpm_date=next_mpm_date or ""
        )
    
    def _check_red_conditions(
        self,
        primary_evidence: List[PrimaryEvidence],
        market_evidence: MarketImpliedEvidence
    ) -> Dict[str, Any]:
        """
        Check if RED state conditions are met.
        
        RED requires PRIMARY evidence:
        1. Governor/Deputy Governor/Multiple board members signal imminent hike
        2. Summary of Opinions / Outlook / Statement confirms imminent hike
        3. Actual policy decision (rate increase)
        4. Exception: Explicit Market Weather RED threshold triggered
        
        Market probability alone does NOT trigger RED.
        """
        # Check for explicitly imminent primary evidence
        has_imminent_evidence = any(
            ev.hawkishness == HawkishnessLevel.EXPLICITLY_IMMINENT.value
            for ev in primary_evidence
        )
        
        if has_imminent_evidence:
            return {
                "is_red": True,
                "rationale": "PRIMARY EVIDENCE: BOJ officials/statements explicitly signal imminent rate hike"
            }
        
        # Check for actual policy decision
        has_policy_decision = any(
            ev.type == "policy_decision" and ev.hawkishness in ["hawkish", "explicitly_imminent"]
            for ev in primary_evidence
        )
        
        if has_policy_decision:
            return {
                "is_red": True,
                "rationale": "PRIMARY EVIDENCE: BOJ policy decision indicates rate hike"
            }
        
        # Market probability alone is NOT sufficient for RED
        return {"is_red": False, "rationale": ""}
    
    def _check_orange_conditions(
        self,
        primary_evidence: List[PrimaryEvidence],
        market_evidence: MarketImpliedEvidence,
        macro_indicators: Optional[MacroIndicators]
    ) -> Dict[str, Any]:
        """
        Check if ORANGE state conditions are met.
        
        ORANGE requires multiple factors:
        - Inflation/import prices trending up
        - BOJ hawkish breadth expanding
        - Market pricing increasing
        - JPY weakness / JGB yield rise / energy shock pressuring normalization
        """
        orange_factors = []
        
        # Factor 1: Market probability elevated
        if market_evidence.next_meeting_hike_probability >= self.ORANGE_MARKET_PROB_THRESHOLD:
            orange_factors.append(
                f"Market-implied hike probability at {market_evidence.next_meeting_hike_probability:.1%}"
            )
        
        # Factor 2: Hawkish breadth in primary evidence
        hawkish_count = sum(
            1 for ev in primary_evidence
            if ev.hawkishness in ["moderately_hawkish", "hawkish"]
        )
        if hawkish_count >= 2:
            orange_factors.append(f"Multiple hawkish BOJ communications ({hawkish_count})")
        
        # Factor 3: Inflation indicators elevated
        if macro_indicators:
            if macro_indicators.ppi_yoy and macro_indicators.ppi_yoy > 5.0:
                orange_factors.append(f"PPI elevated at {macro_indicators.ppi_yoy:.1f}% YoY")
            if macro_indicators.import_price_yoy and macro_indicators.import_price_yoy > 20.0:
                orange_factors.append(f"Import prices elevated at {macro_indicators.import_price_yoy:.1f}% YoY")
        
        # Need at least 2 factors for ORANGE
        is_orange = len(orange_factors) >= 2
        rationale = "ORANGE: " + "; ".join(orange_factors) if is_orange else ""
        
        return {"is_orange": is_orange, "rationale": rationale}

