# BOJ Sensitivity — final five screen

担当: 🌅アサヒ  
Issue: #512
Evidence date: 2026-08-13

対象: 古河電工 / 富士通 / ダイヘン / 三菱重工 / 日本ギア工業

## Rules
- 一次IRで確認できない固定/変動金利比率等は UNKNOWN。
- BOJ RED単独でSELLを自動生成しない。
- 金利、円、valuation、energy、position sizeを分離する。

## 6622 ダイヘン
Primary: 2026-05-11 2026年3月期決算短信。
- 2027/3会社予想: 売上280,000百万円、営業利益25,000百万円。
- 2026年度想定為替: 157円/USD。
- 会社は中東情勢による原材料価格高騰をリスクとして明示。
- AI/DC半導体投資、再エネ・蓄電池、省人化需要を成長要因として明示。

```yaml
rate_sensitivity: MEDIUM
yen_sensitivity: MEDIUM_HIGH
energy_input_sensitivity: MEDIUM
valuation_duration: MEDIUM
balance_sheet_rate_risk: UNKNOWN
boj_orange_action: WATCH
boj_red_action: REVIEW_IF_YEN_APPRECIATION_OR_RATE_STRESS
confidence: MEDIUM_HIGH
```

## 6702 富士通
Primary: company IR page, 2026年度Q1決算は2026-07-30公表済み。
- サービス/AI成長期待がvaluation経路を持つ。
- 直接的な金利感応度は最新Q1/有報の負債構造確認まで UNKNOWN。

```yaml
rate_sensitivity: UNKNOWN
yen_sensitivity: MIXED
energy_input_sensitivity: LOW_MEDIUM
valuation_duration: MEDIUM_HIGH
balance_sheet_rate_risk: UNKNOWN
boj_orange_action: WATCH
boj_red_action: REVIEW_IF_VALUATION_OR_YEN_SHOCK
confidence: MEDIUM
```

## 5801 古河電工
- AI/DC・光関連の成長期待からvaluation/景気循環経路を重視。
- 最新一次IRでの負債・為替感応度精査をNext Checkpointとし、未確認値はUNKNOWN。

```yaml
rate_sensitivity: UNKNOWN
yen_sensitivity: UNKNOWN
energy_input_sensitivity: MEDIUM
valuation_duration: HIGH
balance_sheet_rate_risk: UNKNOWN
boj_orange_action: WATCH
boj_red_action: REVIEW_IF_VALUATION_CYCLE_BREAKS
confidence: MEDIUM_LOW
```

## 7011 三菱重工
- 大型受注・長期プロジェクト企業。金利だけでなく円と資材価格を複合監視。
- 最新Q1/有報の負債構造確認をNext Checkpointとする。

```yaml
rate_sensitivity: MEDIUM
yen_sensitivity: MEDIUM_HIGH
energy_input_sensitivity: MEDIUM
valuation_duration: MEDIUM
balance_sheet_rate_risk: UNKNOWN
boj_orange_action: WATCH
boj_red_action: REVIEW_IF_YEN_OR_FINANCING_SHOCK
confidence: MEDIUM
```

## 6356 日本ギア工業
Primary: company IR calendar confirms 2027/3 Q1 announced 2026-07-31。
- 小型資本財・工事企業として国内設備投資/金利経路を監視。
- Q1財務数値の一次取得前はbalance-sheet評価をUNKNOWNとする。

```yaml
rate_sensitivity: MEDIUM
yen_sensitivity: LOW_MEDIUM
energy_input_sensitivity: LOW_MEDIUM
valuation_duration: MEDIUM
balance_sheet_rate_risk: UNKNOWN
boj_orange_action: WATCH
boj_red_action: REVIEW_IF_DOMESTIC_CAPEX_WEAKENS
confidence: MEDIUM_LOW
```

## Next checkpoint
1. 古河電工Q1一次IR: cash/debt, FX assumptions/sensitivity。
2. 富士通Q1/有報: cash/debt, financing structure。
3. ダイヘンQ1: cash/debt and fixed/variable debt if disclosed。
4. 三菱重工Q1/有報: debt structure, FX sensitivity。
5. 日本ギアQ1短信: cash/debt and order trend。

このscreenはEvidence不足を明示した暫定Mapping。UNKNOWNを推測で埋めず、一次資料取得時に昇格する。