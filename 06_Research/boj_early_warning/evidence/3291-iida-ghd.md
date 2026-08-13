# 飯田グループホールディングス (3291) — BOJ sensitivity evidence mapping

Status: PARTIAL_VERIFIED (2026-08-13)
Issue: #512

## Assessment
- position_side: SHORT (Canonical Portfolio)
- company_rate_sensitivity: HIGH
- valuation_duration: LOW_MEDIUM
- balance_sheet_rate_risk: MEDIUM_HIGH (provisional)
- domestic_mortgage_demand_sensitivity: HIGH
- BOJ ORANGE portfolio action: WATCH; do not apply LONG reduction rule
- BOJ RED portfolio action: SHORT_THESIS_REVIEW / potential hedge-benefit, not REDUCE_CANDIDATE by default

## Evidence
会社は戸建分譲を中心とする住宅事業であり、国内住宅ローン金利上昇は購入者の支払能力・住宅需要・在庫回転に直接波及し得る。2026年3月期連結決算は2026-05-15に開示済み。

Company IR / disclosure should be used for final debt and inventory figures. Current mapping deliberately leaves exact debt sensitivity provisional until latest IFRS statements are extracted.

## Transmission path
BOJ hike -> mortgage rates up -> affordability down -> housing demand/inventory turnover pressure -> company earnings downside.

For this portfolio the position is SHORT, therefore the first-order equity-price effect can be beneficial. The engine must invert LONG-side portfolio action semantics.

## Guardrail
金利上昇=必ず株安とはしない。建築コスト、土地価格、政策支援、販売価格転嫁、需給、ショート固有の踏み上げリスクを同時確認する。BOJ RED時も機械的な売り増しは禁止。