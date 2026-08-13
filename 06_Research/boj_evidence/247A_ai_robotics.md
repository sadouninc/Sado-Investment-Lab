# 247A Aiロボティクス — BOJ Sensitivity Evidence

担当: 🌅アサヒ  
種別: Research / Policy Intelligence  
Issue: #512  
Evidence date: 2026-08-13

## Canonical position
- Position: 現物300株
- Authority: root `Current_Status.md` / SBI VERIFIED snapshot

## Primary evidence
### 2026年3月期 決算短信（2026-05-13）
- 売上高: 29,359百万円（前年比 +106.7%）
- 営業利益: 3,802百万円（+53.3%）
- 経常利益: 3,780百万円（+56.0%）
- 当期純利益: 2,654百万円（+55.9%）
- 総資産: 18,431百万円
- 純資産: 6,049百万円
- 自己資本比率: 32.8%
- 現金及び現金同等物: 3,987百万円
- 営業CF: -5,880百万円
- 財務CF: +6,417百万円
- 期末負債合計: 12,381百万円
- 有利子負債は前期末から6,333百万円増加。
- 財務CFでは短期借入金純増3,500百万円、長期借入収入3,900百万円。

### BJC株式取得・資金借入（2026-03-27）
- BJC取得価額: 25,550百万円
- 株式取得資金としてみずほ銀行から25,550百万円を借入。
- 借入期間: 6か月のブリッジファイナンス。
- 借入金利: 基準金利＋スプレッド。
- パーマネント化を含む最適な資金調達手段について金融機関と協議すると開示。

### 資金借入・コミットメントライン（2026-01-16）
- 長期借入契約: 合計1,300百万円。
- コミットメントライン極度額: 1,000百万円。
- 金利はいずれも基準金利＋スプレッド。

### 短期資金借入（2026-06-25）
- りそな銀行から2,000百万円の短期借入。
- 借入実行予定: 2026-06-29。
- 返済期日: 2026-10-01。
- 支払金利: 基準金利＋スプレッド。
- 用途: 運転資金。

## Sensitivity assessment
```yaml
rate_sensitivity: HIGH
yen_sensitivity: MIXED
energy_input_sensitivity: MEDIUM
valuation_duration: HIGH
balance_sheet_rate_risk: HIGH
boj_orange_action: WATCH
boj_red_action: REDUCE_CANDIDATE_REVIEW
confidence: HIGH
```

## Rationale
### Rate / balance sheet
2026年3月期末時点で有利子負債が大きく増加し、営業CFは大幅マイナス、財務CFは借入中心に大幅プラス。さらにBJC取得のため255.5億円のブリッジ借入を実行し、その後も20億円の短期借入を追加している。複数借入で金利が「基準金利＋スプレッド」とされており、BOJ追加利上げは借換・パーマネント化・追加運転資金の調達条件に直接波及しやすい。

### Valuation duration
会社は2029年3月期に売上高2,200億円・営業利益400億円・時価総額1兆円という高い成長目標を掲げており、将来成長期待の現在価値が株価評価の重要部分を占める。金利上昇局面ではdiscount-rate上昇によるvaluation compressionにも注意が必要。

### Working capital / growth funding
売上高は急成長している一方、売上債権・棚卸資産増加により営業CFはマイナス。成長継続には運転資金需要が大きく、資金調達コスト上昇の影響を受けやすい。

### Yen / energy
化粧品・美容家電では海外調達・輸入部材等の影響があり得る一方、現一次資料だけで純為替感応度を一方向に断定できないため `MIXED`。データセンター運営ほど電力直接感応度は高くないためenergyは `MEDIUM` とする。

## BOJ Early Warning implication
ORANGEでは即売却ではなく `WATCH`。ただしBOJがREDへ進み、短期金利・借換金利上昇、グロース株valuation compression、資金調達環境悪化が重なる場合は、保有ロングの中でも上位の `REDUCE_CANDIDATE_REVIEW` 対象。

BUY/SELL自動生成なし。Issue #79 untouched。
