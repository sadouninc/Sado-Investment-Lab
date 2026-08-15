# W33 Re-entry Watch v0.1 — BOJ RED first live case

As of: 2026-08-15  
Contract: #568 v0.1 (frozen)  
Event log: #590  
Execution / position authority: #564

## Macro state
`BOJ = RED` / `Re-entry observation = ACTIVE`

Price decline alone is not a buy signal. While macro risk continues to worsen, names remain capped at WATCH / BUY WATCH. `RE-ENTRY READY` requires the #568 risk-stabilization gate.

## Fixed exit anchors
| Code | Name | Exit date | Exit price | Qty | Benchmark | Initial integrity | Initial state |
|---|---|---|---:|---:|---|---|---|
| 6702 | 富士通 | 2026-08-12 | 3,715 | 100 | TOPIX | REVIEW | WATCH |
| 4588 | オンコリスバイオファーマ | 2026-08-13 | 3,150 | 100 | Growth250 | REVIEW | WATCH |
| 5801 | 古河電気工業 | 2026-08-13 | 4,180 | 100 | TOPIX | REVIEW | WATCH |
| 3778 | さくらインターネット | 2026-08-14 | 3,800 | 100 | Growth250 | REVIEW | WATCH |
| 6376 | 日機装 | 2026-08-14 | 3,875.5 (PTS) | 100 | TOPIX | PASS | WATCH |

Benchmarks are fixed for this event; do not switch after observing outcomes.

## First priority candidate — 日機装 6376
Fundamental Integrity is pre-registered as `PASS`, with Fundamental Strength `25/25` under #568 v0.1.

Primary evidence already captured in #404 from FY2026 Q2 materials:
- H1 orders: +26.9% YoY
- H1 revenue: +18.0%
- H1 operating profit: +53.8%
- FY operating-profit guidance: ¥16.5bn → ¥19.7bn
- annual dividend: ¥50 → ¥60
- core thesis: STRENGTHENING

Counter-evidence is retained:
- precision-equipment orders remain slightly below prior year
- 3D Sinter product/technology is confirmed, but customer adoption / order / profit conversion remains unconfirmed

Therefore the company is **not** automatically BUY WATCH. Price relative decline, valuation reset, and risk stabilization remain unfilled gates.

## Observation schedule
For each exit:
1. first Japanese trading close after BOJ RED
2. 5 trading days after exit/event anchor
3. 10 trading days
4. 20 trading days

Record on same-source/same-close basis:
- stock return
- benchmark return
- excess return
- low since exit / avoided drawdown
- high since exit / false-exit opportunity cost
- valuation reset if forward PER is verifiable
- risk stabilization inputs (2Y JGB / 5Y JGB / USDJPY / OIS / bad-news equity response)

## Next macro checkpoints
- 2026-08-21: national CPI
- 2026-08-27: BOJ Deputy Governor Himino speech / meeting

## Fail-closed
- Missing forward PER = UNKNOWN, not 0.
- Missing same-basis benchmark price = UNKNOWN.
- Company-specific negative evidence can downgrade Integrity before price scoring.
- Do not alter #568 v0.1 thresholds until the prospective event is closed and backtested.
