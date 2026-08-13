# Work Contract v1 — validation boundary

担当: 🌊ナギ  
種別: Implementation / Agent Harness / Documentation  
Refs: #480 #479 #431

`work_contract` は、Issue本文の人間向けGoal / Scope / Acceptance Criteriaを置き換えるものではない。Agentが作業開始前に、明示された実行境界をdeterministicに検証するための補助contractである。

## v1 supported shape

Issue本文の fenced `yaml` / `yml` block内に、単一の `work_contract:` を置く。

v1 parserは意図的に小さく、top-level scalarとlistだけを受け付ける。nested mappingなど未対応構造は推測せずfail closedする。

必須field:

- `version`
- `goal`
- `status`
- `owner_slice`
- `risk`
- `authority`
- `dependencies`
- `allowed_paths`
- `forbidden_paths`
- `acceptance_tests`
- `expected_outputs`
- `human_gate`
- `non_goals`

## Execution gate

`validate_issue_body()` が `valid=true` かつ `executable=true` の場合だけ、contract上は実装開始可能とみなす。ただしTEAM_RULES / Broadcast / Single Implementation Owner / Authority Gateは別途必須であり、このvalidatorはそれらを上書きしない。

v1は以下をfail closedする。

- malformed / missing contract
- required field欠損
- unsupported version / risk / authority
- `status != READY_FOR_IMPLEMENTATION`
- allowed / forbidden path overlap
- empty acceptance tests
- GREEN contractによる `TEAM_RULES.md`, `TEAM_STATE.md`, `.github/**` の許可
- GREEN contractによるIssue #79関連pathの許可

Dependenciesはv1では宣言値を保持するだけで、存在・merge・完了状態を推測しない。

## Non-goals

- automatic dispatch
- GitHub Issue Form
- merge / close
- owner lease / lock
- Investment Authority判定
- Issue本文の自動書換え

## Next integration

PR1 merge後、PR Rescue / Agent harnessのpreflightからこのpure validatorを呼ぶ小sliceを検討する。automatic dispatchは別Gateとする。
