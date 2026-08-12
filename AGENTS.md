# Sado Investment Lab — Agent Instructions

このファイルは、リポジトリ内で作業する実装Agentが最初に読む入口です。

## Instruction order

1. `TEAM_RULES.md` — チームの恒久ルール。常に最優先
2. Issue #99 `Team Broadcast` — 最新の一時方針
3. 対象IssueのGoal / Scope / Authority / Acceptance Criteria / Non-goals
4. [`docs/process/ai-implementation-autonomy-policy.md`](docs/process/ai-implementation-autonomy-policy.md)

矛盾がある場合は上位を優先し、解消できないAuthority矛盾では作業を停止します。

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
