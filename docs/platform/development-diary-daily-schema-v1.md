# Development Diary daily snapshot schema v1

担当: ♦️ソラ  
種別: Implementation / Observability Contract

## 目的

Development Diaryの日次記録を、後続collector / renderer / monthly rollupが同じ意味で利用できるmachine-readable contractとして固定する。PR数やmerge数だけを性能スコアにせず、Factory Output / Executor Performance / Flow Health / Economicsの4層を別々に保持する。

## 時間境界

`diary_date_jst` はJSTの対象日。`source_window_start_jst`〜`source_window_end_jst` はそのJST 1日分の観測windowを表し、UTCへ変換しても対象日の意味を変えない。`closed_at_jst` はsnapshotを締めた時刻。

## UNKNOWNと0

nullable metricの`null`は取得不能・未観測・分母不明などのUNKNOWNを表す。`0`は観測済みのゼロであり、両者を変換しない。特に`free_executor_ratio`は観測分母が0またはUNKNOWNなら推測せず`null`とする。

## 4 layers

### factory_output
READY数、実装開始数、PR open/merge/close-unmerged、durable output、productive step、lead timeを記録する。countは非負整数、lead timeは非負数または`null`。

### executor_performance
`executor`と`task_class`を各recordに保持する。同じexecutorでもtask classが異なれば別recordを許容し、将来のexecutor × task_class集計をlosslessにする。dispatch/ACK/execution evidence/PR/merge/success/failure/no-op/rework/duplicate-conflict wasteを独立して保持する。

### flow_health
active implementation WIP、waiting/READY、queue replenish latency、path-owner conflict、CI stall、starvation state、BLOCKED_ESCAPE、人手介入、durable output intervalを保持する。待機PR数をactive WIPへ自動変換しない。

### economics
free executor ratio、paid fallback、Copilot usage/credits、accepted unit/merge当たりAI costを保持する。取得不能なcost/usageは`null`であり、0を捏造しない。

## Factory Capability Change

`factory_capability_changes[]` は`FACTORY_CAPABILITY_CHANGE`としてeffective time、capability、before/after、evidence refs、`PILOT | PROVEN | UNKNOWN`を保持する。evidence不足を隠さないためevidence_refsは1件以上必須。PROVENは特に証拠なしでは成立しない。

## Corrections

過去snapshotをsilent rewriteしない。訂正は`corrections[]`に`correction_id / reason / evidence_refs / recorded_at`を残し、監査可能にする。負値を訂正表現として使用しない。

## Safety

このschemaは総合performance ranking、BUY/SELL/HOLD、投資閾値を定義しない。Pages UI、workflow、permission、AUTO_GREEN設定も変更しない。Issue #79 untouched。
