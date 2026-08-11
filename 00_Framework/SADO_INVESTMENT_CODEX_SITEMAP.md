# Sado Investment Codex — Sitemap & Evolution Roadmap

> Canonical architecture/status document for Issue #324.
>
> Purpose: show the target Codex structure, the current build state, the next build order, and planned evolution without treating Issue state itself as product completion state.

- Architecture version: v1.1-route-verification
- Last reviewed: 2026-08-11
- Source authority: repository state + GitHub Issue/PR state + reviewed architecture decisions
- Status rule: route/page existence must be verified independently; an open/closed Issue is never copied mechanically into page status.
- Reachability rule: repository artifact existence and user reachability are separate checks. `LIVE` requires a verified published route plus a verified user entry path; an orphan artifact is not `LIVE`.

## 1. Current snapshot

### NOW

- Canonical Pages design-system foundation is in production use on Home.
- Home / OS Map is user-reachable at `/` and already exposes verified entries into Company Research, Decision Cockpit, Risk Preflight, Trade Journal, and research tools.
- Existing Investment OS knowledge/data/runtime layers remain authoritative; this document is a roadmap/status view, not a new investment-data SSoT.

### IMPLEMENTATION BUILD ORDER

This is the team implementation dependency order. It is the answer to **“what should implementation pick up next?”**

1. Remaining Home / OS Map refinement (#312)
2. Concept architecture + Cockpit concept (#313, #317)
3. Global navigation stabilization (#314)
4. Practical decision UX (#307, #308)
5. Money Flow daily operationalization (#305)

### NODE-LOCAL NEXT

`NEXT` inside the node/evolution registry means **the next meaningful change for that node**, not the globally next implementation assignment. This prevents Product evolution priority from competing with the team implementation queue.

### LATER

- Decision Journal / history finalization, including #316 zero-trade / `NOT_EXECUTED` projection and reachability
- Review / Learning hierarchy
- Remaining high-value Concept pages
- Backend Runtime Architecture visualization (#349)

The order above is dependency-aware, not frozen. Existing IMPLEMENTING work should not be interrupted merely to satisfy this document.

## 2. Status vocabulary

| Status | Meaning |
|---|---|
| `LIVE` | Published user-accessible page or major feature is verified to exist **and is reachable from a verified user entry path** |
| `DONE` | Design/doc deliverable is complete |
| `BUILDING` | Implementation is actively underway |
| `DESIGNED` | Contract/design exists; implementation is not yet verified complete |
| `NEXT` | Node-local next meaningful evolution item; not the global implementation queue |
| `PLANNED` | Intended future work |
| `IDEA` | Early concept, not committed |
| `BLOCKED` | Explicit blocker exists |
| `DEFERRED` | Intentionally postponed |
| `RETIRED` | Superseded or removed |

`LIVE` and `DONE` are intentionally different. A closed Issue does not imply either status.

## 3. Target Sitemap

```text
HOME
│
├─ CODEX MAP / OS OVERVIEW
│   │
│   ├─ 1 Observe / 観測
│   │   ├─ Market Intelligence
│   │   ├─ News / Daily Context
│   │   └─ Money Flow
│   │
│   ├─ 2 Discover / 発見
│   │   ├─ Candidate Selector
│   │   └─ Developing Signals
│   │
│   ├─ 3 Understand / 理解
│   │   └─ Company Research
│   │
│   ├─ 4 Hypothesize / 仮説
│   │   ├─ Investment Hypothesis
│   │   ├─ Earnings Engine
│   │   └─ Bear / Base / Bull
│   │
│   ├─ 5 Decide / 判断
│   │   ├─ Cockpit Concept
│   │   └─ Company Decision Cockpit
│   │
│   ├─ 6 Act / 行動
│   │   ├─ Trade Intent
│   │   ├─ Portfolio Preflight
│   │   └─ Execute / Pass
│   │
│   ├─ 7 Record / 記録
│   │   ├─ Decision Journal
│   │   └─ Decision Snapshot / History
│   │
│   ├─ 8 Learn / 振り返り
│   │   ├─ Decision Review
│   │   ├─ Learning / Pattern Lab
│   │   └─ Investment Episode
│   │
│   └─ 9 Re-observe / 再観測
│       └─ Market / Checkpoint loop
│
├─ PORTFOLIO
├─ INVESTMENT TIMELINE / CHECKPOINTS
├─ CONCEPT / HOW-TO
└─ ARCHITECTURE
    ├─ Investment OS / Repository Architecture
    └─ Backend / Runtime Architecture (#349)
```

This is the target information architecture. A node is not considered live until its actual route/artifact and user reachability have both been verified.

## 4. Node registry

Evidence basis for verified routes in this revision: merged Home adoption PR #343 and Company Cards integration PR #375.

| Node ID | Display name | Stage | Page status | Concept status | Route | Reachability evidence | Related issues | Next change |
|---|---|---:|---|---|---|---|---|---|
| `global.home` | Home | Global | `LIVE` | n/a | `/` | root permalink / primary entry | #312 | Continue Home read-model refinement without creating Home-only truth |
| `global.codex-map` | Codex Map / OS Overview | Global | `LIVE` | n/a | `/` | embedded in Home Investment OS map | #312, #309 | Keep status/context aligned with real user journey |
| `global.navigation` | Global Navigation | Global | `DESIGNED` | n/a | null | route taxonomy not independently verified as complete | #314 | Stabilize after major concept links settle |
| `global.concept` | Concept / How-to Architecture | Global | `DESIGNED` | `DESIGNED` | null | no standalone route verified in this slice | #313 | Add only high-value explanatory Concept nodes |
| `observe.money-flow` | Money Flow | 1 Observe | `PLANNED` | `DESIGNED` | null | detector capability != verified daily Pages surface | #305, #112 | Move to dependable daily operating surface |
| `discover.candidates` | Candidate Selector | 2 Discover | `DESIGNED` | `DESIGNED` | null | artifact/route not independently verified in this slice | #108 | Verify presentation route before LIVE |
| `understand.company-research` | Company Research | 3 Understand | `LIVE` | `DESIGNED` | `/companies/` | Home primary entry + #375 published Companies index | #113, #36 | Expand canonical research coverage using existing #320 primitives |
| `hypothesize.thesis` | Investment Hypothesis | 4 Hypothesize | `DESIGNED` | `DESIGNED` | null | no user-reachable dedicated surface verified | #130, #313 | Connect evidence and monitoring-ready hypothesis contract |
| `hypothesize.valuation` | Earnings / Bear-Base-Bull / Forward PER | 4 Hypothesize | `DESIGNED` | `DESIGNED` | null | no dedicated reachable route verified | #117, #313 | Make scenario provenance visible in decision flow |
| `decide.cockpit` | Investment Decision Cockpit | 5 Decide | `LIVE` | `NEXT` | `/decision-cockpit/daihen/` | Home primary entry / Today entry | #317, #308 | Node-local NEXT: Cockpit Concept + prior/current/delta context |
| `act.trade-intent` | Trade Intent | 6 Act | `PLANNED` | `DESIGNED` | null | not verified as user surface | #307 | Define practical transition from decision to intended action |
| `act.preflight` | Portfolio Preflight | 6 Act | `LIVE` | `DESIGNED` | `/risk-preflight/` | Home primary entry / Today entry | #307, #313 | Connect intent semantics without changing canonical portfolio authority |
| `record.decision-journal` | Decision Journal / Snapshot / History | 7 Record | `LIVE` | `DESIGNED` | `/trade-journal/` | Home primary entry; final semantic/reachability slice still tracked by #316 | #133, #316 | Preserve `0 trades != 0 decisions`, `NOT_EXECUTED != PASS`; finalize 2026-08-10 projection/index reachability |
| `learn.review` | Decision Review | 8 Learn | `DESIGNED` | `PLANNED` | null | no dedicated reachable surface verified | #141 | Clarify review priority and evidence-delta drill-down |
| `learn.pattern-lab` | Decision Pattern Lab | 8 Learn | `DESIGNED` | `PLANNED` | null | no dedicated reachable surface verified | #135 | Broaden learning beyond trade-only analysis |
| `reobserve.checkpoints` | Catalyst / Checkpoint Timeline | 9 Re-observe | `PLANNED` | `PLANNED` | null | no route verified | #130, #141 | Close loop back into observation/review |
| `architecture.runtime` | Git-Native Agentic Runtime Architecture | Architecture | `DESIGNED` | n/a | null | canonical runtime doc not yet implemented | #349 | PR1 canonical runtime doc, then diagrams; Pages later |

## 5. Build Order

```text
#312 Home / OS Map remaining refinement
  ↓
#313 Concept architecture + #317 Cockpit Concept
  ↓
#314 Global Navigation stabilization
  ↓
#307 / #308 practical decision UX
  ↓
#305 Money Flow daily operations
```

Rules:

1. Existing `BUILDING` work is not pre-empted by this document.
2. Global implementation order is expressed only in this section / Current snapshot.
3. Node-registry `NEXT` is node-local Product evolution, not assignment order.
4. Dependency or Owner decisions may reorder the baseline.
5. Any reorder should update this document rather than silently diverging.

## 6. Evolution registry

| Change ID | Node | Status | Summary | Issue | Priority |
|---|---|---|---|---|---|
| `decide.cockpit.concept` | `decide.cockpit` | `NEXT` | Node-local: explain the Cockpit purpose and use | #317 | High |
| `decide.cockpit.delta` | `decide.cockpit` | `PLANNED` | Show previous → current → delta for important decision context | #308 | High |
| `record.journal.zero-trade` | `record.decision-journal` | `NEXT` | Preserve zero-trade day, `NOT_EXECUTED`, and index/user reachability in the final journal slice | #316 | High |
| `act.intent-preflight` | `act.trade-intent` / `act.preflight` | `PLANNED` | Connect decision to trade intent and portfolio preflight | #307 | High |
| `observe.money-flow.daily` | `observe.money-flow` | `PLANNED` | Turn Money Flow into a dependable daily operational input | #305 | High |
| `architecture.runtime.current` | `architecture.runtime` | `PLANNED` | Document CURRENT runtime model before future-state diagrams | #349 | High |
| `architecture.runtime.diagrams` | `architecture.runtime` | `PLANNED` | Add Runtime, Git State Machine, and Versioned Input diagrams | #349 | Medium |

## 7. Authority and non-overlap

- #309: parent OS / information architecture. This document does not replace it.
- #312: Home / user-facing OS Map. This document tracks its place/status; it does not redesign Home by itself.
- #313: Concept / How-to architecture. This document tracks which concepts exist or are planned; it does not own their prose.
- #314: navigation authority. This document does not invent route taxonomy.
- #317: Cockpit-specific concept. This document places it under Decide and tracks its build state.
- #349: backend/runtime architecture. It is a separate architecture view, not a child implementation detail of the user-facing 9-stage loop.

## 8. Maintenance contract

When a meaningful Pages/Codex idea appears:

```text
Idea
→ check existing node / Issue overlap
→ create or refine Issue if needed
→ map to stable node_id
→ set IDEA / PLANNED / node-local NEXT
→ design
→ BUILDING
→ verify repository artifact
→ verify user reachability
→ LIVE or DONE
→ update last reviewed
```

Drift checks to add in a later slice:

- route is non-null but artifact is missing
- artifact exists but has no verified user entry path while status says `LIVE`
- `BUILDING` has no owner/slice reference
- closed Issue leaves a `PLANNED` node indefinitely without review
- stale `last_reviewed`
- multiple conflicting global implementation-next claims
- multiple conflicting node-local `NEXT` changes without an explicit priority

## 9. Architecture plane context

The Codex is not a single folder tree. Keep the planes distinct:

```text
Knowledge      00_Framework / 01_Portfolio / 02_Themes / 03_Companies / ...
Machine        data/*
Execution      scripts/* / workflows
Operations     Ops/*
Presentation   Pages / generated read models
```

This Sitemap is an architecture/status projection across those planes. It must never become the primary truth for portfolio, research facts, hypotheses, decisions, or market data.

## 10. Definition of Done for #324

A reader should be able to answer within roughly 30 seconds:

1. What does the final Codex aim to contain?
2. What is live, designed, building, node-local next, and later?
3. What should implementation build next, and why is it ordered that way?
4. Which Issue owns each meaningful evolution item?
5. Which routes are verified and user-reachable versus merely planned?

The document should remain useful even when individual Issues open/close, because status is tied to actual artifacts, user reachability, and reviewed architecture state rather than Issue state alone.
