# Multi-Executor Auto Router v1

担当: ♦️ソラ  
種別: Implementation Contract / Flow Automation

## 目的

READY workをAmazon Q / Jules / SoraへFREE_FIRSTでleaseし、起動しないexecutorを短時間で失効・rerouteする。global priorityは🌊ナギのAuthorityに残し、この機構は既に選定されたmachine-readable candidateの実行制御だけを担う。

## Fail-closed preflight

candidateは `preflight_valid=true`、dependency/path/owner conflictなし、GREEN/YELLOW、`broadcast_sync_verified=true`、かつ明示的な非Owner authority (`EXECUTOR|FLOW|AUTOMATION`) が必要。欠落/UNKNOWNはPASSへ丸めない。`OWNER_AUTHORITY` は独立したblock reasonで停止する。Issue #79はhard deny。

## Lease / reconcile

`READY → DISPATCHED → ACKED → EXECUTION_EVIDENCE → PR_OPEN`

- ACKなし10分: `DISPATCH_ACK_EXPIRED`
- ACK後20分execution evidenceなし: `ACK_STALLED`
- late ACKはexpired leaseを復活させない
- execution evidence / PR_OPENを観測したら競合leaseを抑止
- PR_OPENでimplementation capacityを解放
- provider dispatchはdurable `AUTO_ROUTER_DISPATCH lease_id=...` markerでidempotent化

## Reroute

terminal pre-execution failureだけがreroute対象。reroute前にcandidateを必ずfresh preflightし、失敗providerは同一attemptで再選択しない。FREE_FIRST順序を維持し、safe candidate/providerがなければfail closedする。paid duplicate dispatchは禁止。

## Telemetry

reconcilerは `lease_id / work_ref / executor / task_class / terminal_state / execution_evidence / pr_open / rerouted / next_executor` をmachine-readableに返し、#479/#723 collectorが利用できる形にする。

## 境界

- provider-specific dispatch primitiveは `executor_dispatch_adapters.py` を再利用し、第二のcontrol planeを作らない
- actual AUTO_GREEN executionはOFFのまま
- `.github/**`, TEAM_STATE, TEAM_RULES, Pages, investment logicはこのsliceで変更しない
- Issue #79 untouched
