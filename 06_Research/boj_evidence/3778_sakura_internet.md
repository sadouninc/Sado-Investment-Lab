# 3778 さくらインターネット — BOJ Sensitivity Evidence

担当: 🌅アサヒ  
種別: Research / Policy Intelligence  
Issue: #512  
Evidence date: 2026-08-13

## Canonical position
- Position: 信用買い100株
- Authority: root `Current_Status.md` / SBI VERIFIED snapshot

## Primary evidence
Source: 2027年3月期 第1四半期決算短信（2026-07-28, company IR）

- Q1売上高: 11,134百万円（前年同期比 +48.6%）
- Q1営業利益: 1,230百万円（前年同期は営業損失457百万円）
- Q1経常利益: 1,258百万円
- Q1純利益: 855百万円
- 総資産: 87,546百万円
- 純資産: 30,989百万円
- 自己資本比率: 35.1%
- 現金及び預金: 17,271百万円
- 短期借入金: 14,742百万円
- 1年内返済予定長期借入金: 4,242百万円
- 長期借入金: 5,067百万円
- リース債務: 13,520百万円
- 会社説明では、石狩データセンターのインフラ増強に備えた借入金・リース債務増加が負債増の主因。
- GPUインフラストラクチャー売上は4,718百万円、前年同期比 +245.9%。

## Sensitivity assessment
```yaml
rate_sensitivity: HIGH
yen_sensitivity: MIXED
energy_input_sensitivity: HIGH
valuation_duration: HIGH
balance_sheet_rate_risk: HIGH
boj_orange_action: WATCH
boj_red_action: REDUCE_CANDIDATE_REVIEW
confidence: HIGH
```

## Rationale
### Rate / balance sheet
短期借入金147.42億円、1年内返済予定長期借入金42.43億円、長期借入金50.67億円に加え、リース債務135.21億円を抱える。GPU・データセンター増強で資本集約度が高く、追加利上げは借換・新規調達コスト上昇を通じて影響しやすい。

### Valuation duration
AI/GPUインフラの高成長期待が株価評価の重要要素であり、金利上昇による将来キャッシュフローの割引率上昇の影響を受けやすい。

### Energy
データセンター/GPUは電力多消費型。BOJ利上げと同時にエネルギー高が続く場合、金融コストと運営コストの二重圧力になり得る。

### Yen
GPU調達等の輸入コストには円高が追い風になり得る一方、為替影響の純方向はIRだけでは単純化できないため `MIXED`。

## BOJ Early Warning implication
ORANGEでは即売却ではなく `WATCH`。ただし、BOJがREDへ進み、JGB上昇・グロース株valuation圧縮・エネルギー高が同時発生した場合は、保有ロングの中でも上位の `REDUCE_CANDIDATE_REVIEW` 対象。

BUY/SELL自動生成なし。Issue #79 untouched。
