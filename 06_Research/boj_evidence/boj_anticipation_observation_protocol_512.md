# BOJ Anticipation — Prospective Observation Protocol

担当: 🌅アサヒ  
種別: Research / Policy Intelligence / Market Reaction  
Issue: #512

## Purpose
PoCで確認したexcess-return計測を、2026年9月BOJ会合までのprospective observationへ移行する。後知恵で都合のよい期間を選ばず、観測ルールを事前固定する。

## Observation unit
各fresh transactionで同一営業日basisの以下を保存する。
- BOJ Early Warning state
- policy pricing
- 2年 / 5年JGB
- USDJPY
- stock close / volume
- benchmark close / return
- stock return
- excess return
- drawdown from observation-window high
- company / sector confound
- evidence timestamp / source

## Prospective windows
### A. Stage-transition window
Yellow→Orange、Orange→Red等の状態遷移日をanchorとして、T-5 / T0 / T+1 / T+3 / T+5を保存する。

### B. Pricing-transition window
市場織込みが明確に段階上昇した時点をanchorとして保存する。単一報道値を連続seriesと誤認しない。

### C. Rolling observation
危機stage継続中は営業日ごとに相対returnをappendし、単日ノイズと継続劣後を区別する。

## Escalation logic
単独条件ではMarket Reaction HIGHへ上げない。以下の複数同時成立を重視する。
1. BOJ state / pricingが悪化
2. JGB上昇または円高が整合
3. benchmark比で2営業日以上継続劣後
4. 出来高増加またはdrawdown拡大
5. 決算・IR・M&A・sector shockで十分説明できない

## Academic guardrails
- 期間を株価結果を見た後で変更しない
- 負けたwindowだけを選ばない
- 1 eventで恒久分類しない
- benchmark変更は事前理由を記録
- missing dataはUNKNOWN
- 相関を因果と断定しない
- BUY / SELL自動生成なし

## Current phase
`POC_COMPLETE → PROSPECTIVE_OBSERVATION_ACTIVE`

8/7→8/10は方法検証用PoC。今後の主学習対象は、観測ルール固定後に実際のBOJ危機stage / pricing transitionが発生したwindowとする。

Issue #79 untouched.
