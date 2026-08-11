# Git-Native Agentic Runtime Architecture

> Issue #349 — Canonical Runtime Architecture Doc / PR1
>
> 担当: 🌊ナギ  
> 種別: Architecture / Runtime / Documentation  
> Last reviewed: 2026-08-11

## 30秒要約

Sado Investment Labは、常駐Application Serverを中心に置くのではなく、**GitHub上の永続状態・Issue/PR・Actions・履歴をoperating substrateとして使い、必要な時だけAI Agentとdeterministic logicが起動するInvestment OS**として構成されている。

```text
Input / Event
   ↓
AI Semantic Interpretation
   ↓
GitHub上の提案・永続状態
   ↓
Review / CI / Merge
   ↓
Deterministic Logic / Read Model
   ↓
Pages / Cockpit
   ↓
👑 Owner judgment
   ↓
Next Event
```

重要なのは、**AIが投資判断のAuthorityになるわけではない**こと。AIは意味付け・整理・提案を担い、検証可能な処理はdeterministic logicへ分離し、投資思想・risk threshold・最終BUY/SELL等のOwner Authorityは👑サドに残る。

---

## 1. この文書の責務

この文書は「Investment OSの裏側がどう動くか」を説明するRuntime viewである。

- `SADO_INVESTMENT_CODEX_SITEMAP.md` / #324: Codex全体の建築状態・Build Order
- #309: Investment OS / Information Architecture
- #320: Pages Visual Design System
- #314: Global Navigation
- **本書 / #349: Event → Agent → Git → Logic → Read Model → Human のRuntime Architecture**

旧Architecture Issue #47 / #142 / #152の設計史は参照対象だが、現行のRuntime SSoTを複数作らない。

---

## 2. CURRENT — 現在確認できるRuntime Model

### 2.1 Human / External Input

現在の入力は一つの巨大API gatewayへ集約されていない。入力種別ごとにGitHub上のCanonical state / Research / Issue / operational artifactへ接続される。

代表例:

- 👑 Ownerの判断・要求・設計Authority
- Market / Portfolio / Research input
- Company Research (`03_Companies`)
- Framework / operating rules (`00_Framework`, `TEAM_RULES.md`)
- Issue / PR / commit / merge event
- scheduled / workflow execution

Inputが存在したことと、その内容がVerified Factであることは同義ではない。

### 2.2 AI Semantic Layer

AI Agentは必要時に起動し、主に次を担う。

- raw inputの意味理解
- relevance / scope整理
- Fact / Interpretation / Hypothesisの分離
- Issue化・設計・実装・レビューhandoff
- provenance / Authority不足の明示
- Owner判断が必要な項目のescalation

**Agent conversation memory自体をPrimary SSoTにしない。** 継続作業に必要な仕様・成果物・handoffはGitHubへ残す。これは`TEAM_RULES.md`のGitHub-complete Handoff Ruleに従う。

### 2.3 GitHub Operating Substrate

GitHubは単なるsource code storageではなく、Runtimeの複数責務を担う。

| GitHub primitive | Investment OSでの意味 |
|---|---|
| files / Git | durable Canonical state / rules / research / code |
| Issue | unresolved work / design / decision / coordination state |
| branch | isolated proposed change |
| commit | versioned state transition |
| PR | review可能なstate transition proposal |
| review | Authority / quality / design / implementation validation |
| CI / Actions | deterministic validation / build / publish reaction |
| merge | accepted software/data/document transition |
| SHA / history | audit / reproduction point |
| Pages | safe derived projection / human-facing read model |

`merge = BUY/SELL承認`ではない。Mergeはsoftware/data/document stateの受理であり、投資判断のOwner Authorityとは別。

### 2.4 Deterministic Logic Layer

`scripts/*`, `.github/pages/*`, validators, builders, tests等は、AI Semantic Layerと区別する。

現在確認できる例:

- Pages builder / presentation generation
- navigation contractのpublish
- Company Researchからsummary-first Company Cardsへのderived projection
- validators / regression tests / PR Preflight
- GitHub Actionsによるbuild / publish

原則:

```text
AI: 意味・文脈・候補・説明
Deterministic logic: 計算・schema validation・build・再現可能な変換
```

AIの推論をdeterministic factへ暗黙昇格させない。

### 2.5 Canonical State / Knowledge

Canonical stateは一つのDBへ統合せず、責務ごとのAuthorityを維持する。

```text
Knowledge / Rules   00_Framework, TEAM_RULES.md, Research Markdown
Portfolio           Canonical portfolio artifacts
Company Research    03_Companies
Machine state       data/*
Execution           scripts/* / .github/*
Operations          Ops/*
```

Derived artifactはCanonical inputを書き換えない。

### 2.6 Derived / Read Model Layer

Pages / Cockpit / generated public dataは、Canonical stateを人間が速く判断できる形へ変換するprojectionである。

例:

- Home / OS Map
- Company Cards
- Decision Cockpit
- Morning / diagnostic views
- generated public artifacts

失敗・欠損・staleを「正常」「最新」と見せない。取得不能はUNKNOWN / UNAVAILABLE等として明示する。

### 2.7 Human Decision Loop

Runtimeの終点は自動BUY/SELLではなくHuman-in-the-loop。

```text
Pages / Cockpit
   ↓
👑 Ownerが確認
   ↓
判断 / 質問 / 変更要求 / Trade Intent
   ↓
Next Event
```

Owner Authorityが必要な項目をAgentやCIが勝手に確定しない。

---

## 3. CURRENT Event Flow

```text
👑 Owner / Market / Research / Portfolio / GitHub event
                         │
                         ▼
                 AI Semantic Layer
          意味理解 / Fact分離 / scope整理
                         │
                         ▼
              GitHub Operating Substrate
       Issue / files / branch / commit / PR
              │                    │
              │                    └─ review / CI
              ▼
          accepted merge
              │
      ┌───────┴────────┐
      ▼                ▼
Canonical State   Deterministic Logic
      │                │
      └────────┬───────┘
               ▼
          Derived Read Model
               │
               ▼
          Pages / Cockpit
               │
               ▼
            👑 Owner
               │
               └────────→ Next Event
```

この図は責務を示す。すべてのイベントが必ず全layerを通るという意味ではない。例えば軽微なdocument correctionとmarket-data derived buildでは経路が異なる。

---

## 4. GitをState Machineとして使う

```text
State N
  ↓ raw change / new evidence / new requirement
Proposed change
  ↓ branch + commit
PR
  ↓ review + CI + Authority checks
Accepted / rejected
  ↓ merge when accepted
State N+1
```

### diff

`diff`は「前状態から何が変わったか」を明示する。研究・rule・codeのsilent overwriteを避け、レビュー可能にする。

### SHA

SHAは再現可能な過去時点のanchorになる。将来のreplay / historical reconstructionでは、Canonical stateだけでなく、その時点のlogic versionも重要になる。

### IssueとPRの分離

- Issue = 何を変える必要があるか / unresolved state
- PR = その変更をどう実体化するか / proposed transition

Issue CloseのみでPagesやRuntimeが完成したと判断しない。

---

## 5. Authority / Safety Boundary

### AIがしてよいこと

- fact candidate / interpretation / hypothesisを分離して提示
- evidence不足を明示
- deterministic処理へ渡すstructured inputを準備
- implementation / review / design proposalを作る
- unresolved Owner Authorityを返す

### AIがしてはいけないこと

- 推論をverified factとしてsilent promotion
- Owner risk thresholdを推測して固定
- BUY / SELLをOwner承認なしに最終確定
- missing dataを都合よく補完
- chat-only artifactをチームの唯一のhandoffにする

### Public / Secret境界

- API key / secretをCanonical public stateやPagesへ出さない
- Pagesはpublic-safe derived projectionのみ
- operational secretと投資研究のpublic projectionを分離する

### CIの意味

CI greenは「software/document contractに対して検証が通った」ことを意味する。

**CI green ≠ 投資判断が正しい。**

---

## 6. Versioned Input Mechanism — 観測方法そのものをGit管理する

Investment OSではデータだけでなく、**何を観測するか・どう解釈へ渡すか・どのvalidator/buildへ流すか**もversion controlledにできる。

CURRENTですでにGit管理対象になっているもの:

- Team / Authority rules
- workflow / build behavior
- scripts / validators
- Pages presentation contracts
- data/config等のdeterministic configuration

これにより新しいsignal typeが必要になった時、観測機構を変更してreviewできる。

```text
New signal requirement
   ↓
sensor / rule / config / agent contract proposal
   ↓
branch / PR
   ↓
review / validation
   ↓
merge
   ↓
以後のOSが新しい観測dimensionを持つ
```

---

## 7. CURRENT と EVOLUTION を混同しない

### CURRENT

実在をrepository / Issue / PR / Actionsで確認できるもの。

- GitHub-native state / review / CI workflow
- Canonical files / Research / config
- deterministic scripts / validators / builders
- Pages derived projection
- AI Agentによる意味解釈・handoff
- Human final judgment

### EVOLUTION

Architecture上は価値があるが、本書PR1時点で「完成済み」と扱わないもの。

- external event sourceからのより広い自動trigger
- historical replay engine
- counterfactual simulation
- runtime-wide event ledger
- fully automated provenance propagation
- multi-agent orchestrationの一般化

Future architectureをCurrent実装のように図示しない。

---

## 8. Replay / Reproduction Property

Git-native構造は、将来次の2種類を分離して検証できる余地を持つ。

```text
Past Canonical State + Past Logic
→ 当時のdecision contextを再現

Past Canonical State + New Logic
→ 新logicならどう見えたかをreplay / counterfactual比較
```

ただし#349 PR1ではReplay Engineを実装しない。

再現性の前提:

- Canonical stateのversionが残る
- logic/configのversionが残る
- input provenanceが追える
- decision-time snapshotを後知恵でsilent rewriteしない

---

## 9. Architecture Planesとの関係

#324で扱うCodex / Repository architectureとRuntime viewを重ねると、次のようになる。

```text
Knowledge      00_Framework / 01_Portfolio / 02_Themes / 03_Companies / ...
Machine        data/*
Execution      scripts/* / .github/workflows / .github/pages
Operations     Ops/*
Presentation   site-src / GitHub Pages

Runtime        Event → Agent → Git → Logic → Read Model → Human
```

Planeは「どこに何を置くか」、Runtimeは「状態がどう流れるか」を説明する。両者を一つの巨大diagramへ無理に統合しない。

---

## 10. Related Architecture

- `../SADO_INVESTMENT_CODEX_SITEMAP.md` — Codex Sitemap / Evolution Roadmap (#324)
- `../../TEAM_RULES.md` — change flow / Authority / GitHub-complete handoff
- #309 — Sado Investment OS overall architecture
- #320 — canonical Pages Design System
- #314 — Global Navigation Authority
- #349 — this Runtime Architecture work

Historical / superseded architecture discussions (#47 / #142 / #152)は設計史として参照し、現行SSoTを増やさない。

---

## 11. Next slices

### PR2 — Diagrams

この文書をAuthorityとして、以下をdiff/reviewしやすいdiagramへ落とす。

1. Runtime Architecture
2. Git as State Machine
3. Versioned Input / Self-evolving Observation

図にはaccessible text explanationを必ず併設する。

### PR3 — Pages view

#320 Design Systemを再利用してPagesから閲覧可能にする。新しい独自themeは作らず、⭐️ミナDesign Reviewを通す。

---

## Definition of Done for PR1

この文書を読んだ人が、次を説明できればPR1は完了。

1. なぜ常駐server中心でなくてもLabが動くのか
2. GitHubが何を担うのか
3. AI Semantic Layerとdeterministic logicの違い
4. Canonical stateとderived projectionの違い
5. Owner Authorityがどこに残るか
6. CURRENTとEVOLUTIONの境界
7. なぜGit historyが将来のreproduction / replayに効くのか
