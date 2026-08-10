# Blocker Classification & Self-Unblock Rule

担当: 🌊ナギ  
種別: Process / Team Coordination

## Purpose

「分からない」「確認できていない」を理由に、本来は担当者自身で調査して前進できる作業がユーザー入力待ちとして停止することを防ぐ。

## Blocker Types

| Type | Meaning | Default action |
| --- | --- | --- |
| `AUTHORITY_BLOCKED` | 👑サド等のAuthority判断が必要 | 判断材料・選択肢を準備して待つ |
| `DEPENDENCY_BLOCKED` | 先行Issue / PR / artifact待ち | dependencyを明記し、非競合作業へ移る |
| `CI_BLOCKED` | CI / build / test failure | 原因調査・修正。外部待ちなら別READYへ移る |
| `MISSING_ARTIFACT` | 必須prototype / fixture / specがGitHub SSoTにない | 作成元へhandoff不備として返す |
| `TECHNICAL_INVESTIGATION` | repo / code / Pages / build構造等を調べれば自己解消可能 | **停止せず調査を作業として続行** |
| `EXTERNAL_BLOCKED` | connector / permission / external service等、自力解消不能 | evidenceを残し、別作業へ移る |

## Core Rule

`TECHNICAL_INVESTIGATION` は原則として blocker ではなく作業である。

以下はユーザー入力待ちにしない。

- 既存CSS / component体系が分からない
- build / Pages構造が未確認
- 再利用すべき既存file / primitiveが未特定
- test / fixtureの場所が未確認
- repository内の実装経路をまだ調査していない

担当者自身が repository、commit、PR、tests、Pages、build configを確認し、安全な実装経路を特定する。

## Authority Boundary

- 投資思想、複数案の最終選択、Owner Acceptance → `AUTHORITY_BLOCKED`
- code構造、CSS体系、既存component、fixture位置、build方法 → `TECHNICAL_INVESTIGATION`
- 必須prototypeがGitHubに存在しない → `MISSING_ARTIFACT`

「分からない」だけではAuthority blockerにしない。

## Blocker Declaration Contract

停止する場合はIssueへ可能な限り以下を記録する。

```text
Status: <*_BLOCKED / TECHNICAL_INVESTIGATION>
Blocker Type: <classification>
Evidence: <Issue / PR / file / test / Pages checked>
Can Self-Unblock: YES / NO
Next Action: <who does what next>
Resume Condition: <condition>
```

`Can Self-Unblock: YES` の場合、原則として同run内でNext Actionへ進む。

待ち時間が発生する場合は、Single Implementation Ownerを守りながら別の非競合READY slice、review、test補強、dependency調査、次Queue準備へ切り替える。

## Scrum Master Maintenance

🌊ナギはMaintenance時に以下を確認する。

1. stale `IMPLEMENTING` / `BLOCKED`
2. Blocker Type未記載の停止
3. `Can Self-Unblock: YES` なのに長時間停止している作業
4. `TECHNICAL_INVESTIGATION` がユーザー待ちへ誤分類されていないか
5. `MISSING_ARTIFACT` がGitHub-complete Handoff Rule違反として作成元へ返されているか
6. CI / external wait中に別READY作業へ移れているか

## Visual Prototype Persistence

👑サド承認済み、またはProduct/IA Review・Implementation・Design QAの基準となるVisual Prototypeはチャットだけを正にしない。

- GitHub上の恒久成果物として保存する。
- 対応Issueから直接到達可能にする。
- 最新版 / version / superseded関係を識別可能にする。
- チャット履歴なしで次担当が対象物・目的・Authority状態を確認できることをhandoff完了条件とする。
- GitHubに必須prototypeが存在しない場合は `MISSING_ARTIFACT` としてhandoff未完了扱いにする。

## Origin

2026-08-11、#320の自己停止と#317のprototype handoff停止を受けて制定。Issue #99 Broadcast comment `5247406486` で即時運用を開始。
