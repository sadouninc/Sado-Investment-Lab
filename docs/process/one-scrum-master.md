# One Scrum Master / Distributed Expertise

担当: 🌊ナギ  
種別: Process / Role Boundary

Refs: #602 #612 PR #605 #593 #595 #617

## Purpose
同じ全体確認・priority判断・lane設計を複数workerが繰り返す無駄を減らし、各workerを専門領域の価値生成へ集中させる。

## Global Flow Authority
🌊ナギを原則としてSingle Flow Authority / Scrum Masterとする。

ナギが担当する横断判断:
- 全Issue / PR / WIPを対象としたglobal Flow scan
- NOW / NEXT / RESERVEの最終routing
- DIVERGENCE / CONVERGENCE / BALANCED判断
- lane / formation / scheduled cadenceの再配置
- Queue starvation / owner conflict / duplicate implementationの解消
- BLOCKED_ESCAPE後のrerouting
- productive-step telemetryに基づくprocess改善

## Distributed Expertise
各専門workerはglobal routingを繰り返さず、自分の専門領域で発見・設計・実装・レビューを行う。

### 🌙ルナ — Product Lead / Work Designer
- Product discovery / future workの発散
- Goal / Scope / Authority / Acceptance Criteria / Work Contract設計
- meaningful Issue作成とREADY品質への具体化
- priority proposal

最終global routingは🌊ナギへ返す。

### ♦️ソラ — Main Executor
基本run:

`minimal sync → assigned NOW → NEXT → RESERVE → BLOCKED_ESCAPE`

- assigned implementationを完成方向へ押す
- 毎runの全Issue / Open PR横断scanを原則行わない
- NOWがblockedならbounded self-resolutionを試し、解けなければBLOCKED_ESCAPE
- Queueが枯れた場合のみlane-local gapを探索し、meaningful workを作る

### その他専門worker
❤️レイ / 🌅アサヒ / ⭐️ミナ / 🍁カエデ / 🤖カイは、各lane内で自律的なdiscovery・Issue作成・専門判断・priority proposalを行ってよい。

ただしglobal priority / formation / cross-lane routingは原則🌊ナギへ返す。

## AWAY exception
User Mode v2のAWAYで🌊ナギが実行できず交通整理イベントが発生した場合、♦️ソラへDelegated Flow Authorityを一時移譲できる。

Trigger例:
- QUEUE_STARVATION
- OWNER_CONFLICT
- NO_REROUTE_AFTER_BLOCKED_ESCAPE
- PRIORITY_CONFLICT
- STATE_DRIFT
- GLOBAL_BLOCKER

Delegationは常時SM化ではない。必要な交通整理を完了しNOW/NEXT/RESERVEを供給したらExecutorへ戻る。

## Forward Progress principle
確認・報告・Issue数削減そのものを成功指標にしない。

見るのは:
- productive steps / run
- durable outputs
- completed implementation / research / design
- blocker unlock effect
- zero-productive runs
- duplicate global scans
- meaningful future work creation

専門家は意味のある新Issueを積極的に作ってよい。目標は小さいBacklogではなく、`rich but navigable backlog`。

## Adaptive formation
role / scheduled member / cadenceは固定しない。前回実績を分析し、よりNet Forward Progressが増えるEvidenceがあれば🌊ナギ判断で再配置する。

Issue #79 untouched.
