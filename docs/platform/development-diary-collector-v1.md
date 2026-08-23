# Development Diary collector v1

担当: ♦️ソラ  
種別: Implementation Contract / Evidence Mapping  
Authority: Issue #730 / `data/contracts/development-diary-daily-v1.schema.json`

## 目的

Development Diaryの日次snapshotへ、GitHub/SMの**durable evidenceだけ**を決定論的に正規化する。collectorは投資判断、executor ranking、routing policyを作らない。

## 時間境界

`diary_date_jst` はJSTの半開区間 `[00:00:00, 翌日00:00:00)`。23:59:59は当日、翌00:00:00は翌日。通常close時刻は翌00:10 JST。

## Evidence mapping

| normalized kind | source例 | snapshotへの意味 |
| --- | --- | --- |
| `READY` | machine-readable READY evidence | Factory Output ready |
| `DISPATCHED` | durable lease record | reservation / waitingのみ |
| `ACKED` | durable ACK record | reservationのみ |
| `EXECUTION_EVIDENCE` | slice-linked non-empty commit等 | implementation start |
| `PR_OPEN` | GitHub PR created evidence | PR output |
| `MERGED` | GitHub merge evidence | accepted durable output |
| `PR_CLOSED_UNMERGED` | GitHub close evidence | unmerged close |

`DISPATCHED` / `ACKED` は実装開始へ昇格しない。`EXECUTION_EVIDENCE` が最初のimplementation-start evidenceである。

## Stable identity / rerun

入力eventは `event_id`、または `kind + ref + timestamp` からstable identityを作る。同一identityは1回だけ集計する。同じday/schema/evidenceを再実行してもsemantic countは増えない。

executorとtask_classは `(executor, task_class)` の組を保持し、異なるprovider/task classを推測で統合しない。

## UNKNOWN / null / zero

`null` は未取得・観測不能、`0` は観測した結果ゼロ。collectorが未観測のcredits/cost/lead timeを0へ丸めない。UNKNOWNをPASSへ昇格しない。

## Late evidence / correction

close後に対象日へ帰属するdurable evidenceを検出した場合、過去snapshotの意味をsilent rewriteしない。stable late-event identityからcorrection IDを生成し、`reason / evidence_refs / recorded_at` を持つcorrection audit recordを最大1件追加する。同じlate evidenceの再処理でcorrectionを重複させない。

## Validation / persistence

#725 schemaをsole validation authorityとして使用する。collector内にrequired-field schemaを複製しない。snapshot全体をschema validationしてから一時ファイルへ書き、atomic replaceする。validation failure時は既存daily fileを変更しない。

runtime persistence targetは `data/development-diary/YYYY-MM-DD.json`。PR fixtureとして日次生成物は追加しない。

## Safety boundary

Factory Capability Changeの`PROVEN`をcollectorが合成しない。source evidenceがない能力変化は作らない。Pages、workflow、monthly rollup、TEAM_STATE/TEAM_RULES、routing policy、BUY/SELL/HOLD等のInvestment Authority logicはこのsliceの対象外。Issue #79 untouched。
