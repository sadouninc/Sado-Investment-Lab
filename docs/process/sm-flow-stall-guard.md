# SM Flow Stall Guard — Queue starvation再発防止

担当: 🌊ナギ  
種別: Process Reliability / Scrum Master Control Loop

## 目的

レビュー・CI・Research/Design Gate待ちのPRを「実装中WIP」と誤計上してMain Implementation laneを止めない。

## WIP state contract

実装capacityを消費する:
- `IMPLEMENTING`
- `REVISION_REQUIRED`
- `CONFLICT_RESOLUTION`

原則として実装capacityを解放する:
- `CI_WAIT`
- `REVIEW_WAIT`
- `RESEARCH_GATE_WAIT`
- `DESIGN_GATE_WAIT`
- `OWNER_WAIT`
- `EXTERNAL_WAIT`
- `MERGE_READY`

後続workが同じpathを変更する場合は、capacityとは別にowner/path conflict guardでBLOCKする。

## Durable output signal

Flow stallの時間判定は `last_durable_output_age_minutes` を正とする。

Durable outputには少なくとも以下を含められる。
- 新規PR
- 実装・修正commit
- review blockerを解消するrevision
- accepted artifact / deterministic test evidence
- 次担当が即着手可能になる永続化handoff

`last_new_pr_age_minutes` はlegacy/補助signalとしてのみ扱い、PR発行数そのものを生産性KPIにしない。

## Starvation invariants

SM runでは以下をチェックリストではなく判定として評価する。

1. `READY_nonconflicting > 0 && active_implementation_wip == 0`
   - `QUEUE_STARVATION`
   - 同じrunでREADY workをroutingする。
2. READY workが存在し、durable outputが120分以上更新されていない
   - `FLOW_STALL_WARNING`
3. READY workが存在し、durable outputが240分以上更新されていない
   - `FLOW_STALL_CRITICAL`
   - 同じrunでreroute必須。
4. Agent dispatchが60分以上ACK/進捗Evidenceなし
   - `DISPATCH_LEASE_EXPIRED`
   - dispatchをorphan扱いし、lease expiry / reroute候補へ移す。
5. 同一blockerが2 run継続
   - `BLOCKED_ESCAPE_OVERDUE`
   - `BLOCKED_ESCAPE`必須。
6. worker stateがunknown/staleでも、READY + active WIP=0をsilent PASSしない。
   - explicit quota/unavailable等なら別workerへrerouteする。

PR数最大化が目的ではない。READYな非競合実装workがあるのにdurable implementation outputが止まる状態を検知する。

## Closed-loop decision

`flow_health_guard` は異常を分類し、`flow_control_loop` が必要時に #556 Queue selectorへ同一decision pathで接続する。

- detectorだけ置いて終了しない
- expired dispatch leaseはowner sliceを解放してreroute候補化
- selectorはowner/path/dependency/worker stateをfail-closedで確認
- GitHubへの実assignment/writeはruntime Flow AuthorityがEvidence付きで行う

## Dispatch lease contract

Agent/worker dispatchには最低以下を持たせる。

```text
work_ref:
owner_slice:
assigned_at:
acknowledged_at:
lease_expires_at:
fallback_owner:
```

ACKまたは進捗Evidenceなしで期限切れなら `DISPATCH_LEASE_EXPIRED` とし、旧dispatchを永続占有扱いしない。

## SM run output

最低限、以下を1 recordで残す。

```text
active_implementation_wip:
waiting_work_count:
ready_nonconflicting_count:
last_durable_output_age_minutes:
dispatch_orphans:
blocked_escape_overdue:
status: PASS|WARN|CRITICAL|ACTIONED
actions_taken:
missed_stall:
false_positive:
```

`確認済み`は判定結果として扱わない。

## Validation

Issue #645はコードmergeだけではCloseしない。

- hourly 🌊ナギ SM runで `SM_FLOW_SAMPLE` を#645へ永続化
- 5〜10 runを観測
- `missed_stall = 0`
- 重大なfalse positive = 0
- Queue starvation時に同runでACTIONEDされること

を確認後に完了判定する。条件未達ならguard/routingを修正して観測を継続する。

## Safety

- Review/Research/Design Gateを省略しない。
- WIP capを撤廃しない。
- 同一path/owner conflictは別guardでfail-closedする。
- actual AUTO_GREENを有効化しない。
- Owner / Investment Authorityを変更しない。
- Issue #79 untouched。

Refs: #645 #602 #593 #556 #479
