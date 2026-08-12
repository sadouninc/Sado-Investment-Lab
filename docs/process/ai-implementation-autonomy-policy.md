# AI Implementation Autonomy Policy v1

> Sado Investment Lab — Codex / Copilot共通のDelegation Boundary

## 目的

確認を無条件になくすのではなく、確認が必要な境界を外側へ追い出す。

Issueが `READY_FOR_IMPLEMENTATION` となり、Goal / Scope / Authority / Acceptance Criteria / Non-goalsが明確で、handoffに `Autonomy: STANDARD` がある場合、その境界内の実装判断をAgentへ委譲する。

本Policyは`TEAM_RULES.md`を置換・複製しない。矛盾する場合は`TEAM_RULES.md`を優先する。

## GREEN — Autonomous

Acceptance Criteriaの範囲内で、以下は追加確認なしで進めてよい。

- repository内のread / search
- 対象作業ブランチ内のfile edit
- 既存コード・文書パターンの調査と再利用
- unit / integration testの追加
- test / lint / typecheck / buildの実行
- Acceptance Criteria達成に必要な軽微なbug fix
- git diff / statusの確認
- 作業branchの作成
- scope内変更のcommit
- PRの作成
- CI結果の確認
- CI failureが自分の変更に起因する場合のscope内修正

実装上の細部は、`TEAM_RULES.md`、対象Issue、既存パターンの順で判断する。質問の代わりに、重要な仮定と判断をIssueまたはPRへ記録する。

## YELLOW — Explicit scope permission

以下は、対象Issueまたはhandoffで明示的に許可された場合だけ自律実行する。未記載の場合は質問または停止する。

- dependencyの追加・更新
- generated artifactの更新
- database migration
- external network access
- GitHub Issue / PRへの自動コメント
- GitHub Actions・workflowの変更

許可があっても、REDに該当する操作へ拡張してはならない。

## RED — Fail closed

以下は`Autonomy: STANDARD`の対象外であり、自律実行しない。

- mainへの直接変更・直接push
- PR merge
- Issueの自動close
- destructive delete、history rewrite、回復困難な操作
- secrets、permissions、billingの変更
- production external systemへのwrite
- BUY / SELL / HOLD等のInvestment Authority判断
- Investment Canonical State / Canonical truthの推測による確定
- Issue Scope / Acceptance Criteriaを実質的に変更する設計判断
- 複数Authorityが矛盾し、安全に解決できない状態での続行
- Issue #79への変更

RED操作が必要になった時点で停止し、必要なAuthorityへ具体的な理由と最小の選択肢を提示する。

## Ask-only conditions

Agentが実装を止めて質問するのは、原則として次の7条件だけとする。

1. Acceptance Criteria同士が矛盾している
2. 必要なAuthority判断がIssueに存在しない
3. RED操作が必要である
4. Scope外変更なしではAcceptance Criteriaを満たせない
5. destructive / irreversible riskがある
6. secrets / billing / permissions / external production writeが必要である
7. Canonical investment truthを推測する必要がある

該当しない場合は、合理的かつ可逆な仮定を明示して作業を続ける。

## Runtimeとの境界

この文書はrepository-side instructionであり、Codex runtime固有のsandbox・approval設定値を定義しない。

- workspace内に限定されたwrite権限を優先する
- unrestricted / full-accessを既定にしない
- 実環境で利用できない設定を推測で追加しない
- runtime tuningとCopilot allow/deny実装は別sliceで扱う

## Pilot measurement

Policy適用後の最初の通常READY Issueで次を記録する。

| Metric | 記録内容 |
|---|---|
| `human_confirmation_count` | GREEN範囲でOwnerへ確認した回数。目標0 |
| `blocked_duration` | AgentがAuthority・環境待ちで停止した時間 |
| `implementation_to_review_ready` | 実装開始からreview-readyまでの時間 |
| `unsafe_operation_blocked_count` | RED操作をfail-closedした回数 |

本Policy自体のPRはbaselineとし、PR1 merge後に開始する最初の通常READY implementationをpilot対象とする。

## READY handoff

実装担当へのhandoffには、[`ready-for-implementation-handoff.md`](ready-for-implementation-handoff.md)を使用する。
