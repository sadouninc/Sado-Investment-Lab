# Development Diary daily close collector v1

担当: ♦️ソラ  
種別: Implementation Contract / Evidence Normalization  
Issue: #730  
Schema Authority: #725 / `data/contracts/development-diary-daily-v1.schema.json`

## 目的

前日JST 00:00–24:00の**durable GitHub / SM evidence**を決定論的に正規化し、Development Diary daily schema v1へ投影するcollectorを定義する。

このsliceはcollector / validation / persistenceだけを担当する。00:10 JSTのscheduler、Pages、monthly rollup、routing policyは別責務であり、本実装には含めない。

## Authority boundary

- snapshotの構造・required field・型・非負制約は、merged #725 schemaだけを正とする。
- collector側に第二schemaを持たない。
- `DISPATCHED` / `ACKED` は予約状態であり、実装開始へ昇格しない。
- `EXECUTION_EVIDENCE` がdurable implementation startの最初の証拠。`PR_OPEN` / `PR_MERGED` はそれより強いdurable outputとして別metricへ保持する。
- 未観測値は`null`。観測した0だけを`0`にする。
- `Factory Capability Change.validation_status` は入力authorityを保持し、collector自身が`PROVEN`へ昇格させない。
- BUY / SELL / HOLD、Investment Authority、AUTO_GREEN activationは生成しない。
- Issue #79はhard deny / untouched。

## Normalized evidence contract

collectorはprovider固有API responseを直接truthへ変換せず、stable identityを持つnormalized durable evidenceを入力にする。

最低限:

```json
{
  "event_id": "pr:735:merged",
  "kind": "PR_MERGED",
  "occurred_at": "2026-08-19T18:56:05+09:00",
  "executor": "SORA",
  "task_class": "IMPLEMENTATION"
}
```

`event_id`は再実行時にも同一eventを指すstable identityでなければならない。同一run内のduplicate identityは1回だけ集計する。

対応kind:

- `READY`
- `DISPATCHED`
- `ACKED`
- `EXECUTION_EVIDENCE`
- `PR_OPEN`
- `PR_MERGED`
- `PR_CLOSED_UNMERGED`
- `TERMINAL_NOOP`
- `REWORK`
- `DUPLICATE_CONFLICT`
- `PATH_OWNER_CONFLICT`
- `CI_STALL`
- `BLOCKED_ESCAPE`
- `HUMAN_INTERVENTION`
- `FACTORY_CAPABILITY_CHANGE`

未知kindはfail-closedで拒否する。

## JST source window

`diary_date_jst`のsource windowはhalf-open:

```text
[YYYY-MM-DD 00:00:00 JST, next-day 00:00:00 JST)
```

したがって23:59:59 JSTは対象日、翌00:00:00 JSTは次日。default close時刻は翌00:10 JST。

## Executor × task_class

performance rowは `(executor, task_class)` をkeyとして保持する。同一executorでもtask classが異なれば別rowとし、恣意的に結合しない。これは外部executor比較やtask fitを後から検証できるようにするため。

## Reservationと実装開始

TEAM_STATEのactive WIP contractを維持する。

```text
DISPATCHED → reservation only
ACKED → reservation only
EXECUTION_EVIDENCE → implementation start
PR_OPEN → durable PR evidence
PR_MERGED → accepted durable output
```

`DISPATCHED` / `ACKED`しか存在しない日は`implementation_start_count`を増やさない。

## Late evidence / correction

既にclose済みsnapshotへ、対象日のeventが後から観測された場合はsilent rewriteしない。

late eventには`observed_at`を持たせ、既存snapshotの`closed_at_jst`より後なら、stable `event_id`からcorrection identityを生成して`corrections[]`へ追加する。同じlate eventを再度入力してもcorrectionは1件のまま。

例:

```json
{
  "event_id": "pr:999:merged",
  "kind": "PR_MERGED",
  "occurred_at": "2026-08-19T23:00:00+09:00",
  "observed_at": "2026-08-20T00:20:00+09:00",
  "evidence_refs": ["pr:#999"],
  "correction_reason": "late merge evidence"
}
```

既存aggregateを暗黙に書き換えるのではなく、correction auditを残す。

## Persistence

runtime defaultは `data/development-diary/YYYY-MM-DD.json`。PR fixtureとしてdaily generated dataは追加しない。

`persist_snapshot()`は**完全snapshotをschema validationしてから**一時ファイルへ書き、`os.replace`で置換する。validation failure時は既存fileを変更しない。

## CLI

normalized evidence JSON arrayを入力する。

```bash
python scripts/development_diary_collector.py \
  --diary-date 2026-08-19 \
  --evidence /path/to/evidence.json
```

出力先省略時は `data/development-diary/2026-08-19.json`。late evidence reconciliationでは`--existing`に既存snapshotを渡す。

## Acceptance mapping

- JST 23:59:59 / 翌00:00:00 boundary → focused test
- duplicate stable identity → deterministic rerun test
- DISPATCHED / ACKED ≠ implementation start → focused test
- EXECUTION_EVIDENCE → executor×task_class lossless test
- unavailable economics=null / observed zero=0 → focused test
- late evidence replay → exactly one correction
- invalid snapshot → prior persistence unchanged
- schema metadata → merged #725 schema loader test

Issue #79 untouched。actual AUTO_GREEN executionはOFFのまま。
