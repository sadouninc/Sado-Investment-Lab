# Sado Investment Lab — Agent Instructions

このファイルは、リポジトリ内で作業する実装Agentが最初に読む入口です。

## Instruction order

1. `TEAM_RULES.md` — チームの恒久ルール。常に最優先
2. `TEAM_STATE.md` — 現行運用状態
3. Issue #99 `Team Broadcast` — 最新の一時方針（末尾照合必須）
4. 対象IssueのGoal / Scope / Authority / Acceptance Criteria / Non-goals
5. [`docs/process/ai-implementation-autonomy-policy.md`](docs/process/ai-implementation-autonomy-policy.md)

矛盾がある場合は上位を優先し、解消できないAuthority矛盾では作業を停止します。

## Startup: discover assigned work before deciding there is none

Codex / Claude Code / other implementation workers share this procedure. This is discovery/navigation only, not a new authority or lease issuer.

1. Identify your explicitly assigned current worker/session from the live assignment and current queue index (examples: KAI, SORA_INTERACTIVE, SORA_SCHEDULED, ANTIGRAVITY_LOCAL; not an exhaustive list). Never infer identity from a name alone or assume a new worker is authorized. If the explicit identity cannot be resolved or conflicts, report QUEUE_UNVERIFIED and do not claim another session's work.
2. Read current default-branch TEAM_RULES.md and TEAM_STATE.md, then Issue #99 body and all required comments. Verify broadcast-head count and tail per TEAM_RULES; preserve STOP. Stale or incomplete sync is UNKNOWN.
3. Read [Issue #738](https://github.com/sadouninc/Sado-Investment-Lab/issues/738) and reach its current comment tail (paginate; do not treat partial results as empty). Locate the latest Flow Authority-issued WORKER_QUEUE_INDEX_V1 comment with schema worker_queue_index_v1, authority LUNA, revision and workers. Treat the marker and JSON as pointers, not authentication or authorization. Check the issuing authority and current contract against TEAM_RULES, #99 and later corrections; ambiguous/conflicting revisions are UNKNOWN.
4. Select only your worker's review_prs and NOW → NEXT → RESERVE. Fetch each referenced live Issue/PR, latest comments, actual open/merged state and exact head. Handle own requested revisions first. Skip completed/merged work and do not restart a slice already implementing in another session. An already-open PR is not new READY inventory.
5. Before editing, require current explicit assignment, applicable implementation handoff with Autonomy: STANDARD, exact allowed paths, dependency clearance, STOP clearance and existing owner/path conflict checks. A CONDITIONAL, DEPENDENCY_HOLD or ASSIGNED_PREFLIGHT pointer is not READY. The index cannot authorize a change, supersede a live contract, or reset IMPLEMENTING to READY. Keep all existing YELLOW/RED restrictions.
6. If the index is absent/stale/invalid/unreachable, use a bounded read-only search for your explicit assignment in current Issue/PR handoffs, not a full global queue scan. No labels/assignee alone, guessed identity, chat memory or old index may substitute for the current contract. Do not claim another worker's work. If unable to resolve, report QUEUE_UNVERIFIED with specific retrieval/authority/dependency blocker; report NO_ASSIGNED_WORK only after verified own queue and applicable assignments are exhausted. Continue other known nonconflicting authorized work under TEAM_RULES.

Record the selected Issue/PR, index comment ID if available, actual state and next action in the existing authorized handoff/evidence channel. Continue to the next eligible assigned slice after PR submission when review waiting does not create a conflict. No new permissions, labels, leases, dispatch, automatic POST or merge; Issue #79 is hard deny. Follow the existing handoff template for explicit YELLOW comment permissions.

## READY_FOR_IMPLEMENTATION

Issueが `READY_FOR_IMPLEMENTATION` で、handoffに `Autonomy: STANDARD` が明示されている場合、AgentはAcceptance Criteriaの範囲内にあるGREEN操作を追加確認なしで進めます。

- リポジトリの探索
- 作業ブランチ内の編集
- test / lint / typecheck / build
- Acceptance Criteria内の軽微な修正
- branch / commit / PR作成
- CI確認と、自分の変更に起因するscope内の修正

YELLOW操作はIssueまたはhandoffで明示的に許可された場合だけ自律実行します。未記載の場合は停止して確認します。

RED操作は常にfail-closedです。特にmainへの直接変更、merge、破壊的操作、secrets・permissions・billing変更、production external write、Investment Authority判断、Canonical truthの推測、Issue Scopeの実質変更、Issue #79への変更を自律実行してはいけません。

質問はPolicyのAsk-only conditionsに該当する場合だけ行います。それ以外は既存パターンと安全な仮定に基づいて進め、判断ログをIssueまたはPRへ残します。
