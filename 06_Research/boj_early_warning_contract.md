# BOJ Early Warning Contract

担当: 🌅アサヒ  
種別: Policy Intelligence / Product Contract  
Issue: #512

## Purpose
日銀追加利上げを発表後ではなく、市場が本格的に織り込む前に検知し、既存のMarket Weather / Intraday Meaningful Delta / Morning Portfolio Checkへread-onlyで接続する。

売買は自動化しない。最終判断はOwner Authority。

## Signal states

### GREEN
追加利上げの近接性を示す一次Evidenceが弱く、市場織込みにも顕著な加速がない。

### YELLOW
利上げ方向のEvidenceが増加しているが、次回または次々回会合での実施を強く示すには不足。

### ORANGE
複数の独立センサーが同方向へ進み、次回または次々回会合での利上げが現実的となり、株式市場の事前調整リスクが高まった状態。

候補センサー:
- BOJ発言のhawkish breadth拡大
- CPI/PPI/賃金/サービス価格の上振れ
- 2年/5年JGB、OISの利上げ織込み加速
- 円安またはenergy shockによる物価圧力
- 銀行優位と高duration株劣後など株式内部の金利反応

単一のmarket-implied probabilityだけではREDにしない。

### RED
原則、次の一次Evidenceのいずれかを要求する。
1. 総裁・副総裁・複数審議委員が近い会合での追加利上げを強く示唆
2. Summary of Opinions / Outlook / Statementで追加利上げの近接性が明確化
3. 実際の政策決定
4. 例外として既存Market Weatherの明示的RED threshold発火

## Portfolio projection

各Canonical holdingへ以下を付与する。
- `position_side`: LONG / SHORT
- `rate_sensitivity`: LOW / MEDIUM / HIGH / UNKNOWN
- `yen_sensitivity`: BENEFIT / NEUTRAL / HEADWIND / MIXED / UNKNOWN
- `energy_input_sensitivity`: LOW / MEDIUM / HIGH / UNKNOWN
- `valuation_duration`: LOW / MEDIUM / HIGH / UNKNOWN
- `balance_sheet_rate_risk`: LOW / MEDIUM / HIGH / UNKNOWN
- `boj_risk_action`: HOLD / WATCH / REDUCE_CANDIDATE / EXIT_REVIEW
- `evidence_refs`
- `confidence`

業種名だけでは分類しない。会社IR・財務・海外売上・借入・valuation・既存Company Researchを根拠にし、不明はUNKNOWNとする。

## State → action
- GREEN: BOJ要因のみではaction変更なし
- YELLOW: monitoring強化。原則action変更なし
- ORANGE: HIGH sensitivityのLONGをWATCH。既存の弱いMarket Phase / event riskが重なる場合のみREDUCE_CANDIDATEレビュー
- RED: HIGH sensitivityのLONGをREDUCE_CANDIDATEレビュー。thesis invalidation / liquidity / leverage riskが重なる場合のみEXIT_REVIEW
- SHORTは方向を反転して評価し、機械的な退避対象にしない

## Fail-closed rules
- Current holdingsはCanonical portfolio SSoTから取得し、chat memoryから推測しない
- missing company evidenceはUNKNOWN
- probability-only REDは禁止
- BUY/SELLを自動生成しない
- #444と重複するmarket collectorを新設しない
- Issue #79 untouched

## Test scenarios
1. 市場利上げ確率のみ急上昇 → 最大ORANGE
2. 市場確率上昇 + BOJ一次Evidenceで近接性明確化 → RED候補
3. company evidence欠損 → sensitivity UNKNOWN、EXIT_REVIEW禁止
4. SHORT position → LONGと同じactionへ自動投影しない
