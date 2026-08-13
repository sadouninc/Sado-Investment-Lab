# BOJ Early Warning — Portfolio Heatmap

担当: 🌅アサヒ  
種別: Research / Policy Intelligence  
Issue: #512  
Date: 2026-08-13

## Authority
- Portfolio authority: root `Current_Status.md`
- Snapshot: `as_of: 2026-08-08`
- Verification: `sbi_verified_position_snapshot / VERIFIED`
- BOJ research state: `ORANGE`

This file is a review queue, not a trade instruction. BUY/SELL is never auto-generated. Missing evidence remains `UNKNOWN` and is not inferred from sector stereotypes.

## Operational tiers

### Tier A — BOJ RED時の優先退避レビュー
These names already have company-specific evidence indicating high direct rate / funding / valuation sensitivity.

| Holding | Position | Rate | Valuation duration | Balance-sheet rate risk | ORANGE | RED review | Evidence status |
|---|---|---:|---:|---:|---|---|---|
| さくらインターネット | margin LONG 100 | HIGH | HIGH | HIGH | WATCH | REDUCE_CANDIDATE_REVIEW | VERIFIED |
| Aiロボティクス | cash LONG 300 | HIGH | HIGH | HIGH | WATCH | REDUCE_CANDIDATE_REVIEW | VERIFIED |
| GENDA | cash LONG 100 | HIGH | HIGH candidate | HIGH | WATCH | REDUCE_CANDIDATE_REVIEW | VERIFIED/PARTIAL |
| ispace | cash LONG 100 | MEDIUM | HIGH | MEDIUM | WATCH | REDUCE_CANDIDATE_REVIEW | VERIFIED |

### Tier B — valuation/funding stress同時発生時に退避レビュー

| Holding | Position | Rate | Valuation duration | Balance-sheet rate risk | ORANGE | RED review | Evidence status |
|---|---|---:|---:|---:|---|---|---|
| オンコリスバイオファーマ | cash LONG 100 | UNKNOWN | HIGH | UNKNOWN | WATCH | CONDITIONAL_REDUCE_REVIEW | PARTIAL |
| サンバイオ | cash LONG 100 | UNKNOWN | HIGH | UNKNOWN | WATCH | CONDITIONAL_REDUCE_REVIEW | PARTIAL |
| フィックスターズ | margin LONG 100 | LOW | HIGH | LOW | WATCH | CONDITIONAL_REDUCE_REVIEW | VERIFIED |
| NTT | cash LONG 300 | MEDIUM_HIGH | LOW/MEDIUM candidate | UNKNOWN/PARTIAL | WATCH | REVIEW | PARTIAL |

### Separate lane — SHORT / hedge-like direction

| Holding | Position | BOJ transmission | ORANGE | RED review | Evidence status |
|---|---|---|---|---|---|
| 飯田グループHD | margin SHORT 100 | Housing/mortgage rate sensitivity HIGH; portfolio direction opposite LONG holdings | WATCH | SHORT_THESIS_REVIEW | PARTIAL |

Do not automatically increase the short position on BOJ RED.

## Unverified queue — do not rank until company evidence is checked

| Holding | Position | Current BOJ classification | Next primary evidence |
|---|---|---|---|
| NEXT FUNDS 日経225 ETF | cash LONG 5 | UNKNOWN / index exposure | index composition + existing Market Weather contract |
| 日東紡績 | margin LONG 900 | UNKNOWN | latest results / debt / overseas sales / energy input |
| 信越化学工業 | margin LONG 100 | UNKNOWN | latest results / cash-debt / FX / energy exposure |
| 積水化学工業 | margin LONG 100 | UNKNOWN | latest results / housing + capex + debt / FX |
| 古河電気工業 | margin LONG 100 | UNKNOWN | latest results / debt / copper-energy / FX |
| 日本ギア工業 | margin LONG 100 | UNKNOWN | latest results / balance sheet / domestic capex sensitivity |
| ダイヘン | margin LONG 100 | UNKNOWN | latest results / debt / FX / capex cycle |
| 富士通 | margin LONG 100 | UNKNOWN | latest results / net cash-debt / FX / valuation duration |
| 浜松ホトニクス | margin LONG 100 | UNKNOWN | latest results / capex / FX / valuation duration |
| 三菱重工業 | margin LONG 100 | UNKNOWN | latest results / debt / FX / government order duration |

## Current review order

1. `Tier A` names if BOJ state worsens ORANGE → RED.
2. `Tier B` only when BOJ RED overlaps with valuation compression / funding stress / sector selloff.
3. 飯田GHD SHORT is evaluated separately; do not apply LONG exit logic.
4. Unverified names stay `UNKNOWN` until primary company evidence is added.

## RED escalation guard
BOJ state itself is not promoted to RED by market-implied probability alone. RED normally requires primary BOJ evidence or an explicit existing Market Weather RED threshold, per #512 contract.

## Next evidence sprint
Priority for remaining UNKNOWNs:
1. 日東紡績 — largest canonical LONG size (900 shares) and energy/semiconductor-material exposure.
2. 信越化学工業 — semiconductor/material + FX/energy transmission.
3. 積水化学工業 — housing/rate + capex transmission.
4. 古河電気工業 — copper/energy/FX + capex cycle.
5. 富士通 / 浜松ホトニクス — valuation-duration check.
6. ダイヘン / 三菱重工 / 日本ギア — industrial/capex and balance-sheet evidence.
7. Nikkei 225 ETF — handled mainly through Market Weather / index-level shock contract.

Issue #79 untouched.
