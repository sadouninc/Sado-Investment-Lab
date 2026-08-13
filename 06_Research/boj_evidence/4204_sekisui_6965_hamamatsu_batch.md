# BOJ Sensitivity Evidence — 積水化学 / 浜松ホトニクス

担当: 🌅アサヒ
Issue: #512
Evidence date: 2026-08-13

## 4204 積水化学工業
Primary evidence: 2026年3月期決算短信・2027年3月期会社計画（2026-04-28 company IR）

- 2027年3月期は売上14,084億円、営業利益1,150億円を計画。
- 全セグメント増収増益、営業利益は過去最高を目標。
- 高付加価値品拡販が成長ドライバー。

Assessment:
```yaml
rate_sensitivity: MEDIUM
yen_sensitivity: MIXED
energy_input_sensitivity: MEDIUM
valuation_duration: MEDIUM
balance_sheet_rate_risk: UNKNOWN
boj_orange_action: WATCH
boj_red_action: REVIEW_IF_JGB_YEN_DOMESTIC_DEMAND_SHOCK
confidence: MEDIUM
```

金利上昇の直接財務影響は有報の固定/変動構成確認までUNKNOWN。住宅・設備投資等の国内需要経路、円、原材料・エネルギーを複合センサーとして扱う。

## 6965 浜松ホトニクス
Primary evidence: 2026年9月期第2四半期決算短信・半期報告書（2026-05-14/15 company IR）

- 会社は継続的な物価上昇、中東地政学リスクによる原材料・エネルギー価格変動、不安定な物流を事業環境リスクとして明示。
- 光技術の研究・製品開発を継続し、市場環境変化への対応を進める。

Assessment:
```yaml
rate_sensitivity: LOW_MEDIUM
yen_sensitivity: MIXED
energy_input_sensitivity: MEDIUM
valuation_duration: MEDIUM_HIGH
balance_sheet_rate_risk: UNKNOWN
boj_orange_action: WATCH
boj_red_action: REVIEW_IF_VALUATION_YEN_SHOCK
confidence: MEDIUM
```

高成長技術期待によるvaluation経路を重視。直接金利負担は最新半期報告書の金融負債詳細確認までUNKNOWNのままfail-closed。

BUY/SELL自動生成なし。Issue #79 untouched。
