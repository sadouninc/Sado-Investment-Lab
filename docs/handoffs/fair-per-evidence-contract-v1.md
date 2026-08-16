# Fair PER Evidence Contract v1 — Machine-Readable Research Boundary

担当: ❤️レイ  
関連Issue: #626 Fair PER Evidence Framework, #403 Sony Entry Review  
状態: `IMPLEMENTATION_COMPLETE`  
Version: v1.0  
Date: 2026-08-16

## Goal

Promote Sony #403's Fair PER estimation methodology to a **common framework** for all stocks in Sado Investment Lab. Enable separation of "good company" from "good entry price" through structured, machine-readable evidence contracts.

## Core Philosophy

```
Fair PER = f(
    Historical valuation, 
    EPS growth, 
    Earnings quality, 
    Business mix, 
    Cyclicality/Risk, 
    Capital allocation, 
    Peer valuation, 
    Optionality evidence, 
    Macro discount rate, 
    Market expectation
)
```

### Key Principles

1. **Fair PER is a RANGE, not a point estimate**
   - Always express as `min / base / max` with `confidence`
   - Range reflects uncertainty and evidence quality

2. **Evidence stages must be preserved**
   - Intent → Operating Evidence → Financial Realization
   - Never promote Intent to Financial Realization
   - Only Financial Realization enters current valuation baseline

3. **Optionality is option value ONLY**
   - Track as upside potential
   - Do NOT mix unrealized optionality into current EPS
   - Example: Sony Physical AI is tracked but not added to FY2026 EPS

4. **Fail-closed for stale/unknown data**
   - STALE/FAILED/UNKNOWN price → current valuation fields remain UNKNOWN
   - Research-derived Fair Value Range can exist independently
   - Never fallback to stale, fixture, or incorrect-identity data

5. **Framework provides evidence, not decisions**
   - NO BUY/SELL/HOLD signal generation
   - Entry Zone requires high confidence and sufficient evidence
   - Owner Authority makes final investment decisions

## 10 Evidence Factors

### Factor 1: Historical Valuation Evidence

**Purpose**: Self-comparison against own past PER and profit phase context.

**Schema**: `HistoricalValuationEvidence`

**Fields**:
- `historical_per_range_min/max/median`: Historical PER range and median
- `profit_phase`: `"GROWTH"` / `"MATURITY"` / `"DECLINE"` / `"TURNAROUND"` / `"UNKNOWN"`
- `abnormal_years_excluded`: Tuple of excluded years with rationale
- `period_start` / `period_end`: Analysis period
- `data_quality`: `DataQuality` enum
- `notes`: Additional context

**Guardrails**:
- ❌ Do NOT use simple historical average as Fair PER
- ❌ Do NOT include red ink years, accounting basis changes, extraordinary events
- ✅ Explicitly document excluded abnormal years
- ✅ Account for profit phase context (growth vs. maturity)

**Example** (Sony):
```python
HistoricalValuationEvidence(
    historical_per_range_min=15.0,
    historical_per_range_max=22.0,
    historical_per_median=18.0,
    profit_phase="GROWTH",
    abnormal_years_excluded=(
        "FY2020: COVID impact",
        "FY2012: Restructuring losses"
    ),
    period_start="FY2018",
    period_end="FY2026",
    data_quality=DataQuality.FRESH,
)
```

---

### Factor 2: EPS Growth Evidence

**Purpose**: Growth rate, revision direction, sustainability assessment.

**Schema**: `EPSGrowthEvidence`

**Fields**:
- `eps_growth_3y_cagr` / `eps_growth_5y_cagr`: Growth CAGR
- `recent_revision_direction`: `"UPGRADE"` / `"DOWNGRADE"` / `"STABLE"` / `"UNKNOWN"`
- `sustainability_assessment`: `"HIGH"` / `"MEDIUM"` / `"LOW"` / `"UNKNOWN"`
- `data_quality`: `DataQuality` enum
- `notes`: Rationale

**Example** (Sony):
```python
EPSGrowthEvidence(
    eps_growth_3y_cagr=0.12,
    eps_growth_5y_cagr=0.15,
    recent_revision_direction="UPGRADE",
    sustainability_assessment="MEDIUM",
    data_quality=DataQuality.FRESH,
    notes="FY2026 Q1 operating income +40% YoY, guidance upgraded",
)
```

---

### Factor 3: Earnings Quality Evidence

**Purpose**: Margin, recurring nature, FCF conversion.

**Schema**: `EarningsQualityEvidence`

**Fields**:
- `operating_margin`: Operating margin ratio
- `recurring_revenue_ratio`: Subscription, maintenance, etc.
- `fcf_conversion_ratio`: FCF / Net Income
- `quality_assessment`: `"HIGH"` / `"MEDIUM"` / `"LOW"` / `"UNKNOWN"`
- `data_quality`: `DataQuality` enum
- `notes`: Additional context

**Example** (Sony):
```python
EarningsQualityEvidence(
    operating_margin=0.167,
    recurring_revenue_ratio=0.35,
    fcf_conversion_ratio=0.85,
    quality_assessment="HIGH",
    data_quality=DataQuality.FRESH,
    notes="Multiple recurring engines: G&NS, Music, Pictures",
)
```

---

### Factor 4: Business Mix Evidence

**Purpose**: High-profit, recurring segment composition and trend.

**Schema**: `BusinessMixEvidence`

**Fields**:
- `high_margin_segment_ratio`: Ratio of high-margin segments
- `recurring_segment_ratio`: Ratio of recurring revenue segments
- `segment_diversification`: `"HIGH"` / `"MEDIUM"` / `"LOW"` / `"UNKNOWN"`
- `mix_trend`: `"IMPROVING"` / `"STABLE"` / `"DETERIORATING"` / `"UNKNOWN"`
- `data_quality`: `DataQuality` enum
- `notes`: Context

---

### Factor 5: Cyclicality / Risk Evidence

**Purpose**: Business exposure to external cycles and structural risks.

**Schema**: `CyclicalityRiskEvidence`

**Fields**:
- `economic_cycle_sensitivity`: `"HIGH"` / `"MEDIUM"` / `"LOW"` / `"UNKNOWN"`
- `fx_exposure` / `commodity_exposure` / `regulatory_risk` / `disaster_risk`: Risk levels
- `overall_risk_assessment`: Overall risk rating
- `data_quality`: `DataQuality` enum
- `notes`: Context

**Example** (Sony):
```python
CyclicalityRiskEvidence(
    economic_cycle_sensitivity="MEDIUM",
    fx_exposure="MEDIUM",
    regulatory_risk="LOW",
    disaster_risk="MEDIUM",
    overall_risk_assessment="MEDIUM",
    data_quality=DataQuality.FRESH,
    notes="Kumamoto earthquake monitored; diversification reduces single-cycle risk",
)
```

---

### Factor 6: Capital Allocation Evidence

**Purpose**: Shareholder value creation through capital deployment.

**Schema**: `CapitalAllocationEvidence`

**Fields**:
- `buyback_yield` / `share_dilution_3y`: Shareholder return metrics
- `roe` / `roic`: Return on equity and invested capital
- `debt_to_equity`: Balance sheet health
- `allocation_quality`: `"HIGH"` / `"MEDIUM"` / `"LOW"` / `"UNKNOWN"`
- `data_quality`: `DataQuality` enum
- `notes`: Context

---

### Factor 7: Peer Valuation Evidence

**Purpose**: Relative valuation with quality/growth adjustments.

**Schema**: `PeerValuationEvidence`

**Fields**:
- `peer_per_range_min/max/median`: Peer PER range
- `growth_adjusted_premium`: Expected premium/discount for growth differential
- `quality_adjusted_premium`: Expected premium/discount for quality differential
- `adjustment_rationale`: Explanation of adjustments
- `data_quality`: `DataQuality` enum
- `notes`: Context

**Guardrails**:
- ❌ Do NOT do simple peer comparison without adjustments
- ✅ Adjust for growth rate differences
- ✅ Adjust for margin differences
- ✅ Adjust for business quality differences

**Example** (Sony):
```python
PeerValuationEvidence(
    peer_per_range_min=16.0,
    peer_per_range_max=20.0,
    peer_per_median=18.0,
    growth_adjusted_premium=0.05,  # +5% for diversification
    quality_adjusted_premium=0.05,  # +5% for quality
    adjustment_rationale="Multiple earnings engines, recurring revenue, I&SS tech leadership",
    data_quality=DataQuality.FRESH,
)
```

---

### Factor 8: Optionality Evidence ⚠️ CRITICAL

**Purpose**: Track future themes and new business potential WITHOUT mixing into current EPS.

**Schema**: `OptionalityEvidence`

**Fields**:
- `optionality_themes`: Tuple of theme names
- `evidence_stage`: `EvidenceStage` enum (INTENT / OPERATING_EVIDENCE / FINANCIAL_REALIZATION)
- `potential_upside`: `"HIGH"` / `"MEDIUM"` / `"LOW"` / `"UNKNOWN"`
- `per_premium_if_realized`: Potential PER premium if realized
- `realization_timeline`: `"1Y"` / `"2-3Y"` / `"3-5Y"` / `"UNKNOWN"`
- `data_quality`: `DataQuality` enum
- `notes`: Context

**CRITICAL GUARDRAILS**:
- ❌ **NEVER add unrealized optionality to current EPS**
- ❌ **NEVER promote Intent to Financial Realization**
- ✅ Track evidence progression: Intent → Operating Evidence → Financial Realization
- ✅ Only Financial Realization enters valuation baseline
- ✅ Optionality provides upside asymmetry context, not baseline

**Evidence Stage Definitions**:
- **INTENT**: Plans, announcements, strategies (e.g., "AI Vision strategy announced")
- **OPERATING_EVIDENCE**: Design wins, orders, partnerships (e.g., "Major automotive sensor design win")
- **FINANCIAL_REALIZATION**: Revenue and profit in actual results (e.g., "AI sensor revenue +50% YoY")

**Example** (Sony Physical AI):
```python
OptionalityEvidence(
    optionality_themes=(
        "AI Vision",
        "Physical AI",
        "Robotics Sensing",
        "Automotive Sensing"
    ),
    evidence_stage=EvidenceStage.OPERATING_EVIDENCE,  # Design wins exist
    potential_upside="HIGH",
    per_premium_if_realized=2.0,  # +2 PER points if materialized
    realization_timeline="2-3Y",
    data_quality=DataQuality.FRESH,
    notes="I&SS sensor tech → AI Vision design wins tracked; NOT in current baseline EPS",
)
```

---

### Factor 9: Macro Discount Rate Evidence

**Purpose**: Interest rate and equity risk premium context.

**Schema**: `MacroDiscountRateEvidence`

**Fields**:
- `risk_free_rate`: 10Y government bond yield
- `equity_risk_premium`: ERP estimate
- `discount_rate_assessment`: `"LOW"` / `"NORMAL"` / `"HIGH"` / `"UNKNOWN"`
- `macro_environment`: `"ACCOMMODATIVE"` / `"NEUTRAL"` / `"RESTRICTIVE"`
- `data_quality`: `DataQuality` enum
- `notes`: Context

---

### Factor 10: Market Expectation Evidence

**Purpose**: Reverse-engineer what market is pricing in.

**Schema**: `MarketExpectationEvidence`

**Fields**:
- `current_price` / `price_as_of`: Current market price and timestamp
- `current_eps`: Current or forward EPS used for PER calculation
- `implied_per`: Price / EPS
- `implied_scenario`: `"BEAR"` / `"BASE"` / `"BULL"` / `"BEYOND_BULL"` / `"UNKNOWN"`
- `expectation_gap`: `"MARKET_TOO_OPTIMISTIC"` / `"FAIR"` / `"MARKET_TOO_PESSIMISTIC"`
- `data_quality`: `DataQuality` enum (FRESH / STALE / FAILED / UNKNOWN)
- `notes`: Context

**Fail-Closed Guardrails**:
- If `data_quality` is STALE / FAILED / UNKNOWN:
  - `current_price` → `None`
  - `implied_per` → `None`
  - `implied_scenario` → `"UNKNOWN"`
- Research-derived Fair Value Range remains available independently

---

## Output Contract

### Scenario EPS

**Schema**: `ScenarioEPS`

**Fields**:
- `bear_eps` / `base_eps` / `bull_eps`: Three scenario EPS values
- `scenario_as_of`: Scenario timestamp (distinct from `price_as_of`)
- `fiscal_year`: Target fiscal year
- `share_basis`: "Diluted weighted average" or other basis
- `data_quality`: `DataQuality` enum
- `notes`: Assumptions and context

---

### Fair PER Range

**Schema**: `FairPERRange`

**Fields**:
- `fair_per_min` / `fair_per_max` / `fair_per_base`: PER range
- `confidence`: `Confidence` enum (LOW / MEDIUM / HIGH / UNKNOWN)
- `as_of`: Timestamp
- `rationale`: Explanation
- `data_quality`: `DataQuality` enum

**Principle**: Fair PER is always a **range**, not a single point.

---

### Valuation Matrix

**Schema**: `ValuationMatrix`

Combines Fair PER Range × Scenario EPS:

| Scenario | EPS | Fair PER | Fair Value Range |
|----------|-----|----------|------------------|
| Bear | 180 | 18-20x | 3240-3600 |
| Base | 200 | 18-20x | 3600-4000 |
| Bull | 220 | 18-20x | 3960-4400 |

**Fields**:
- `bear_fair_value_min/max`
- `base_fair_value_min/max`
- `bull_fair_value_min/max`
- `matrix_as_of`: Timestamp
- `data_quality`: `DataQuality` enum

---

### Entry Zone

**Schema**: `EntryZone`

**Fields**:
- `entry_zone_min` / `entry_zone_max`: Entry price range
- `margin_of_safety`: Margin below fair value (e.g., 0.10 for 10%)
- `entry_zone_as_of`: Timestamp
- `sufficient_evidence`: Boolean flag
- `rationale`: Explanation

**Generation Rules**:
- ✅ Only when `confidence` is HIGH or MEDIUM with strong evidence
- ✅ Only when all required data is FRESH
- ✅ Entry Zone ≠ Fair Value Range (requires margin of safety)
- ❌ Framework does NOT generate BUY/SELL/HOLD signals

---

### Checkpoints

**Schema**: `Checkpoint`

**Types**:
- `STRENGTHENING`: Conditions that strengthen the investment case
- `INVALIDATION`: Conditions that invalidate the investment case
- `NEXT_CHECKPOINT`: Upcoming events to monitor

**Fields**:
- `checkpoint_type`: Checkpoint type
- `description`: Human-readable description
- `expected_date`: Expected date (if applicable)
- `trigger_condition`: Specific trigger

---

## Authority Boundary

### Framework Provides:
- ✅ Fair PER Range with Confidence
- ✅ Evidence across 10 factors
- ✅ Valuation Matrix (Fair PER × Scenario EPS)
- ✅ Entry Zone (when sufficient evidence)
- ✅ Strengthening / Invalidation / Checkpoint conditions

### Framework Does NOT Provide:
- ❌ BUY/SELL/HOLD signals
- ❌ Automatic investment decisions
- ❌ Portfolio allocation recommendations
- ❌ Timing signals

### Owner Authority:
- 👑 Final BUY/SELL/HOLD decision
- 👑 Position sizing
- 👑 Entry timing
- 👑 Exit timing

### Pages / Decision Board:
- ✅ Display Fair PER Evidence Contract
- ✅ Show Entry Zone when available
- ❌ Do NOT generate independent Fair PER
- ❌ Do NOT generate BUY/SELL/HOLD signals

---

## Validation Rules

The framework includes built-in validation functions:

1. **`validate_evidence_stage_separation`**: Ensures Intent is not promoted to Financial Realization
2. **`validate_stale_price_fail_closed`**: Ensures STALE/FAILED/UNKNOWN data fails closed
3. **`validate_abnormal_years_excluded`**: Ensures abnormal years are documented
4. **`validate_no_buy_sell_hold_generation`**: Ensures no decision signals in output
5. **`validate_fair_per_evidence_contract`**: Runs all validation rules

---

## Usage Example: Sony #403 Pilot

See `tests/test_fair_per_evidence.py::_sony_403_fixture()` for complete Sony Fair PER Evidence Contract.

**Key Highlights**:
- All 10 factors populated
- Optionality at Operating Evidence stage, NOT in baseline EPS
- Fair PER 18-20x with MEDIUM confidence
- Entry Zone 3400-3800 with 10% margin of safety
- Checkpoints for strengthening (I&SS margin) and invalidation (smartphone weakness)

---

## Implementation

**Files**:
- `scripts/fair_per_evidence.py`: Core framework
- `tests/test_fair_per_evidence.py`: Test suite and fixtures
- `docs/handoffs/fair-per-evidence-contract-v1.md`: This document

**Acceptance Tests**: All pass ✅

```bash
python -m pytest -q tests/test_fair_per_evidence.py
```

---

## Next Steps

1. Apply framework to at least 1 additional stock for reproducibility validation
2. Integrate with Decision Board (#403) display
3. Integrate with Canonical Market Data (#633) for price identity gate
4. Extend to all Watchlist / Strong Watch stocks
5. Build Fair PER revision tracking over time

---

## Related

- #626 Fair PER Evidence Contract v1
- #403 Sony Entry Review
- #633 Canonical Market Data
- #308 Bear/Base/Bull Scenario Evolution
- #402 Investment Review Display Contract
