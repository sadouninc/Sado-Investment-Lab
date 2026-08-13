# Productivity Baseline Dataset v1

担当: 🤖カイ  
種別: Productivity Measurement / Methodology  
関連Issue: #540  
Collector: #506 / PR #528

## 目的

Sado Investment Labの実PR事例を同じTelemetry schemaへ正規化し、今後の改善前後を比較するための初回Baselineを作る。

このDatasetはメンバーやAgentのランキング、因果推論、能力評価には使用しない。現時点の4事例はいずれも部分的なEvidenceしかないため、全件を `evidence_quality: PARTIAL` とする。

## 対象事例

| Case | Class | Durable evidence |
|---|---|---|
| `stale-base-472` | STALE_BASE / MERGE_CONFLICT | PR #472のblocking review、superseded記録、clean follow-up #482 |
| `duplicate-owner-475` | DUPLICATE_WORK / OWNER_CONFLICT | PR #475のSingle Owner conflict記録、authoritative PR #476 |
| `false-ready-483` | FALSE_READY / HARNESS_GAP | PR #483のfalse-positive REVIEW_READY対策contract |
| `normal-control-504` | NORMAL / LOW-RISK CONTROL | PR #504のintegration review、Design Gate、CI成功記録 |

## Evidence policy

- GitHub上のPR本文、恒久コメント、review URLのみを `source_refs` として使用する。
- チャット記憶や推測値は使用しない。
- timestampが取得できない場合は `null` のまま残す。
- merge/closeの明示Evidenceをfixtureへ固定していないため、`result` は `UNKNOWN` とする。
- clarificationとhuman confirmationはexplicit eventがないため0件。
- review reworkはrequestと対応するexplicit fix roundがない限り0件。
- queued / skipped / cancelled / neutral等をCI failureへ変換しない。
- `FALSE_READY`、`superseded`、`stale base / merge conflict` は明示Evidenceがある事例だけに付与する。

## 再生成

```powershell
python scripts/build_productivity_baseline.py tests/fixtures/productivity_baseline_v1.json data/generated/diagnostics/productivity_baseline_v1.jsonl
```

同じfixtureから同じJSONLが生成されることをテストで確認する。

## 制約

このBaselineは初回sampleであり、Productivity改善の効果や原因を断定できない。追加caseの収集後も、Evidence qualityと欠損値を保持して比較する。
