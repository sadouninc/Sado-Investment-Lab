# AI開発組織の進化 — Evidence Record

担当: 🌊ナギ  
種別: Engineering History / Productivity Evidence  
関連Issue: #675  
Status: Evidence collection / living record

## この記録の目的

Sado Investment Labでは、ChatGPTチームが直接実装・レビューする比重の高い体制から、🌊ナギをSingle Flow AuthorityとするControl Plane、Copilotによるbounded implementation、Amazon Qによる独立Technical/Flow verification、GitHub Actionsによるmechanical verificationを組み合わせる体制へ段階的に変化している。

この文書は、その変化を後から美化して物語化するためのものではない。GitHub上のIssue、PR、commit、workflow run、comment、timestamp、Flow telemetryから、**誰が何を決め、AIが何を観測し、どのprocess adaptationを行い、その前後でdelivery performanceがどう変わったか**を再現可能に残すためのEvidence Recordである。

## まず分離するもの

### Human-originated direction / Authority

人間が与えたGoal・Authority・Safety境界は、AI側の自己判断と混同しない。

- GitHubをSSoTとして運用する。
- ユーザーの逐次指示を減らし、安全に自律前進できる体制を目指す。
- Investment / Owner Authorityは人間に残す。
- actual AUTO_GREEN executionはActivation Gate完了までOFFとする。
- required CI / review / Authorityを省略しない。
- 明示的なuntouched対象などSafety constraintを守る。

### AI-observed / AI-adapted process

以下はGitHub evidenceで確認できる場合だけ「AI側のprocess adaptation」として扱う。

- global Flow scan / routingをSingle Flow Authorityへ集約する。
- open PR数とactive implementation WIPを分離し、waiting workでcapacityを塞がない。
- READY workがあるのにactive WIPがない状態をQueue Starvationとして検出・routingする。
- persistent dispatch leaseでAgent ownershipを期限付きにする。
- Copilot implementationをHarness / Follow-up / Patch Promotionへ接続する。
- duplicate dispatchを検出し、不要なpaid Copilot sourceを起動しない。
- production failureをimplementation failureとinfrastructure failureへ切り分け、blocker escape後に元workへ復帰する。
- reviewをRisk/Scope-drivenにし、scope外specialist gateを常時blockingにしない。

これは「AIが自由意思で組織を変更した」という主張ではない。**人間が定めたGoal / Authority / Safetyの範囲で、AIがFlow evidenceを観測し、processを適応し、productionで検証した**という記録である。

## Before → Current

### Before: ChatGPTチーム中心の直接作業

```text
Human
  ↓
ChatGPT Team
  ├─ Flow / planning
  ├─ implementation
  └─ review
  ↓
PR / CI
  ↓
Human Merge
```

この段階ではChatGPT担当間の直接handoffと、人間からの開始・merge指示の比重が相対的に高かった。

### Current: 複数AIを組み込んだ5-plane model

```text
Human Authority Plane
 Goal / Authority / Safety / final merge
              │
              ▼
ChatGPT Control Plane
 🌊ナギ = Single Flow Authority
 Flow observation / priority / routing / RCA
              │
      ┌───────┴────────┐
      ▼                ▼
Copilot             ChatGPT specialists
Execution Plane     Product / Research / RCA
bounded work
      │
      ▼
GitHub Actions Mechanical Verification Plane
Harness / CI / Follow-up / Patch Promotion
      │
      ▼
PR ───────────────► Amazon Q Independent Verification Plane
      │             independent Technical / Flow evidence
      └───────────────┬─────────────────────
                      ▼
                 Human Merge
```

Amazon QとChatGPTはalternative PR routesではない。同じdelivery flowに対して異なる責務を持つplaneである。

## 2026-08-16 — Productivity inflection hypothesis

### contemporaneous user observation

2026-08-16後半、ユーザーから「明らかに今日後半になって生産性が上がってきている気がする」という観測があった。

これは重要な一次観測として保存するが、**測定結果や因果結論とは分離する**。

### Hypothesis

2026-08-16後半にdelivery throughputまたはdurable-output cadenceが改善している可能性がある。その変化が確認できた場合、Copilot / Amazon Qというworker追加だけでなく、Single Flow Authority、lease、Harness、Promotion、duplicate suppression、BLOCKED_ESCAPE、Risk/Scope-driven reviewなどの運用成熟と時間的に対応しているかを検証する。

1日分のsampleだけでcausalityは主張しない。

## Measurement contract

既存の `docs/platform/ai-productivity-metrics.md` と `docs/platform/productivity-baseline-v1.md` を再利用し、別の都合の良い指標体系を作らない。

主要指標:

| 観点 | Metric | Guard |
|---|---|---|
| Throughput | merged PR / period | PR数だけを生産性としない |
| Throughput | completed Issue / period | close without meaningful outputを区別 |
| Flow cadence | durable output / period | durable output定義を固定する |
| Flow cadence | median / p90 durable-output interval | timestamp evidenceのみ |
| Lead time | READY → implementation start | anchor不明はUNKNOWN |
| Lead time | implementation → PR ready | 同一source priorityを使用 |
| Review | PR ready → merge / reviewer wait | waitingとimplementationを混同しない |
| Rework | CI failure / reviewer rework | speedのための品質低下を検出 |
| Flow | Queue Starvation / BLOCKED_ESCAPE | structured evidenceのみ |
| Agent cost | duplicate source run / suppressed duplicate | duplicate抑止を速度と別表示 |
| Human load | Owner intervention / completed unit | 観測不足はUNKNOWN |

### Durable output v0 — #675 analysis用

このPages分析で「成果物」を恣意的に増やさないため、少なくとも次を別categoryとして数える。

- `MERGED_PR`
- `PRODUCTION_ACCEPTANCE`
- `PR_HANDOFF`
- `BLOCKER_REPAIR_MERGED`
- `EFFECT_CONFIRMED`

同じ出来事を複数categoryで二重に総数加算しない。primary categoryとsupporting evidenceを保持する。

## 2026-08-16 timelineで確認する代表Evidence

本文完成時には各Issue/PR/workflowを再取得し、timestampと因果関係を確定する。候補:

- AI Production Follow-up / Patch Promotionのproduction chain成立
- #661 / PR #662: productionで見つかったPromotion障害の修復
- #664: terminalization hardeningとOwner介入なしPR到達acceptance
- #668 / PR #670: duplicate redispatch suppression
- PR #671: #550 PR1 Contract / Taxonomy hardening
- #626: Copilot implementation / Harness後のPromotion anomaly
- #672 / PR #674: declarative acceptanceをcommand実行しないhardening
- #645: SM Flow Validation Ledger

## Case study pattern

#626系の事例では、次のfeedback loopをEvidence付きで再構築する。

```text
Work routed
   ↓
Copilot implementation
   ↓
Harness validation
   ↓
Production anomaly
   ↓
🌊ナギ Flow/RCA judgment
   ↓
implementationを盲目的retryしない
   ↓
infrastructure blockerへBLOCKED_ESCAPE
   ↓
repair implementation / review / CI / merge
   ↓
original workへresume
```

このloopは「失敗しなかった」ことではなく、**失敗を検出した後の回復経路が短く、別workへcapacityを解放し、再発防止をdurable outputにできたか**を評価する。

## Pagesで作る可視化

1. **Evolution Timeline** — process adaptation eventとdurable outputを同一時間軸に置く。
2. **Before / After cards** — architecture、human intervention、throughput、lead time、quality guard。
3. **Cumulative Durable Outputs** — 時間に対する累積成果物。後半で傾きが変わったかを見る。
4. **Human vs AI Decision Matrix** — Goal/AuthorityとFlow adaptationの境界を可視化する。
5. **Observe → Decide → Route → Execute → Verify → Adapt loop** — AI-native process improvement cycle。

## Interpretation guard

Pagesでは必ず以下を区別する。

- `Observed fact` — GitHub timestamp / state / workflow evidence
- `User observation` — その時点で人間が感じた変化
- `Measured result` — 固定metricから計算した値
- `Interpretation` — process eventとの時間的対応
- `Causal claim` — 十分な反復sampleがある場合のみ

`correlated with` / `consistent with` と `caused by` を混同しない。

## Safety / Quality guard

速度だけを成功条件にしない。throughput改善と同時に以下が悪化していないことを確認する。

- required CI / Harness failureとrework
- duplicate paid source runs
- scope deviation
- review blocker / review wait
- unsafe AUTO_GREEN execution
- Owner / Investment Authority violation

UNKNOWNは0やPASSへ変換しない。

## Next evidence work

- 2026-08-16 JSTのPR / Issue / workflow timestampsを収集する。
- 前半/後半の境界は結果に合わせて恣意的に決めず、主要process adaptation時刻を併記する。
- #645 ledgerから取得可能なFlow telemetryを抽出する。
- cumulative durable outputsとBefore/After tableを生成する。
- 1日sampleと、その後の日次/週次追跡を分離する。
- Pages navigationへ掲載する際は日本語ファースト・mobile readableとする。
