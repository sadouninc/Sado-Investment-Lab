# 4063 信越化学工業 — BOJ Sensitivity Evidence

担当: 🌅アサヒ  
種別: Research / Policy Intelligence  
Issue: #512  
Evidence date: 2026-08-13

## Canonical position
- Position: 信用買い100株
- Authority: root `Current_Status.md` / SBI VERIFIED snapshot

## Primary evidence
Source: 2027年3月期 第1四半期決算短信（2026-07-24, company IR）

- Q1売上高: 662,424百万円（前年同期比 +5.4%）
- Q1営業利益: 173,798百万円（+4.2%）
- Q1経常利益: 192,129百万円（+5.8%）
- Q1純利益: 130,829百万円（+3.5%）
- 総資産: 5,762,953百万円
- 純資産: 4,744,783百万円
- 自己資本比率: 79.0%
- 現金及び預金: 1,654,261百万円
- 短期借入金: 23,999百万円
- 長期借入金: 236,368百万円
- 負債合計: 1,018,170百万円
- 電子材料事業はAI関連需要を背景に売上+16%、営業利益+23%。
- 生活環境基盤材料では中東情勢に起因する原料・エネルギー価格上昇を受け値上げを推進。
- 会社は業績変動要因として対米ドルを含む為替レートを明示。

## Sensitivity assessment
```yaml
rate_sensitivity: LOW
yen_sensitivity: MIXED
aenergy_input_sensitivity: MEDIUM
valuation_duration: MEDIUM_HIGH
balance_sheet_rate_risk: LOW
boj_orange_action: WATCH
boj_red_action: WATCH_OR_REDUCE_REVIEW_IF_VALUATION_FX_SHOCK
confidence: HIGH
```

## Rationale
### Rate / balance sheet
現金及び預金約1.65兆円に対し、短期・長期借入金合計は約2,604億円。自己資本比率79.0%で、ネットキャッシュ余力は極めて大きい。したがって直接的な借入金利上昇リスクは `LOW`。

### Valuation duration
電子材料・AIインフラ向け成長期待がある一方、既に高収益・高キャッシュ創出企業であり、赤字グロースほど将来利益依存ではない。よって `MEDIUM_HIGH`。

### Yen
会社自身が為替レートを重要な業績変動要因として明示。海外事業規模が大きく円高は円換算利益に逆風となり得る一方、輸入原料コスト面の恩恵もあるため一方向に断定せず `MIXED`。

### Energy
生活環境基盤材料で原料・エネルギー価格上昇を受け値上げを実施しており、エネルギー価格は利益変動要因。ただし値上げ力・多角化があるため `MEDIUM`。

## BOJ Early Warning implication
BOJ REDでも財務脆弱性から優先退避する銘柄ではない。警戒点は円高による海外利益換算、半導体/材料成長株のvaluation compression、エネルギー高との複合ショック。

BUY/SELL自動生成なし。Issue #79 untouched。
