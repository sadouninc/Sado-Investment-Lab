# 4592 サンバイオ — BOJ Sensitivity Evidence

担当: 🌅アサヒ  
種別: Research / Policy Intelligence  
Issue: #512  
Evidence date: 2026-08-13

## Canonical position
- Position: 現物100株
- Authority: root `Current_Status.md` / SBI VERIFIED snapshot

## Primary evidence
Official SanBio IR confirms the company is a regenerative-medicine / cell-therapy developer and publishes financial results, securities reports, financial highlights and pipeline disclosures through its IR library.

Primary source URLs:
- https://www.sanbio.com/ir/library/
- https://www.sanbio.com/ir/financial_results/
- https://www.sanbio.com/ir/highlights/

## Sensitivity assessment
```yaml
rate_sensitivity: MEDIUM
yen_sensitivity: UNKNOWN
energy_input_sensitivity: LOW
valuation_duration: HIGH
balance_sheet_rate_risk: UNKNOWN
boj_orange_action: WATCH
boj_red_action: REDUCE_CANDIDATE_REVIEW_IF_FUNDING_OR_VALUATION_STRESS
confidence: MEDIUM
```

## Rationale
### Valuation duration
SanBio's equity value is strongly tied to future commercialization, manufacturing scale-up, approval/launch progress and long-dated future cash flows. Higher Japanese discount rates can therefore compress valuation even without verified direct debt sensitivity.

### Funding / balance sheet
Biotech commercialization and manufacturing scale-up can require meaningful capital, but the current BOJ inventory does not infer debt or liquidity risk from industry alone. Current interest-bearing debt, cash runway and financing terms must be verified from the latest filing before changing `balance_sheet_rate_risk` from UNKNOWN.

### Energy / yen
The company is not a data-center or heavy industrial power consumer, so direct energy-input sensitivity is LOW. Foreign development, manufacturing and commercialization links can create FX exposure; however, the net direction is not asserted without current primary evidence and remains UNKNOWN.

## BOJ Early Warning implication
ORANGE: `WATCH`. Main current concern is high valuation duration rather than a verified floating-rate debt burden.

RED: `REDUCE_CANDIDATE_REVIEW` only when BOJ RED coincides with funding/runway stress, a broad high-duration biotech selloff, or deterioration in company-specific commercialization evidence. BOJ RED alone is not an automatic exit.

No automatic BUY/SELL. Missing debt/runway evidence remains UNKNOWN. Issue #79 untouched.
