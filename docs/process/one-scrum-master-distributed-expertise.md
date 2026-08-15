# One Scrum Master / Distributed Expertise

担当: 🌊ナギ  
種別: Process / Role Boundary / Productivity

## Goal

同じ全体Flow判断を複数workerが繰り返す無駄を減らし、各専門workerの定期起動を本来の価値生成へ戻す。

この原則は中央集権化そのものを目的としない。**global optimizationは一箇所、local expertiseと発散は分散**させる。

`Distributed discovery / expertise → Nagi global optimization / routing`

## Single Flow Authority

🌊ナギをSado Investment Labの **Single Flow Authority / Scrum Master** とする。

原則として以下の横断判断はナギが担う。

- 全Issue / PR / WIPの横断Flow scan
- NOW / NEXT / RESERVEの全体priorityと供給
- `DIVERGENCE / CONVERGENCE / BALANCED` 判定
- lane設計、worker再配置、定期起動formation / cadence変更
- Queue starvation、duplicate start、owner conflictの検知
- `BLOCKED_ESCAPE` 後のrerouting
- member/run別productive-step実績分析とprocess改善

## Distributed Expertise

### 🌙ルナ — Product Lead / Work Designer

行う:
- Product discovery、未来workの発散
- Feature / experiment / Work Contract設計
- 意味のあるIssue作成とREADY品質への具体化
- Product priority proposal

原則行わない:
- 全Issue横断scan
- worker空き状況を見たglobal routing
- 他laneを含む最終priority決定

`Product proposes; Nagi routes.`

### ♦️ソラ — Executor / Main Implementation

定期runの基本flow:

`minimal sync → assigned NOW → assigned NEXT → assigned RESERVE → BLOCKED_ESCAPE`

原則行わない:
- 毎runの全Issue / Open PR横断探索
- 全体priority / formation判断
- 他worker laneのowner-conflict巡回

NOWがblockedならbounded self-resolutionを試す。解消できなければ`BLOCKED_ESCAPE`を記録して供給済みNEXTへ移る。NEXT / RESERVEまで枯れた場合のみlane-local gapを探索し、意味のあるworkを自ら作ってよい。

### ❤️レイ / 🌅アサヒ / ⭐️ミナ / 🍁カエデ / 🤖カイ

- 自分の専門lane内では自律的に発散・Issue作成・局所priority proposalを行ってよい
- 専門Authority（Design Gate / Research Evidence / Implementation ownership等）は維持する
- 全体Issue scan / global routingは原則行わない
- 重大blocker / risk / P0候補はナギへproposalとして返す

## Scheduled Run Contract

各workerの定期起動は、global scanではなくProductive Workをdrainする。

1. minimal syncを行う
2. assigned NOWを進める
3. 完了またはblockedならNEXTへ進む
4. NEXTも完了またはblockedならRESERVEへ進む
5. 同じblockerを状態変化なしで繰り返し確認せず`BLOCKED_ESCAPE`する
6. Queueが枯れたらlane-local gapを探索する
7. meaningful gapがあればIssue / sliceを作る
8. 可能なら同じrunで設計・実装・Research・Designまで進める
9. global reprioritizationが必要な場合のみナギへproposalする

定期runの終了条件は「確認が終わった」ではなく、**安全に実行可能なProductive Workをdrainしたこと**。

## NOW / NEXT / RESERVE Contract

🌊ナギは各laneに実行可能なQueueを供給する。

- `NOW`: 最優先で着手するwork
- `NEXT`: NOW完了・blocked時に即移れるwork
- `RESERVE`: starvation防止用の独立したbounded work

各entryは可能な限り以下を持つ。

- Issue / slice
- owner
- dependency状態
- allowed scope / path
- Definition of DoneまたはAcceptance Criteria
- blocker時のescape条件

## Local Discovery Is Encouraged

この仕組みはIssue作成や発散を抑制しない。

各専門家は、意味のある課題・未来機能・Researchテーマ・UX改善・技術負債・automation案を積極的に発見してよい。

ただし、
- 発見・設計・priority proposal = 専門家
- global priority / routing / formation = ナギ

と責任を分ける。

## Exceptions

次の場合は専門workerが通常境界を越えてよい。

- ナギ不在またはtool limitでglobal routing不能
- 明示的なdelegationがある
- 安全上、即時停止・blocker宣言が必要
- Single Owner scope内でのbounded self-resolution

例外時はGitHubへ理由を残し、恒久的な役割変更として扱わない。

## Measurement

Before / Afterで最低以下を#479へ記録する。

- `productive_steps_per_run`
- `verification_steps_per_run`
- `productive_step_ratio`
- `global_scan_steps_per_worker`
- `duplicate_flow_scan_count`
- `zero_productive_run_rate`
- `durable_outputs_per_run`
- `worker_unlock_count`
- `self_created_meaningful_work_count`
- `blocked_escape_count`

初期仮説:
- ♦️ソラ median productive steps/run >= 3
- ナギ以外のduplicate global scanを原則0へ近づける
- zero productive runを例外化する
- global scan削減分をimplementation / research / designへ移す

## Formation Review

定期起動メンバー・頻度・laneは固定しない。

🌊ナギは前回実績を分析し、productive steps、durable outputs、unlock effect、zero-productive run、発散/収束寄与をEvidenceとしてformationを変更できる。

`observe → hypothesize → reconfigure → measure → keep/revert`

## Relationship to Other Rules

- Project Charter (#595): Why / values / philosophy
- TEAM_RULES.md: 恒久的なチーム運用Rule
- Forward Progress Contract (#593): productive progressの測り方
- 本書 (#602): global Flow authorityとworker role boundary

Issue #79 untouched.
