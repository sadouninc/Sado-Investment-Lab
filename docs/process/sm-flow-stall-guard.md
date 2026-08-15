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

## Starvation invariants

SM runでは以下をチェックリストではなく判定として評価する。

1. `READY_nonconflicting > 0 && active_implementation_wip == 0`
   - `QUEUE_STARVATION`
   - 同じrunでREADY workをroutingする。
2. READY workが存在し、新規PRの最終発行から120分以上
   - `FLOW_STALL_WARNING`
3. READY workが存在し、新規PRの最終発行から240分以上
   - `FLOW_STALL_CRITICAL`
   - 同じrunでreroute必須。
4. Agent dispatchが60分以上ACK/進捗Evidenceなし
   - `DISPATCH_LEASE_EXPIRED`
   - dispatchをorphan扱いし、lease expiry / reroute候補へ移す。
5. 同一blockerが2 run継続
   - `BLOCKED_ESCAPE_OVERDUE`
   - `BLOCKED_ESCAPE`必須。

PR数最大化が目的ではない。READYな非競合実装workがあるのにdurable implementation outputが止まる状態を検知する。

## SM run output

最低限、以下を1 recordで残す。

```text
active_implementation_wip:
waiting_work_count:
ready_nonconflicting_count:
last_new_pr_age_minutes:
dispatch_unacked_age_minutes:
same_blocker_run_count:
status: PASS|WARN|CRITICAL
actions:
```

`確認済み`は判定結果として扱わない。

## Safety

- Review/Research/Design Gateを省略しない。
- WIP capを撤廃しない。
- 同一path/owner conflictは別guardでfail-closedする。
- actual AUTO_GREENを有効化しない。
- Owner / Investment Authorityを変更しない。
- Issue #79 untouched。

Refs: #645 #602 #593 #556 #479
