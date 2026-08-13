# 4588 オンコリスバイオファーマ — BOJ Sensitivity Evidence

担当: 🌅アサヒ  
種別: Research / Policy Intelligence  
Issue: #512  
Evidence date: 2026-08-13

## Canonical position
- Position: 現物100株
- Authority: root `Current_Status.md` / SBI VERIFIED snapshot

## Primary evidence
Official company IR confirms Oncolys is a research-driven biotech company and maintains IR sections for financial results, securities reports, financial highlights and pipeline disclosures. The company FAQ explicitly states that it does not have stable recurring revenue and is a research-and-development-oriented biotech company.

Primary source URLs:
- https://www.oncolys.com/jp/ir/
- https://www.oncolys.com/jp/ir/faq.html

## Sensitivity assessment
```yaml
rate_sensitivity: MEDIUM
 yen_sensitivity: UNKNOWN
energy_input_sensitivity: LOW
valuation_duration: HIGH
balance_sheet_rate_risk: UNKNOWN
boj_orange_action: WATCH
boj_red_action: REDUCE_CANDIDATE_REVIEW_IF_FUNDING_RISK_CONFIRMED
confidence: MEDIUM
```

## Rationale
### Valuation duration
Oncolys is a clinical-stage / R&D biotech whose equity value depends heavily on future pipeline success, licensing economics, approval timing and future cash flows. That makes equity valuation sensitive to a higher discount rate even when direct bank-borrowing exposure is not yet verified.

### Funding / balance sheet
The company itself states that stable recurring sales are not a feature of the current business model. Therefore future R&D funding conditions matter, but current interest-bearing debt and financing runway are not classified from sector assumptions. `balance_sheet_rate_risk` remains `UNKNOWN` until the latest financial statements / financing disclosures are parsed.

### Energy / yen
The business is not a power-intensive infrastructure operator, so energy sensitivity is assessed LOW. Net FX sensitivity is left UNKNOWN because development/manufacturing/licensing cash flows may include overseas counterparties and foreign-currency exposure; no one-way conclusion is made without a current filing.

## BOJ Early Warning implication
ORANGE: `WATCH` because the main transmission channel is valuation-duration and potentially funding conditions, not a verified near-term floating-rate debt burden.

RED: escalate to `REDUCE_CANDIDATE_REVIEW` only if higher JGB/discount rates coincide with confirmed runway or financing stress, weaker pipeline evidence, or a broad high-duration biotech selloff.

No automatic BUY/SELL. Missing debt/runway evidence remains UNKNOWN. Issue #79 untouched.
