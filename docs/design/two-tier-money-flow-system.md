# Two-Tier Money Flow System

**Issue:** #79  
**Product Owner:** 🌙ルナ  
**Priority:** P1  
**Status:** Implemented (PR1-PR4)

## Background

On 2026-08-14, the existing Money Flow showed `Pharmaceutical: COLD → COLD`, but TradingView showed Biotechnology +3.6%, Oncolys Bio +7.7%, SanBio +4%, indicating clear short-term capital inflow into the bio subsector. The existing Money Flow focuses on medium-term sector regimes (TOPIX-17 ETF proxy, 5d/20d/60d relative return), which is effective for medium-term sector trends but cannot detect localized intraday capital flows.

This gap affected real investment decisions. When fully exiting Oncolys Bio the day before, if Biotechnology's short-term flow acceleration had been visible, a Core Position retention could have been reconsidered.

## Goal

Create a two-tier Money Flow system without replacing existing COLD/WARMING/HOT:

1. **Medium-term Sector Regime** — Current COLD/WARMING/HOT (preserved)
2. **Intraday Subsector/Theme Flow** — Early observation of same-day capital inflow/outflow/acceleration

Enable drill-down through hierarchy:

```
Market → Sector → Subsector/Theme → Stock
```

## Product Contract

Example display:

```
Pharmaceutical
Medium-term regime: COLD → COLD

Biotechnology
Intraday flow: 🔥 STRONG INFLOW
Subsector return: +3.6%
vs TOPIX: +2.7pt
Breadth: 78%
Turnover/volume ratio: 1.8x

Leaders
4588 Oncolys Bio   +7.7%
4592 SanBio        +4.1%
```

**Critical:** Do NOT overwrite `Pharmaceutical=COLD` with intraday flow. Medium-term regime and intraday flow are different time scales and separate signals.

## Architecture

### Data Model

**Contract:** `data/contracts/intraday-subsector-flow-v1.schema.json`

Key fields:
- `sector.medium_term_regime` — Preserves existing COLD/WARMING/HOT
- `flow_state` — Intraday classification (STRONG_INFLOW, INFLOW, MIXED, OUTFLOW, STRONG_OUTFLOW, UNKNOWN)
- `acceleration_state` — Change vs previous snapshot (ACCELERATING, DECELERATING, REVERSING, STABLE, UNKNOWN)
- `observations` — Intraday return, benchmark-relative return, breadth, median constituent return, turnover ratio, concentration
- `leaders` — Top constituents by return
- `observed_at`, `source`, `freshness`, `data_completeness` — Provenance and quality

### Classification

**Harness:** `scripts/intraday_subsector_classifier_harness.py`  
**Threshold Profile:** `data/config/intraday-flow-threshold-profile-v1.json`

Classification uses transparent rule-based thresholds, not black-box ML. Threshold profile includes:
- Version, source/authority, rationale, created_at
- Flow rules (conditions for STRONG_INFLOW, INFLOW, etc.)
- Acceleration rules (conditions for ACCELERATING, DECELERATING, etc.)

**Threshold Change Policy:** All threshold changes require explicit 👑Authority approval with documented rationale and version increment. This guards against post-hoc threshold fitting.

### Taxonomy

**Config:** `data/config/money-flow-subsectors-v1.json`

TOPIX-17 is too coarse. Subsector taxonomy enables:

```
Healthcare / Pharmaceutical (TOPIX-17 sector)
  ├─ Biotechnology (subsector)
  │   ├─ 4588 Oncolys BioPharma
  │   ├─ 4592 SanBio
  │   ├─ 4563 AnGes
  │   └─ ...
  └─ Large-cap Pharma (subsector)
      ├─ 4502 Takeda
      └─ ...
```

Membership includes:
- Security code, company name, symbol
- Inclusion rationale and evidence reference
- Membership version and as_of date

### Pages Integration

**Builder:** `.github/pages/build_money_flow_page.py`  
**Output:** `site/market/money-flow/index.md`

Page structure:
1. **Medium-term Sector Regime** section — Shows TOPIX-17 sector COLD/WARMING/HOT
2. **Intraday Subsector/Theme Flow** section — Shows intraday flow cards grouped by sector
3. **Interpretation** section — Explains two time scales and non-directive guardrail usage

Each intraday flow card shows:
- Parent sector and medium-term regime
- Subsector label
- Flow state (STRONG_INFLOW, etc.) with icon
- Acceleration state (ACCELERATING, etc.) with icon
- Observations (return, relative return, breadth, turnover, concentration)
- Leaders (top 5 constituents)
- Metadata (observed_at, freshness, completeness)

## Flow State Definitions

From `data/config/intraday-flow-threshold-profile-v1.json`:

### Flow States

- **STRONG_INFLOW**: Relative return ≥2.5% vs benchmark, broad participation (≥60% rising), low concentration (≤40% from top constituent)
- **INFLOW**: Relative return ≥1.0% vs benchmark, moderate participation (≥50% rising)
- **MIXED**: Neither clear inflow nor outflow (default state)
- **OUTFLOW**: Relative return ≤-1.0% vs benchmark, weak participation (≤40% rising)
- **STRONG_OUTFLOW**: Relative return ≤-2.5% vs benchmark, very weak participation (≤30% rising), low concentration
- **UNKNOWN**: Data quality insufficient (STALE/PARTIAL) or classification rules not met

### Acceleration States

- **ACCELERATING**: Flow strengthening vs previous snapshot (relative return delta ≥1.5%, breadth delta ≥10pts)
- **DECELERATING**: Flow weakening vs previous snapshot (relative return delta ≤-1.5%, breadth delta ≤-10pts)
- **REVERSING**: Sharp reversal (relative return delta ≤-3.0%)
- **STABLE**: Flow rate stable (default when delta thresholds not met)
- **UNKNOWN**: No previous snapshot, data quality insufficient, or no explicit acceleration rules

## Key Observations

For each subsector/theme:

- **Intraday return** — Equal-weight average constituent return
- **Benchmark-relative return** — Intraday return - benchmark return (e.g., vs TOPIX)
- **Breadth** — rising_count / constituent_count (percentage of constituents with positive returns)
- **Median constituent return** — Median return (less sensitive to outliers than mean)
- **Turnover/volume ratio** — Median constituent turnover ratio vs baseline
- **Concentration (top-1)** — Share of positive return magnitude from strongest constituent
- **Leaders** — Top 5 constituents by return

Separating breadth and concentration avoids single large-cap distorting the whole subsector view.

## Data Source Policy

- Do NOT scrape external heatmaps (SBI/Brisk/TradingView)
- Use those only for product behavior validation/reference
- Production: aggregate from reproducible market data sources (constituent prices/volumes)
- Fail-closed on insufficient data: UNKNOWN/PARTIAL/STALE, NOT rounded to normal
- If source has delay (e.g., US stocks 15min delayed), explicitly show in UI

## Decision-Support Integration (Future)

Future integration with Decision Journal to provide non-directive guardrails:

```
⚠ Strong Theme Flow
Biotechnologyへの短期資金流入が加速しています。
この銘柄は現在Subsector leaderです。
全売却前にCore Position維持の要否を確認してください。
```

**Important:** This is NOT an automatic HOLD/BUY command. It does NOT override Thesis/valuation/risk/portfolio sizing. It is an evidence signal for Decision Review to prevent "I didn't know capital was flowing there" situations.

## Implementation Status

### ✅ Completed

**PR1 — Contract/Taxonomy/Snapshot Model**
- Contract: `data/contracts/intraday-subsector-flow-v1.schema.json`
- Validation: `scripts/intraday_subsector_flow.py`
- Taxonomy: `data/config/money-flow-subsectors-v1.json`
- Fixtures: `data/fixtures/intraday-subsector-flow-v1.json`, `data/fixtures/intraday-subsector-flow-biotechnology-2026-08-14.json`

**PR2 — Intraday Aggregation**
- Aggregation: `scripts/intraday_subsector_aggregation.py`
- Snapshot history management with identity tracking

**PR3 — State/Acceleration Classifier**
- Classifier harness: `scripts/intraday_subsector_classifier_harness.py`
- Threshold profile: `data/config/intraday-flow-threshold-profile-v1.json`
- Classifier script: `scripts/apply_intraday_flow_classifier.py`
- Transparent rule-based classification with provenance

**PR4 — Pages Integration**
- Page builder: `.github/pages/build_money_flow_page.py`
- Tests: `.github/pages/test_money_flow_page.py`
- Two-tier display: Medium-term + Intraday sections
- Sector → Subsector → Leaders hierarchy
- Example data: `data/generated/public/money-flow/intraday-subsector-flow.jsonl`

### 🚧 Future Work (Out of Scope v1)

**PR5 — Decision Guardrail Integration**
- Connect to Decision Journal/Decision UI
- Show Strong Theme Flow guardrails during sell decisions
- Integration with existing Decision layer (not blocking PR1-PR4)

**Additional Enhancements**
- Production data pipeline (scheduled intraday snapshot collection)
- Additional subsector/theme taxonomies
- Historical replay fixtures for backtesting classification profiles
- Automated testing with real market scenarios

## Acceptance Criteria

- ✅ Medium-term Sector Regime preserved, not overwritten by Intraday Flow
- ✅ Sector → Subsector/Theme → Stock hierarchy expressed
- ✅ Intraday snapshot includes observed_at, source, freshness, data_completeness
- ✅ Benchmark-relative return computed
- ✅ Breadth computed from constituent-level data
- ✅ Turnover/volume acceleration supported (when available)
- ✅ Leader/concentration displayed (distinguish single-stock surge from broad inflow)
- ✅ ACCELERATING/DECELERATING determined from multi-snapshot history
- ✅ Pharmaceutical=COLD + Biotechnology=STRONG_INFLOW displayed simultaneously
- ✅ Pages mobile-first design, Medium-term/Today/Leaders on one screen
- ✅ Stale/partial/unknown NOT rounded to normal
- ✅ Threshold profile version/provenance tracked

## Definition of Done

Codex can now express today's scenario: `Pharmaceutical = COLD / Biotechnology = intraday STRONG_INFLOW / Oncolys = leader` without contradiction. Users can discover "sector overall is cold, but capital is entering a specific subsector" after market open. Signal is saved/reproducible and can be cross-referenced with Decision Journal to verify "could flow signal have prevented full exit?"
