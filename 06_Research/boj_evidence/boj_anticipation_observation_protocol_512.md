# BOJ Anticipation — Prospective Observation Protocol

担当: 🌅アサヒ  
種別: Research / Policy Intelligence / Market Reaction  
Issue: #512

## Purpose
PoCで確認したexcess-return計測を、2026年9月BOJ会合までのprospective observationへ移行する。後知恵で都合のよい期間を選ばず、観測ルールを事前固定する。

## Observation unit
各fresh transactionで同一営業日basisの以下を保存する。
- BOJ Early Warning state: GREEN / YELLOW / ORANGE / RED
- policy pricing: 利上げ確率または取得可能な市場織込み
- 2年 / 5年JGB
- USDJPY
- stock close / volume
- benchmark close / return
- stock return
- excess return = stock return - benchmark return
- drawdown from observation-window high
- company / sector confound
- evidence timestamp / source

## Benchmarks
- 247A Aiロボティクス: Growth250
- 9166 GENDA: Growth250
- 3110 日東紡: TOPIX
- 4063 信越化学: TOPIX
- 3778 さくらインターネット: TOPIXをprimary、growth/theme cross-checkをsecondary

## Prospective windows
### A. Stage-transition window
Yellow→Orange、Orange→Red等の状態遷移日をanchorとして、T-5 / T0 / T+1 / T+3 / T+5を保存する。

### B. Pricing-transition window
市場織込みが明確に段階上昇した時点をanchorとして保存する。固定閾値はsource品質に応じて使用し、単一報道値を連続seriesと誤認しない。

### C. Rolling observation
危機stage継続中は営業日ごとに相対returnをappendし、単日ノイズと継続劣後を区別する。

## Escalation logic
単独条件ではMarket Reaction HIGHへ上げない。以下の複数同時成立を重視する。
1. BOJ state / pricingが悪化
2. JGB上昇または円高が整合
3. benchmark比で2営業日以上継続劣後
4. 出来高増加またはdrawdown拡大
5. 決算・IR・M&A・sector shockで十分説明できない

## Confound policy
- 決算前後は EARNINGS_CONFOUND
- 増資 / M&A / 大型受注 / regulatory event等は COMPANY_CONFOUND
- 半導体全面安等は SECTOR_CONFOUND
- confoundが強いwindowはBOJ betaの学習サンプルから除外または低weight

## Academic guardrails
- 期間を株価結果を見た後で変更しない
- 負けたwindowだけを選ばない
- 1 eventで恒久分類しない
- benchmark変更は事前理由を記録
- missing dataはUNKNOWN。補間で警報を作らない
- 相関を因果と断定しない
- BUY / SELL自動生成なし

## Learning output
複数event蓄積後、銘柄ごとに以下を更新する。
- fundamental_rate_sensitivity
- boj_event_beta
- boj_anticipation_beta
- market_reaction_sensitivity
- context_sensitivity
- sample_count / confounded_sample_count
- confidence

## Current phase
`POC_COMPLETE → PROSPECTIVE_OBSERVATION_ACTIVE`

8/7→8/10は方法検証用PoC。今後の主学習対象は、観測ルール固定後に実際のBOJ危機stage / pricing transitionが発生したwindowとする。

Issue #79 untouched.
