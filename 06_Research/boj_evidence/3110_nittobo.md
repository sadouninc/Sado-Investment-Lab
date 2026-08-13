# 3110 日東紡績 — BOJ Sensitivity Evidence

担当: 🌅アサヒ  
種別: Research / Policy Intelligence  
Issue: #512  
Evidence date: 2026-08-13

## Canonical position
- Position: 信用買い900株
- Authority: root `Current_Status.md` / SBI VERIFIED snapshot

## Primary evidence
Source: 2027年3月期 第1四半期決算短信（2026-08-05, company IR / Drive archived copy）

- Q1売上高: 34,033百万円（前年同期比 +20.6%）
- Q1営業利益: 7,943百万円（+84.8%）
- Q1経常利益: 8,433百万円（+94.1%）
- Q1純利益: 5,797百万円（+84.2%）
- 総資産: 280,413百万円
- 純資産: 183,935百万円
- 自己資本比率: 63.2%
- 現金及び預金: 45,476百万円
- 短期借入金: 3,240百万円
- 1年内返済予定長期借入金: 7,744百万円
- 長期借入金: 27,021百万円
- 社債: 10,000百万円
- 電子材料事業ではAIサーバー向け需要拡大によりスペシャルガラス販売が増加。

Additional primary evidence: 中期経営計画（2024-2027年度）
- 4年累計設備投資: 約1,200億円
- ネットD/Eレシオ目標: 0.4倍以下
- 自己資本比率目標: 55%以上

## Sensitivity assessment
```yaml
rate_sensitivity: MEDIUM
yen_sensitivity: MIXED
energy_input_sensitivity: UNKNOWN
valuation_duration: HIGH
balance_sheet_rate_risk: LOW_MEDIUM
boj_orange_action: WATCH
boj_red_action: REDUCE_CANDIDATE_REVIEW_IF_VALUATION_OR_FUNDING_STRESS
confidence: HIGH_FOR_BALANCE_SHEET_MEDIUM_OVERALL
```

## Rationale
### Rate / balance sheet
期末現金約454.8億円に対し、短期借入・1年内長期借入・長期借入・社債の合計は約480.1億円。グロス有利子負債はあるものの、現金と自己資本比率63.2%がクッションとなるため、既存負債だけを理由に `HIGH` とはしない。

一方、中計で4年間約1,200億円の設備投資を計画しており、追加利上げは将来の投資採算・新規調達コストを通じて影響し得る。このためrate sensitivityは `MEDIUM`。

### Valuation duration
AIサーバー向けスペシャルガラスなど高成長期待が株価評価に占める比重が大きく、BOJ利上げ局面ではdiscount-rate上昇によるvaluation compressionを受けやすいと評価し `HIGH`。

### Yen / energy
海外需要・輸出の恩恵と輸入コスト等が混在するため為替は `MIXED`。energy sensitivityは今回の一次資料だけで定量化せず `UNKNOWN`。

## Portfolio implication
Canonical positionは900株で保有数量が大きいため、BOJ RED時のportfolio impactは高い。企業財務の脆弱性よりも、valuation compressionと大型成長投資の資本コスト上昇を重視してレビューする。

BUY/SELL自動生成なし。Issue #79 untouched。
