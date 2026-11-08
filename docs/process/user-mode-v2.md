# User Mode v2 — Presence / Merge Policy / Flow Authority

初版担当: 🌊ナギ / 現行Flow整合: 🌙ルナ  
種別: Process / Mode Contract / Productivity  
現行の権限・運用状態は [`TEAM_RULES.md`](../../TEAM_RULES.md) と [`TEAM_STATE.md`](../../TEAM_STATE.md) が正。本書は旧Mode設計の説明であり、権限・Gate・Leaseを新設しない。

Refs: #617 #602 #587 #479 #871 / PR #869

## Goal
Ownerの在席状態、merge policy、Flow Authorityを分離し、次の3つの利用者向けModeを安全に運用する。

| User Mode | presence | merge_policy | default Flow Authority |
| --- | --- | --- | --- |
| `ACTIVE_MANUAL` | ACTIVE | MANUAL | 🌙ルナ |
| `ACTIVE_AUTO` | ACTIVE | AUTO_GREEN | 🌙ルナ |
| `AWAY` | AWAY | AUTO_GREEN | 🌙ルナ / event-driven ♦️ソラ delegation |

旧 `ACTIVE` はmigration時のみ `ACTIVE_MANUAL` と解釈する。

## ACTIVE_MANUAL
- 👑サドは在席
- GREEN PRもOwner/manual mergeを待つ
- 🌙ルナが暫定Single Flow Authority
- 各専門workerは#602どおりlocal discovery / executionへ集中

## ACTIVE_AUTO
- 👑サドは在席
- 🌙ルナが暫定Single Flow Authority
- `AUTO_GREEN` Merge Gateを満たす低リスクPRだけ自動merge候補
- Owner/Investment Authority、explicit Owner Acceptance、security/secrets/permissions/paid/destructive等は自動mergeしない

## AWAY
- 👑サドは非在席
- Owner-only判断はAuthority backlogへ隔離
- GREEN Merge Gateを満たす範囲は`AUTO_GREEN`候補
- 🌙ルナが実行可能ならglobal Flow Authorityを維持
- 🌙ルナが実行不能かつ交通整理イベントが起きた場合のみ♦️ソラがDelegated Flow Authorityを一時的に担う

### ♦️ソラ Delegated Flow Authority trigger
- `QUEUE_STARVATION`
- `OWNER_CONFLICT`
- `NO_REROUTE_AFTER_BLOCKED_ESCAPE`
- `PRIORITY_CONFLICT`
- `STATE_DRIFT`
- `GLOBAL_BLOCKER`

通常runや単なるCI/review確認はtriggerではない。
Delegation中も全Issue横断scanを毎run行わない。必要な交通整理だけ実施し、NOW/NEXT/RESERVEを供給したらExecutorへ戻る。

## AUTO_GREEN Gate
全条件が既知かつGREENの場合のみ許可する。

- CI / required checks PASS
- REQUEST_CHANGESなし
- merge conflictなし
- required Product / Design / Reliability Gate PASS
- latest headへのreview evidenceあり
- Owner / Investment Authorityを含まない
- security / secrets / permissions / paid / destructive等のsensitive changeではない
- explicit Owner Acceptance必須ではない
- Issue #79 untouched

UNKNOWNはPASSへ補完しない。

## Transition safety
`expected_current_mode + target_mode + transition_id` のCAS guardを使う。

- stale expected mode → BLOCK
- duplicate transition id → BLOCK
- no-op → BLOCK
- legacy `ACTIVE` → migration時のみ`ACTIVE_MANUAL`へnormalize

## Transition record
各mode changeはdurable transactionとして最低限以下を残す。

```text
mode_from: ACTIVE_MANUAL|ACTIVE_AUTO|AWAY
mode_to: ACTIVE_MANUAL|ACTIVE_AUTO|AWAY
changed_at: <timestamp>
transition_id: <unique id>
merge_policy: MANUAL|AUTO_GREEN
global_flow_authority: LUNA|SORA_DELEGATED
authority_backlog: <refs or none>
material_blockers: <refs or none>
```

## Measurement
#479で最低限以下を観測する。

- `mode`
- `merge_policy`
- `manual_merge_wait_minutes`
- `auto_green_merge_count`
- `auto_green_block_count_by_reason`
- `delegated_sora_sm_activation_count`
- `sora_productive_steps_when_delegated`
- `queue_starvation_recovery_count`
- `owner_authority_backlog_count`

## Principle
Modeを増やす目的はルール追加ではなく、Owner不在・merge待ち・交通整理不足による停止時間を減らしつつ、Authorityと安全性を維持すること。

Issue #79 untouched.
