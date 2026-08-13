# BOJ Early Warning — ispace Evidence Mapping

担当: 🌅アサヒ  
種別: Research / Policy Intelligence  
Date: 2026-08-13
Refs: #512

## Scope
Canonical holding: ispace（現物100株） from `Current_Status.md`.
This file evaluates BOJ-related portfolio sensitivity using company primary disclosures. It is not a trade instruction.

## Primary evidence
Source: ispace 2026年3月期 有価証券報告書（提出日 2026-06-25）

Verified FY2026 consolidated figures:
- Revenue: 3,307百万円
- Ordinary loss: 8,142百万円
- Net loss attributable to owners of parent: 8,152百万円
- Total assets: 47,705百万円
- Net assets: 15,173百万円
- Equity ratio: 31.58%
- Cash and cash equivalents at period end: 29,691百万円
- Cash flow from financing activities: 31,448百万円

The filing also shows repeated external financing activity and past loan disclosures. The company remains loss-making while continuing mission/development investment.

## BOJ sensitivity classification
- `rate_sensitivity`: **MEDIUM**
  - Direct near-term interest burden is not judged HIGH from the available evidence because cash holdings are substantial versus current operating scale.
  - However, higher domestic funding costs can matter because the business remains loss-making and capital-intensive.

- `yen_sensitivity`: **MIXED**
  - The group operates in Japan, the U.S. and Europe, and past disclosures include FX gains/losses. A simple exporter/importer label is not appropriate.

- `energy_input_sensitivity`: **LOW / UNKNOWN**
  - No evidence found that energy input cost is a primary earnings driver. Keep conservative because launch/procurement contracts may embed energy-linked costs indirectly.

- `valuation_duration`: **HIGH**
  - Current value depends materially on future mission success and commercialization rather than current profits; FY2026 remained deeply loss-making.

- `balance_sheet_rate_risk`: **MEDIUM**
  - Cash is high, but continued financing needs and capital intensity make future funding conditions relevant.

- `funding_dependency` (research note, non-contract field): **HIGH**
  - Financing cash flow of 31,448百万円 was large relative to operating scale, while losses continued.

## Portfolio action projection
Current BOJ state: `ORANGE`

Recommended contract output for ispace:
- `boj_risk_action`: **WATCH**
- escalation candidate: **REDUCE_CANDIDATE review** only if BOJ state becomes RED and/or funding/liquidity/company-event risk deteriorates concurrently.
- `confidence`: **MEDIUM-HIGH** for valuation/funding sensitivity; **LOW-MEDIUM** for yen/energy sensitivity.

## Why this matters
For ispace, the main BOJ transmission channel is not simply existing floating-rate debt. It is the combination of:
1. discount-rate pressure on a long-duration growth equity,
2. potentially less favorable future equity/debt funding conditions,
3. continued capital requirements before stable profitability.

Therefore a BOJ tightening shock can pressure the equity valuation even when immediate interest expense is not the dominant cost item.

## Next checkpoint
- Review latest financing / borrowing disclosures after 2026-06-25.
- Check whether new mission contracts materially improve customer advances or reduce funding dependency.
- Reassess after next earnings release.

Issue #79 untouched.
