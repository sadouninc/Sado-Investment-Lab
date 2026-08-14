# TEAM_RULES

## Purpose

Sado Investment Lab exists to **move the project forward**. Process, Issue hygiene, verification, and reporting are means to that end; they must never become substitute goals that slow meaningful progress.

## Core execution principle

Every member should maximize safe forward progress per run. Verification is necessary but is not itself the primary outcome.

- Prefer `NOW -> NEXT -> RESERVE -> discover/create next valuable work` over stopping after one item.
- If assigned work is blocked or exhausted, search for another non-conflicting valuable task within the member's lane.
- If no suitable Issue exists, identify a meaningful gap and create a bounded Issue or slice, then advance it as far as Authority and safety allow in the same run.
- A run should not end merely because checks are complete, news delta is zero, READY is empty, or one blocker was found.
- Repeatedly rechecking an unchanged blocker is not forward progress. Record the trigger for re-entry and move to other work.

## Productive Step vs Verification Step

### Productive Step
Counts as real forward progress when it materially changes project state, for example:
- code, tests, docs, data, design artifacts, prototypes, fixtures, automation, contracts, metrics
- PR creation, blocker repair, merge when delegated Authority allows it
- creating a meaningful Issue or turning an Issue into an immediately executable bounded slice
- persisting new Research / Evidence / Hypothesis progress
- converting an ambiguous blocker into a concrete handoff that another worker can immediately execute
- finding and solving reliability, UX, tooling, process, research, or product gaps

### Verification Step
Necessary operational work, but not counted as substantive progress by itself:
- Startup Sync / Broadcast read
- Open PR / CI / review-state checks
- repeated status checks on an unchanged blocker
- no-delta searches
- viewing READY candidates without advancing any of them

Verification should be batched and kept as a small fraction of a run whenever possible.

## Run completion standard

Default target for every scheduled or invoked run:
- at least 1 Productive Step
- normally 3 or more Productive Steps where safely possible
- preferably at least 1 durable output (commit / PR / Issue / design artifact / Research persistence / measurable contract change)

Zero-productive runs are exceptional. Before ending with zero Productive Steps, the worker must have exhausted current WIP, non-conflicting READY/NEXT/RESERVE work, and a reasonable lane-level gap search. If a meaningful bounded gap exists, creating and advancing an Issue is valid work.

## Issue creation philosophy

**Issue count reduction is not a project objective. Project advancement is the objective.**

A growing Issue count can be healthy when it reflects newly discovered risks, opportunities, product ideas, future capabilities, research questions, UX improvements, automation ideas, or technical debt that are worth preserving.

Therefore:
- Do not suppress meaningful Issue creation merely to keep the Issue count low.
- Do not treat `fewer open Issues` as a success metric by itself.
- Creativity and future-work discovery are positive outputs when they are relevant to the Lab's goals.
- Prefer capturing a real valuable idea over losing it because the queue already looks large.
- Avoid meaningless, duplicate, vague, or abandoned Issues that create noise.
- A new Issue should normally communicate enough intent to remain useful: `why_now`, value/outcome, bounded scope or next discovery step, duplicate check, and next executable action when known.
- Large future ideas may remain discovery/design Issues; they do not need to be artificially forced into implementation readiness immediately.

The desired state is **a rich but navigable backlog**, not an artificially small backlog.

## Blocked Escape

If the same Issue has the same blocker across two consecutive runs without new state-changing evidence:
1. record blocker class, owner/trigger, and next checkpoint,
2. stop spending the run rechecking it,
3. move to another valuable task or create a new bounded task from a meaningful gap,
4. re-enter the blocked Issue only when its trigger changes.

## Nagi progress review/reporting contract

🌊ナギ's progress checks and reports must explicitly distinguish **substantive forward progress** from verification overhead.

Whenever reporting team productivity or run progress, include where evidence allows:
- Productive Steps per member per run
- Verification Steps per member per run
- durable outputs created (PR / Issue / commit / design / Research persistence)
- zero-productive runs
- repeated-blocker / blocked-escape behavior
- work created autonomously when the queue was empty or blocked
- whether the project actually advanced, not merely whether Issues were closed or status checks were performed

For run-by-run reporting, prefer the format:

`Member -> Run N -> Productive Steps -> Verification Steps -> Durable Outputs -> Blocker/Escape -> Net Forward Progress`

When the user asks whether productivity improved, base the answer primarily on Productive Steps, durable outputs, lead time, merge/research/design advancement, and reduction of idle/no-op runs. Do not inflate progress by counting checks as equivalent to implementation/design/research work.

🌊ナギ must also watch the opposite failure mode: **backlog minimization becoming a brake on creativity**. Report separately on backlog quality (meaningful vs duplicate/vague) rather than using raw Issue count as a proxy for health.

## Work creation fallback by role

- ♦️ソラ: when implementation queue is empty/blocked, search reliability bugs, missing validation, flaky tests, developer tooling, automation, small safe refactors, or independently executable product slices; create a bounded Issue if valuable and continue toward test/PR where safe.
- ❤️レイ: when material news delta is zero, advance Research debt such as missing valuation inputs, stale sources, falsification criteria, evidence-conversion stages, alert precision, dedupe quality, or hypothesis completeness; zero news delta is not a stop condition.
- 🌅アサヒ: when no new policy/market delta exists, advance prospective tests, threshold quality, counterfactual design, source completeness, or policy-to-company transmission research.
- 🌙ルナ: maintain sufficient future executable work and product discovery; create meaningful bounded READY slices without suppressing larger future ideas solely to limit queue size.
- ⭐️ミナ: when no Design Gate is pending, inspect important Pages/flows for UX debt and create/design valuable improvements.
- 🌊ナギ: when process/coordination work is quiet, search for throughput, duplication, observability, reliability, handoff, or autonomy gaps and advance them into measurable improvements.

## Issue / PR flow

For implementation and material changes, use the normal repository flow:
`Issue -> branch -> commit -> PR -> review / CI -> merge`

Minor non-behavioral corrections and explicitly documented exceptions may use the allowed lightweight flow. When uncertain, use a PR.

## Single Implementation Owner

One implementation owner per Issue/slice/file/logic scope. Parallelize through independent slices, not duplicate implementations.

## Safety and Authority

Forward-progress pressure never overrides Authority or safety gates. Stop or fail closed for:
- Owner-only investment judgment / BUY-SELL-HOLD / risk thresholds
- secrets, authentication, permissions
- paid actions
- destructive or irreversible changes
- material external-publication scope changes
- other explicit gates documented by the repository

Issue #79 remains untouched unless a later explicit authoritative instruction supersedes the restriction.
