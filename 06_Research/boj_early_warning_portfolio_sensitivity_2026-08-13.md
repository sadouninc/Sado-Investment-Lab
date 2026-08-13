# BOJ Early Warning — Portfolio Sensitivity Inventory

担当: 🌅アサヒ  
種別: Research / Policy Intelligence  
Date: 2026-08-13

## Authority
Current holdings source: root `Current_Status.md`, `as_of: 2026-08-08`, authority `sbi_verified_position_snapshot`, verification `VERIFIED`.

This is a research inventory, not a trade instruction. Unknown company-specific evidence remains `UNKNOWN`; do not infer sensitivity from sector name alone.

## BOJ state
Current research state: **ORANGE**.

Evidence snapshot:
- July PPI +7.2% YoY; yen-based import prices +29.1% YoY.
- Market-implied September hike probability reported around 76% on 2026-08-13.
- BOJ July Summary of Opinions showed discussion of faster normalization.
- Next MPM: 2026-09-17/18.

Market probability alone does not promote state to RED. RED requires primary BOJ evidence or an existing explicit Market Weather RED threshold.

## Canonical holdings inventory — first-pass sensitivity queue

| Holding | Position | Rate | Yen | Energy | Valuation duration | Balance-sheet rate risk | ORANGE action | Confidence / next evidence |
|---|---|---|---|---|---|---|---|---|
| NEXT FUNDS Nikkei 225 ETF | cash 5 | MEDIUM | MIXED | MEDIUM | MEDIUM | LOW | WATCH | medium; index exposure |
| Ai Robotics | cash 300 | UNKNOWN | UNKNOWN | UNKNOWN | HIGH candidate | UNKNOWN | WATCH | low; verify valuation/debt/overseas mix |
| Nittobo | margin long 900 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | WATCH | low; verify IR financials/export mix |
| Iida Group HD | margin short 100 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | WATCH | low; short position means impact direction differs; verify housing-rate sensitivity |
| Fixstars | margin long 100 | UNKNOWN | UNKNOWN | UNKNOWN | HIGH candidate | UNKNOWN | WATCH | low; verify valuation/debt |
| Sakura Internet | margin long 100 | UNKNOWN | UNKNOWN | HIGH candidate | HIGH candidate | UNKNOWN | WATCH | low; verify DC power cost/capex/debt |
| Shin-Etsu Chemical | margin long 100 | UNKNOWN | UNKNOWN | HIGH candidate | UNKNOWN | UNKNOWN | WATCH | low; verify overseas sales/energy/feedstock/debt |
| Sekisui Chemical | margin long 100 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | WATCH | low; verify housing/overseas/energy mix |
| Oncolys BioPharma | cash 100 | UNKNOWN | UNKNOWN | LOW candidate | HIGH candidate | UNKNOWN | WATCH | low; verify cash runway/financing risk |
| SanBio | cash 100 | UNKNOWN | UNKNOWN | LOW candidate | HIGH candidate | UNKNOWN | WATCH | low; verify cash runway/financing risk |
| Furukawa Electric | margin long 100 | UNKNOWN | UNKNOWN | HIGH candidate | UNKNOWN | UNKNOWN | WATCH | low; verify raw material/FX/debt |
| Nippon Gear | margin long 100 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | WATCH | low; verify IR |
| Daihen | margin long 100 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | WATCH | low; verify export/debt/energy mix |
| Fujitsu | margin long 100 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | WATCH | low; verify overseas mix/net cash/valuation |
| Hamamatsu Photonics | margin long 100 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | WATCH | low; verify overseas sales/valuation |
| Mitsubishi Heavy Industries | margin long 100 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | WATCH | low; verify debt/FX/order profile |
| GENDA | cash 100 | UNKNOWN | UNKNOWN | UNKNOWN | HIGH candidate | UNKNOWN | WATCH | low; verify leverage/acquisition financing |
| ispace | cash 100 | UNKNOWN | UNKNOWN | LOW candidate | HIGH candidate | HIGH candidate | WATCH | low; verify cash runway/financing |
| NTT | cash 300 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | WATCH | low; verify debt duration/rate exposure |

`candidate` means a research priority only, not a verified classification.

## Evidence priority
Before any `REDUCE_CANDIDATE` projection, verify company evidence in this order:
1. Margin-long + high valuation-duration candidates: Sakura Internet, Fixstars, Ai Robotics, ispace, biotech holdings.
2. Balance-sheet / financing candidates: ispace, GENDA, NTT, Sakura Internet, biotech holdings.
3. Energy / import-cost candidates: Shin-Etsu, Furukawa Electric, Sakura Internet.
4. Yen sensitivity: export-heavy holdings and overseas-revenue mix using company IR.
5. Iida Group HD must be evaluated separately because the canonical position is short.

## Fail-closed rules
- No company moves to `REDUCE_CANDIDATE` from sector intuition alone.
- `UNKNOWN` stays UNKNOWN until company IR / canonical research provides evidence.
- Margin position is a risk amplifier but is not itself proof of BOJ sensitivity.
- BOJ ORANGE alone means WATCH; RED or overlapping Market Phase/event risk is required for stronger review.

## Next checkpoint
Populate verified evidence for the first priority group and emit a machine-readable sensitivity mapping suitable for Issue #512 / Morning Portfolio Check read-only projection.

Issue #79 untouched.
