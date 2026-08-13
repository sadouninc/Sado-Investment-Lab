# 3687 フィックスターズ — BOJ Sensitivity Evidence

担当: 🌅アサヒ  
種別: Research / Policy Intelligence  
Issue: #512  
Evidence date: 2026-08-13

## Canonical position
- Position: 信用買い100株
- Authority: root `Current_Status.md` / SBI VERIFIED snapshot

## Primary evidence
Source: 2026年9月期 第2四半期（中間期）決算短信（2026-05-14, company IR）

- 中間売上高: 5,442百万円（前年同期比 +13.8%）
- 営業利益: 1,635百万円（+8.8%）
- 経常利益: 1,641百万円（+9.5%）
- 中間純利益: 964百万円
- 総資産: 10,456百万円
- 純資産: 8,959百万円
- 自己資本比率: 83.7%
- 現金及び預金: 5,085百万円
- 負債合計: 1,496百万円
- 営業CF: +822百万円
- 投資CF: -255百万円
- 財務CF: -691百万円（主因は配当金支払）
- Solution事業は売上5,049百万円、営業利益1,932百万円。
- SaaS事業は売上393百万円、営業損失295百万円で将来収益獲得に向け投資継続。

## Sensitivity assessment
```yaml
rate_sensitivity: LOW
yen_sensitivity: MIXED
energy_input_sensitivity: LOW
valuation_duration: HIGH
balance_sheet_rate_risk: LOW
boj_orange_action: WATCH
boj_red_action: WATCH_OR_REDUCE_REVIEW_IF_VALUATION_SHOCK
confidence: HIGH
```

## Rationale
### Rate / balance sheet
自己資本比率83.7%、現金約50.9億円、負債合計約15.0億円で、借入依存による直接的な金利上昇耐性は比較的高い。財務CFも借入増加ではなく主に配当支払いでマイナス。

### Valuation duration
一方、AI・量子・高速化ソフトウェアなど将来成長期待の比重が高く、株式valuationは金利上昇によるdiscount-rate圧力を受けやすい。このため企業財務の金利耐性は高いが、株価の金利感応度は別途警戒する。

### Yen / energy
米国子会社はあるが、売上・コストの為替純感応度を今回の一次資料だけで一方向に断定できないため `MIXED`。データセンター運営会社ではなく、人材・ソフトウェア中心の事業構成のためenergy input sensitivityはLOWと評価。

## BOJ Early Warning implication
BOJ ORANGEでは `WATCH`。REDでも財務悪化を理由に優先退避する銘柄ではないが、高PERグロース全体のvaluation compressionが強い場合は `REDUCE_CANDIDATE_REVIEW` へ昇格し得る。

BUY/SELL自動生成なし。Issue #79 untouched。
