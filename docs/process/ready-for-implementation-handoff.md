# READY_FOR_IMPLEMENTATION Handoff Template

以下をIssueコメントへ記入して実装担当へ渡す。

```text
担当: <担当者>
種別: Implementation Handoff
Status: READY_FOR_IMPLEMENTATION
Autonomy: STANDARD

Goal:
<達成する結果>

Scope:
- <変更対象>

Authority:
- <仕様・判断の正となるIssue、文書、担当者>

Acceptance Criteria:
- [ ] <検証可能な完了条件>

Non-goals:
- <今回変更しないもの>

YELLOW permissions:
- <許可するYELLOW操作。なければ None>

Agent contract:
このIssueのAcceptance Criteria内では、repo探索、branch作成、file edit、test/lint/typecheck/build、軽微修正、commit、PR作成、CI確認まで自律的に進めてよい。

実装上の細部はTEAM_RULES、Issue Authority、既存パターンに従い自分で判断する。質問はAI Implementation Autonomy PolicyのAsk-only conditionsに該当する場合だけ行う。それ以外は質問せず、必要な仮定を作業ログへ残して進める。

main direct write / merge / Issue auto-close / destructive operation / secrets・billing・permissions変更 / production external write / Investment Authority判断 / Canonical truth推測 / scope実質変更 / Issue #79変更は禁止する。
```

`YELLOW permissions`に記載されていないYELLOW操作は自律実行しない。`Autonomy: STANDARD`はRED操作の許可を意味しない。
