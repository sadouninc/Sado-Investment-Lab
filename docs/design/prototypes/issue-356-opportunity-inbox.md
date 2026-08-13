# #356 Opportunity Inbox — Visual Prototype Contract

担当: ⭐️ミナ  
種別: Product UI Design / Opportunity Discovery  
Status: IMPLEMENTATION_HANDOFF_READY  
Related: #356 / #170 / #108 / #113 / #320

## Goal
大量のSeedをOwnerへ直接見せず、昇格候補だけを「なぜ今見る価値があるか」で30秒以内に理解できるOwner-facing Opportunity Inboxへ整理する。

## Responsibility boundary
- Seed Inbox = 運用者向け未整理Signal
- Developing Signals = 継続観測中の兆候
- Opportunity Inbox = Researchへ昇格させる候補
- Company Research = 個社Fundamental解釈
- Cockpit = 投資判断文脈

Opportunity Inboxは第二Research truthを作らない。canonical Seed / Signal / Research Candidate projectionのみを読む。

## Owner first-view
1. 新しい投資機会候補 + freshness
2. Why now
3. Transmission path
4. Evidence / Counter-evidence
5. Next checkpoint
6. Status / downstream destination

## Card contract
1 candidate = 1 vertical card。

必須表示:
- title
- status: RESEARCH_CANDIDATE / OPPORTUNITY_CANDIDATE
- Why now 1〜2行
- Transmission summary
- Signal Lead / Evidence Quality / Counter-evidence を独立表示
- Next checkpoint
- source freshness

詳細へ:
- Novelty / Magnitude / Japan Equity Relevance / Expectation Gap
- Evidence refs
- Counter-evidence
- Seed lineage / related issue refs

## Mobile 390px
- 巨大比較tableは禁止。
- first viewport内に最低1候補の `Why now + status + next checkpoint` が見える。
- raw metricを先に並べず、日本語要約を主役にする。
- card内の軸は2列圧縮せず縦stack可。
- tap target >= 2.75rem相当。

## Semantic safety
- HIGH/MEDIUM/LOWは独立軸であり総合winner scoreではない。
- Expectation Gap = 株価上昇余地ではない。
- Evidence件数だけで昇格しない。
- Counter-evidenceを折り畳んで隠蔽しない。
- OPPORTUNITY_CANDIDATE = BUYではない。
- UNKNOWNをnegativeへ丸めない。

## Design Gate
### BLOCKER
- 全SeedをOwner first-viewへ大量表示
- opaque総合scoreだけで順位づけ
- OPPORTUNITY_CANDIDATEをBUY/SELLへ変換
- #170/#108/#113と第二truthを作る
- Counter-evidenceを非表示
- Home/CockpitへOpportunity内部workflowを複製
- page-specific第二CSS system

### SHOULD_FIX
- Why now / Next checkpointよりraw metricsが先
- freshnessがfirst-viewから遠い
- 390px horizontal overflow
- EvidenceとCounter-evidenceの視覚weightが極端に非対称

### NICE_TO_HAVE
- source sensor filter
- promotion timeline
- changed-since-last-review marker

Result: **PASS_WITH_NOTES — Pages implementation may proceed from canonical projection.**

Issue #79 untouched.
Broadcast checked through: comment_id=5277198470 — VERIFIED
TEAM_STATE User Mode: ACTIVE
