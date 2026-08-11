# Sado Investment Codex — Sitemap & Evolution Roadmap

> Canonical architecture/status document for Issue #324.
>
> Purpose: show the target Codex structure, the current build state, the next build order, and planned evolution without treating Issue state itself as product completion state.

- Architecture version: v1.0-baseline
- Last reviewed: 2026-08-11
- Source authority: repository state + GitHub Issue/PR state + reviewed architecture decisions
- Status rule: route/page existence must be verified independently; an open/closed Issue is never copied mechanically into page status.

## 1. Current snapshot

### NOW

- Reliability / foundation work remains the active prerequisite lane.
- Canonical Pages design-system work is the main visual foundation before broad page expansion.
- Existing Investment OS knowledge/data/runtime layers remain authoritative; this document is a roadmap/status view, not a new investment-data SSoT.

### NEXT

1. Canonical Pages / design-system foundation (#320)
2. Home / OS Map refinement (#312)
3. Concept architecture + Cockpit concept (#313, #317)
4. Global navigation (#314)
5. Practical decision UX (#307, #308)
6. Money Flow daily operationalization (#305)

### LATER

- Act / Preflight flow
- Decision Journal / history expansion
- Review / Learning hierarchy
- Remaining high-value Concept pages
- Backend Runtime Architecture visualization (#349)

The order above is a dependency-aware baseline, not a frozen roadmap. Existing IMPLEMENTING work should not be interrupted merely to satisfy this list.

## 2. Status vocabulary

| Status | Meaning |
|---|---|
| `LIVE` | User-accessible page or major feature is verified to exist |
| `DONE` | Design/doc deliverable is complete |
| `BUILDING` | Implementation is actively underway |
| `DESIGNED` | Contract/design exists; implementation is not yet verified complete |
| `NEXT` | Selected next build target |
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

This is the target information architecture. A node is not considered live until its actual route/artifact has been verified.

## 4. Node registry baseline

Routes are intentionally `null` unless verified during implementation. This prevents planned paths from being presented as live URLs.

| Node ID | Display name | Stage | Page status | Concept status | Route | Related issues | Next change |
|---|---|---:|---|---|---|---|---|
| `global.home` | Home | Global | `DESIGNED` | n/a | null | #312 | Confirm current route/artifact; then refine Home / OS Map hierarchy |
| `global.codex-map` | Codex Map / OS Overview | Global | `DESIGNED` | n/a | null | #312, #309 | Verify live artifact and align status overlay |
| `global.navigation` | Global Navigation | Global | `DESIGNED` | n/a | null | #314 | Implement after foundation and major concept links stabilize |
| `global.concept` | Concept / How-to Architecture | Global | `DESIGNED` | `DESIGNED` | null | #313 | Add only high-value explanatory Concept nodes |
| `observe.money-flow` | Money Flow | 1 Observe | `PLANNED` | `DESIGNED` | null | #305, #112 | Move from detector capability to dependable daily operating surface |
| `discover.candidates` | Candidate Selector | 2 Discover | `DESIGNED` | `DESIGNED` | null | #108 | Verify current page/feature artifact and route before marking LIVE |
| `understand.company-research` | Company Research | 3 Understand | `DESIGNED` | `DESIGNED` | null | #113 | Expand canonical research coverage and verify presentation surface |
| `hypothesize.thesis` | Investment Hypothesis | 4 Hypothesize | `DESIGNED` | `DESIGNED` | null | #130, #313 | Connect research evidence and monitoring-ready hypothesis contract |
| `hypothesize.valuation` | Earnings / Bear-Base-Bull / Forward PER | 4 Hypothesize | `DESIGNED` | `DESIGNED` | null | #117, #313 | Make scenario provenance and comparison visible in decision flow |
| `decide.cockpit` | Investment Decision Cockpit | 5 Decide | `NEXT` | `NEXT` | null | #317, #308 | Build Cockpit Concept and connect prior/current/delta context |
| `act.trade-intent` | Trade Intent | 6 Act | `PLANNED` | `DESIGNED` | null | #307 | Define practical transition from decision to intended action |
| `act.preflight` | Portfolio Preflight | 6 Act | `PLANNED` | `DESIGNED` | null | #307, #313 | Add risk/position checks before execution |
| `record.decision-journal` | Decision Journal / Snapshot / History | 7 Record | `DESIGNED` | `DESIGNED` | null | #133 | Preserve decision-time evidence and reasoning without hindsight rewrite |
| `learn.review` | Decision Review | 8 Learn | `DESIGNED` | `PLANNED` | null | #141 | Clarify review priority and evidence-delta drill-down |
| `learn.pattern-lab` | Decision Pattern Lab | 8 Learn | `DESIGNED` | `PLANNED` | null | #135 | Broaden learning beyond trade-only analysis |
| `reobserve.checkpoints` | Catalyst / Checkpoint Timeline | 9 Re-observe | `PLANNED` | `PLANNED` | null | #130, #141 | Close the loop back into observation/review |
| `architecture.runtime` | Git-Native Agentic Runtime Architecture | Architecture | `DESIGNED` | n/a | null | #349 | PR1 canonical runtime doc, then diagrams; Pages view later |

## 5. Build Order baseline

```text
Reliability / prerequisites
  ↓
#320 Pages Design System foundation
  ↓
#312 Home / OS Map
  ↓
#313 Concept architecture + #317 Cockpit Concept
  ↓
#314 Global Navigation
  ↓
#307 / #308 practical decision UX
  ↓
#305 Money Flow daily operations
```

Rules:

1. Existing `BUILDING` work is not pre-empted by this document.
2. `NEXT` should remain deliberately narrow; this is not a copy of the READY Issue queue.
3. Dependency or owner decisions may reorder the baseline.
4. Any reorder should update this document rather than silently diverging.

## 6. Evolution registry

| Change ID | Node | Status | Summary | Issue | Priority |
|---|---|---|---|---|---|
| `decide.cockpit.concept` | `decide.cockpit` | `NEXT` | Create the Cockpit Concept explaining what the decision surface is for and how to use it | #317 | High |
| `decide.cockpit.delta` | `decide.cockpit` | `PLANNED` | Show previous → current → delta for important decision context | #308 | High |
| `act.intent-preflight` | `act.trade-intent` / `act.preflight` | `PLANNED` | Connect decision to trade intent and portfolio preflight | #307 | High |
| `observe.money-flow.daily` | `observe.money-flow` | `PLANNED` | Turn Money Flow into a dependable daily operational input | #305 | High |
| `architecture.runtime.current` | `architecture.runtime` | `PLANNED` | Document CURRENT runtime model before adding future-state diagrams | #349 | High |
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
→ set IDEA / PLANNED / NEXT
→ design
→ BUILDING
→ verify artifact/route
→ LIVE or DONE
→ update last reviewed
```

Drift checks to add in a later slice:

- route is non-null but artifact is missing
- `BUILDING` has no owner/slice reference
- closed Issue leaves a `PLANNED` node indefinitely without review
- stale `last_reviewed`
- multiple conflicting `NEXT` changes on the same node

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
2. What is live, designed, building, next, and later?
3. What should be built next, and why is it ordered that way?
4. Which Issue owns each meaningful evolution item?
5. Which routes are verified versus merely planned?

The document should remain useful even when individual Issues open/close, because status is tied to actual artifacts and reviewed architecture state rather than Issue state alone.
