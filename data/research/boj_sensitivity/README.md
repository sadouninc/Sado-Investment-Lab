# BOJ Sensitivity Evidence - Company-by-Company Mapping

Owner: 🌅アサヒ (Asahi)  
Parent Contract: `06_Research/boj_early_warning_contract.md`

## Purpose

Machine-readable company-specific sensitivity profiles for BOJ rate hike risk.

**CRITICAL**: Do NOT infer sensitivity from sector/industry name alone. Each profile must be grounded in:
- Company IR disclosures (有価証券報告書, 決算短信)
- Verified financial statements
- Debt structure and maturity schedules
- Management guidance
- Operating leverage and cost structure

## File Format

Each `{ticker}.json` file contains:

```json
{
  "ticker": "3778",
  "name": "さくらインターネット",
  "rate_sensitivity": "HIGH",
  "yen_sensitivity": "MIXED",
  "energy_input_sensitivity": "MEDIUM",
  "valuation_duration": "HIGH",
  "balance_sheet_rate_risk": "HIGH",
  "boj_risk_action": "WATCH",
  "evidence_refs": [
    "06_Research/boj_early_warning_portfolio_sensitivity_2026-08-13.md",
    "Company IR FY2025 securities report"
  ],
  "confidence": "HIGH",
  "position_type": "LONG",
  "notes": "HIGH direct funding / capex sensitivity + HIGH valuation duration"
}
```

## Field Definitions

### Sensitivity Dimensions

**rate_sensitivity**: LOW / MEDIUM / HIGH / UNKNOWN  
Direct exposure to interest rate changes (floating debt, refinancing needs, capex funding)

**yen_sensitivity**: BENEFIT / NEUTRAL / HEADWIND / MIXED / UNKNOWN  
Impact of yen appreciation from BOJ rate hike (exports vs imports, overseas revenue, input costs)

**energy_input_sensitivity**: LOW / MEDIUM / HIGH / UNKNOWN  
Exposure to energy costs (may correlate with yen movements and inflation)

**valuation_duration**: LOW / MEDIUM / HIGH / UNKNOWN  
Sensitivity of equity valuation to discount rate changes (growth vs value, PER level, cash flow profile)

**balance_sheet_rate_risk**: LOW / MEDIUM / HIGH / UNKNOWN  
Balance sheet vulnerability to rate increases (debt ratio, fixed vs floating, maturity profile, interest coverage)

### Action Classification

**boj_risk_action**: HOLD / WATCH / REDUCE_CANDIDATE / EXIT_REVIEW / SHORT_THESIS_REVIEW

Determined by signal state and sensitivity profile:
- **HOLD**: No action from BOJ factor (GREEN state or low sensitivity)
- **WATCH**: Monitor for overlapping risks (ORANGE state + high sensitivity)
- **REDUCE_CANDIDATE**: Review for position reduction (RED state + high sensitivity)
- **EXIT_REVIEW**: Review for exit (RED + high sensitivity + thesis invalidation)
- **SHORT_THESIS_REVIEW**: Special handling for SHORT positions

### Evidence Quality

**confidence**: LOW / MEDIUM / HIGH

- **HIGH**: Verified from primary company disclosures
- **MEDIUM**: Partially verified, some reasonable inference
- **LOW**: Limited evidence, awaiting verification

**UNKNOWN sensitivities automatically get LOW confidence**

## Fail-Closed Behavior

Companies without evidence files return UNKNOWN profile:
- All sensitivity dimensions: UNKNOWN
- Action: HOLD
- Confidence: LOW
- Cannot be moved to REDUCE_CANDIDATE or EXIT_REVIEW based solely on BOJ factors

