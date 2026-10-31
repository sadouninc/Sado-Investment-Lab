# Daily Flow Playbook — Startup Sync v2

担当: 🌙ルナ / Flow Authority  
種別: Process / Reliability / Performance  
Issues: #338, #871

> 日々の入口はこの1ページ。恒久ルールは `TEAM_RULES.md`、現在状態は
> `TEAM_STATE.md`、変更履歴とroutingは Issue #99 を正とする。本書は権限・必須Gate・
> GitHub protectionを追加、削除、または上書きしない。

## 1. Minimal startup sync

1. `TEAM_RULES.md` のidentityを確認する。前回確認済みidentityと異なる、または確認できない場合だけ全文を読み直す。
2. `TEAM_STATE.md` を読む。恒久ルールとの矛盾は `TEAM_RULES.md`、現在routingとの矛盾はIssue #99の最新の正規記録へ照合する。
3. Issue #99本文のauthoritative `broadcast-head` を取得する。
4. 既知cursorの次からheadまでを取得し、`To: ALL` と自分宛だけを適用する。connectorが全件を返しても処理対象は差分に限定する。
5. 取得末尾がheadと一致した時だけcursorを更新して `VERIFIED` とする。head未到達、truncation、rollback、矛盾未解決なら `BROADCAST_SYNC_UNVERIFIED`。
6. minimal sync後は、割当済み `NOW → NEXT → RESERVE` のproductive workへ直ちに移る。

```text
rules identity → TEAM_STATE → #99 body/head → verified cursor delta → NOW
```

`BROADCAST_SYNC_UNVERIFIED` を「新しい指示なし」と解釈しない。新規の高リスク作業は始めず、既に安全性を確認できる非競合作業だけを継続する。

## 2. Normal delivery flow

```text
Issue contract
  → Single Implementation Owner / scope preflight
  → branch → non-empty commit → PR
  → exact-head CI + required independent review/Gates
  → mergeability and blockers recheck
  → merge at expected head
  → merge SHA + parent reconciliation
  → NEXT_AUTO
```

- 実装開始前にIssue/slice、owner、exact scope/path、既存PR・claim・Leaseとの競合を確認する。UNKNOWNなowner/path conflictは実装HOLD。
- PRは最新head SHAでCI、必要なreview、Issue固有Gate、mergeabilityを確認する。古いheadの証跡を流用しない。
- 一般のCOMMENTED reviewを、根拠なくGitHubの正式な`APPROVED`必須条件へ昇格しない。一方でbranch protection、CODEOWNERS、Issue contractが要求するreviewは省略しない。
- `AUTO_GREEN` は適格PRだけに適用する。merge直前にexpected head、CI、blocking review、required Gate、mergeabilityを再確認する。
- merge後は実際のmerge SHAを親Issueへ記録する。IssueがOwner Acceptanceを明示要求する場合、Owner本人のPASS前にcompleted Closeしない。
- run終了時は次の安全な一手を `NEXT_AUTO` として具体化する。PR作成や確認だけを通常の停止条件にしない。

## 3. Non-negotiable safety gates

以下はfail-closed（`UNKNOWN != PASS`）。

| Gate | Source / application |
| --- | --- |
| Issue #79 HARD DENY | 後日の明示的なauthoritative instructionがない限り、変更・コメント・close・実装しない。 |
| Owner / Investment Authority | AIが推定・代行しない。対象Issueの正規契約とOwnerの明示判断が必要。 |
| Security / secrets / permissions / paid / destructive | 正規の権限と必須承認を保持する。AUTO_GREENへ暗黙昇格しない。 |
| Single Implementation Owner | 同じIssue/slice/file/logicの並行実装を避け、競合不明ならHOLD。 |
| GitHub / Issue required Gates | exact-head CI、blocking review、branch protection、Issue固有Product/Design/Reliability Gateを満たす。 |
| Owner Acceptance close | Issue本文・Acceptance Criteria・DoDが明示要求する場合だけ必須。通常Issueへ追加しない。 |

## 4. Exception and recovery

進められない時は、同じ確認を無限反復せず次を1件のHOLD記録へまとめる。

```text
BLOCKER:
canonical source:
unblock owner:
required evidence:
exit condition:
next check event:
safe nonconflicting work:
```

- 技術調査、CI待ち、外部待ちは直ちにuser escalationとはしない。bounded self-resolution後、独立した安全作業へ`BLOCKED_ESCAPE`する。
- expired Leaseやlate ACKは復活させない。新しい正規Lease、fresh conflict preflight、必要なRELEASE/ACKを要求する。
- Authority、Owner判断、秘密情報、権限変更、支払、破壊的操作が必要なら安全な準備までで止め、判断主体と解除条件を明示する。
- 状態が変化した時だけ再確認する。新証跡がなければverification loopを増やさない。
- TEAM_STATEが欠落・stale・矛盾する場合は `TEAM_RULES.md → Issue #99 Current Active Board → verified Broadcast delta` にfallbackし、driftを報告する。

## 5. Evidence at run end

```text
productive_steps:
verification_steps:
durable_outputs:
blocked_escape_count:
zero_productive_run: yes|no
merge_sha: <sha|N/A>
NEXT_AUTO:
```

実装・merge・自然なclosed-loopを実証と未実証に分ける。文書量、コメント数、確認回数だけを成果としない。

## Canonical references

- `TEAM_RULES.md`: permanent rules, PR/review flow, Broadcast verification, ownership and Owner Acceptance
- `TEAM_STATE.md`: current mode, routing, AUTO_GREEN safety, queue/Lease state, active guardrails
- Issue #99: Current Active Board, `broadcast-head`, append-only operational changes
- Issue #625: AUTO_GREEN activation evidence
- Issues #556 / #690: dispatch activation Lease and recovery semantics
- Issues #338 / #871: differential startup and process-simplification contracts
