# AI Productivity Metric Dictionary v0

Status: Pilot / baseline measurement  
Authority: Issue #479  
Pilot contract: Issue #490  
Purpose: Sado Investment Lab のAI開発・運用改善を、感覚ではなく再現可能なBefore/After指標で比較するための共通辞書。

## Measurement principles

- 個人評価ではなくSystem Improvementに使う。
- GitHub timestamp / CI metadata等から取得できる値を優先し、手入力を最小化する。
- 観測不能な値を推測しない。取得不能・定義不能は `UNKNOWN` とする。
- 待ち時間と実装時間を混同しない。
- metricの開始/終了eventを固定し、PoCごとに定義を変えない。
- Investment decision、BUY / SELL / HOLD semanticsとは分離する。

## Core metrics

| Metric | Definition | Start event / source | End event / source | Unit | UNKNOWN handling | Automation feasibility |
|---|---|---|---|---|---|---|
| READY → implementation start | Issueが実装可能状態になってから実装作業が開始されるまで | `READY_FOR_IMPLEMENTATION` が確認できるIssue event / structured status | 最初のimplementation commit、明示的IMPLEMENTING event、またはagent run startのうちcanonicalに採用したevent | duration | start/endのどちらかを確定できなければ `UNKNOWN` | MEDIUM。READY eventの構造化が進めばHIGH |
| implementation → PR ready | 実装開始からreview可能なPRになるまで | 上記implementation start | PR作成時刻。Draft運用時はready-for-review event | duration | implementation start不明なら `UNKNOWN` | HIGH〜MEDIUM |
| PR ready → merge | review可能状態からmergeまで | PR created / ready-for-review timestamp | merged_at | duration | 未mergeは評価時点ではopen durationとして別表示し、完了値を捏造しない | HIGH |
| total lead time | READYからmergeまでのend-to-end時間 | READY event | merged_at | duration | いずれかのanchor不明なら `UNKNOWN` | MEDIUM |
| human confirmation count | 実装開始前後に人間へ明示確認を要求した回数 | Issue READY以降のconversation / issue / agent trace | PR readyまで | count | trace不足時は `UNKNOWN`。0と推測しない | LOW〜MEDIUM |
| Owner wait time | Owner Authority / explicit owner input待ちで停止した時間 | OWNER_AUTHORITY blocker開始 | owner response / unblock event | duration | blocker開始/解除時刻が不明なら `UNKNOWN` | MEDIUM（structured blockerが必要） |
| reviewer wait time | review可能PRがblocking review待ちだった時間 | PR ready または review request | blocking review response / gate satisfied | duration | reviewer stateを復元できなければ `UNKNOWN` | MEDIUM〜HIGH |
| CI wait / rework time | CI実行待ちとCI失敗修正に費やした時間 | first relevant CI run / failure | required checks green | duration | workflow metadata不足時は `UNKNOWN` | HIGH for CI wait; MEDIUM for rework separation |
| conflict count | merge conflict / duplicate implementation / owner collision等、明示的競合の発生回数 | GitHub conflict state / blocker record | N/A | count | evidenceがなければ `UNKNOWN`。単に0としない | MEDIUM |
| first-pass CI result | 最初のrequired validationが再実行・修正なしで通ったか | first required CI/check set | first terminal result | boolean / enum `PASS | FAIL | UNKNOWN` | check setを特定できなければ `UNKNOWN` | HIGH |
| reviewer rework count | review指摘により実装変更が必要になった回数 | blocking/actionable review feedback | subsequent fix cycles | count | review→fix relationが不明なら `UNKNOWN` | MEDIUM |
| scope deviation count | Issue / work contractのScope外変更を試みた、または実施した件数 | diff + contract / explicit blocker evidence | PR ready | count | contractが機械判定不能なら `UNKNOWN` | MEDIUM。allowed_paths導入でHIGH化可能 |
| forbidden path attempt count | machine-readable contractのforbidden_pathsへ変更を試みた件数 | agent trace / rejected diff / validation | PR ready | count | attempt traceがなければ `UNKNOWN` | LOW〜MEDIUM |
| merged PR throughput | 指定期間にmergeされた対象PR数 | GitHub merged PR metadata | period end | count / period | repository/filter不明なら `UNKNOWN` | HIGH |
| completed Issue throughput | 指定期間にcompleted Closeされた対象Issue数 | GitHub issue close metadata | period end | count / period | state_reason等が不足する場合は対象条件を明示 | HIGH |
| Owner intervention per completed unit | 完了単位あたりOwnerによる解除・判断・確認の回数 | structured intervention records | completed Issue / merged unit | count / completed unit | numeratorの観測不足時は `UNKNOWN` | LOW〜MEDIUM |

## Metric event rules

### READY event

優先順位:
1. machine-readable `status: READY_FOR_IMPLEMENTATION`
2. canonical Issue status field / structured comment
3. human-readable text onlyの場合は明示的に識別できるときだけ採用

曖昧な「そろそろ実装可能」はREADY eventにしない。

### Implementation start

候補sourceを混在させる場合はsource typeを保存する。

- `AGENT_RUN_START`
- `IMPLEMENTING_STATUS`
- `FIRST_IMPLEMENTATION_COMMIT`

PoC比較では同じsource priorityを使う。

### PR ready

- non-draft PR: `created_at`
- draft PR: `ready_for_review_at`

Draft作成時刻をreview-readyと誤認しない。

### Merge

GitHub `merged_at` をAuthorityとする。Closed without mergeはmerge完了として扱わない。

## Blocker taxonomy v1

| Blocker | Definition | Typical evidence |
|---|---|---|
| `OWNER_AUTHORITY` | Ownerだけが確定できる判断・承認待ち | Issue/PRにOwner decision required |
| `DESIGN_AMBIGUITY` | Goal/Scope/AC/UX等が曖昧で安全に実装開始できない | clarification request / design gate |
| `DEPENDENCY` | upstream Issue/PR/artifactが未完了 | dependency ref / blocked status |
| `CI_FAILURE` | required CI/check失敗 | workflow/check failure |
| `REVIEW_WAIT` | review可能だがblocking review待ち | requested reviewer / unresolved blocking review |
| `MERGE_CONFLICT` | base進行等によりmerge conflictが発生 | GitHub mergeability / conflict evidence |
| `MISSING_ARTIFACT` | 必要なResearch/data/generated artifact等が存在しない | missing canonical input |
| `TECHNICAL_INVESTIGATION` | 原因特定や技術調査が必要で実装が確定できない | investigation note / spike |
| `TOOL_LIMIT_QUOTA` | tool利用上限・quota・実行環境制約 | explicit tool/quota error |
| `EXTERNAL` | 外部サービス・provider・第三者要因待ち | external status/evidence |
| `DUPLICATE_WORK_OWNER_CONFLICT` | 同一scopeへの複数Owner/Agent競合、重複作業 | ownership conflict / duplicate PR |

### Blocker recording rule

最低限、可能なら以下を保持する。

```text
blocker_type
started_at
resolved_at
source_ref
notes
```

複数blockerが同時に存在する場合、単一原因へ無理に丸めない。primary blockerを置く場合もsecondary blockerを失わない。

## UNKNOWN policy

`UNKNOWN` は失敗や0を意味しない。

- timestamp不明 → duration `UNKNOWN`
- trace不足 → count `UNKNOWN`（0にしない）
- CI対象check不明 → first-pass result `UNKNOWN`
- blocker開始時刻不明 → wait time `UNKNOWN`

集計時はUNKNOWNを分母へ暗黙投入せず、`known_n / total_n` を併記する。

## Pilot measurement template

Issue #490終了時に最低限以下を記録する。

```yaml
pilot_issue: 490
contract_version: 0
clarification_count: 0
human_confirmation_count_before_implementation: 0
implementation_start_to_review_ready: UNKNOWN
scope_deviation_count: 0
forbidden_path_attempt_count: 0
first_pass_validation: UNKNOWN
reviewer_rework_count: UNKNOWN
agent_harness_result_mismatch: UNKNOWN
notes: "Values must be replaced only by observed evidence; UNKNOWN is valid."
```

上記の0は本PilotでIssue Contract上、追加質問・Scope逸脱・forbidden path変更を行わず実装したことを観測できた項目に限る。時間・review/CI系はGitHub metadataが揃った後に確定する。

## Future automation source map

High automation candidates:
- PR created / ready / merged timestamps
- CI run start/end/result
- merged PR throughput
- completed Issue throughput

Medium candidates:
- READY event
- implementation start
- reviewer wait
- blocker duration
- scope deviation（allowed_pathsが構造化されている場合）

Manual/trace-dependent candidates:
- clarification count
- human confirmation count
- Owner intervention
- agent/harness result mismatch

自動取得できない値を埋めるためにLLM推測を使わない。
