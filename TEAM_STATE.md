# TEAM_STATE — Current Operational State

> Compact SSoT for **current, frequently-changing operating state**.
> Permanent rules remain in `TEAM_RULES.md`. Broadcast history remains in Issue #99.
> Do not copy detailed Issue specifications or historical Broadcasts here.

Last updated: 2026-08-18  
Sources: Issue #99 Current Active Board; #602; #617; #625; #645; #556; #690; merged PR #605; merged PR #621; merged PR #627  

## User Mode v2

```yaml
user_mode: AWAY
presence: AWAY
merge_policy: AUTO_GREEN
flow_authority_primary: NAGI
flow_authority_fallback: SORA_DELEGATED
```

- Current operational meaning remains **AWAY**: 👑サド is inactive for routine flow decisions.
- Owner / Investment Authority is never inferred from AWAY.
- `AUTO_GREEN` is the merge policy contract, but actual auto-merge execution remains disabled until #625 Activation Gate is completed.
- Legacy `ACTIVE` is interpreted only as migration alias for `ACTIVE_MANUAL`.

## User-facing Modes

| Mode | Presence | Merge policy | Default Flow Authority |
| --- | --- | --- | --- |
| `ACTIVE_MANUAL` | ACTIVE | MANUAL | 🌊ナギ |
| `ACTIVE_AUTO` | ACTIVE | AUTO_GREEN | 🌊ナギ |
| `AWAY` | AWAY | AUTO_GREEN | 🌊ナギ; event-driven ♦️ソラ fallback |

Mode transition uses the fail-closed CAS contract from #617 / PR #621: `expected_current_mode + target_mode + transition_id`.

## Flow Authority / Role Boundary

### 🌊ナギ — Single Flow Authority / Scrum Master

Global flow work is centralized here to avoid duplicate cross-team scans:
- global Issue / PR / WIP flow scan
- NOW / NEXT / RESERVE global routing
- DIVERGENCE / CONVERGENCE / BALANCED judgment
- lane / formation / scheduled-run cadence adjustment
- queue starvation / owner conflict / duplicate-start detection
- rerouting after `BLOCKED_ESCAPE`
- productivity telemetry and process improvement

### ♦️ソラ — Main Executor

Normal run:

`minimal sync → assigned NOW → assigned NEXT → assigned RESERVE → BLOCKED_ESCAPE`

Do not perform a full global Issue/PR scan every run.

During AWAY, ♦️ソラ receives temporary Delegated Flow Authority only when a traffic-control event occurs and 🌊ナギ is not executable:
- `QUEUE_STARVATION`
- `OWNER_CONFLICT`
- `NO_REROUTE_AFTER_BLOCKED_ESCAPE`
- `PRIORITY_CONFLICT`
- `STATE_DRIFT`
- `GLOBAL_BLOCKER`

Ordinary implementation, CI waiting, or routine review checks are not delegation triggers. After routing is restored, Sora returns to Executor mode.

### 🌙ルナ — Product Lead / Work Designer

- Product discovery / future-work divergence
- Feature / experiment / Work Contract design
- meaningful Issue creation and READY-quality refinement
- Product priority proposals

Global routing and final cross-lane priority remain with 🌊ナギ.

### Other specialist members

❤️レイ / 🌅アサヒ / ⭐️ミナ / 🍁カエデ / 🤖カイ retain lane-local expertise, discovery, Issue creation, implementation/review authority as defined by TEAM_RULES. They may propose global priority changes but do not routinely duplicate global routing scans.

## Continuous Execution / Forward Progress

Each scheduled or invoked run should maximize safe **productive progress**, not verification volume.

1. Verification/startup work is a bounded precondition, not the goal of the run.
2. Execute assigned `NOW → NEXT → RESERVE` continuously when safe.
3. Completing one item or creating one PR is not a stop condition; reduce merge distance and continue safe work.
4. If assigned work is blocked, attempt bounded self-resolution; then `BLOCKED_ESCAPE` and continue the next supplied item.
5. If lane-local work is exhausted, discover a meaningful gap and create/advance a bounded Issue or slice rather than end with zero productive steps.
6. A new meaningful Issue is not a failure. Capture broadly, execute selectively.
7. Stop only for explicit Authority/high-risk gates or when no safe productive action can be found after the fallback sequence.

Recommended run-end telemetry:

```text
productive_steps:
verification_steps:
durable_outputs:
blocked_escape_count:
self_created_meaningful_work:
zero_productive_run: yes|no
NEXT_AUTO:
```

## AWAY Authority Backlog Contract

During AWAY, record but do not decide:
- investment execution or BUY/SELL/HOLD Authority
- investment philosophy / risk threshold changes
- explicit Owner Acceptance
- security / secrets / permissions / paid / destructive decisions
- other Owner-only decisions defined in TEAM_RULES

Each item should contain: `ref`, `decision_needed`, `why_owner`, `safe_work_completed`, `next_action_on_active`.

## AUTO_GREEN Safety

A PR is only an `AUTO_GREEN` candidate when all required facts are known and GREEN:
- CI / required checks PASS
- no `REQUEST_CHANGES`
- no merge conflict
- required Product / Design / Reliability Gates PASS
- latest-head review evidence exists
- no Owner / Investment Authority
- no sensitive security / secrets / permissions / paid / destructive change
- no explicit Owner Acceptance requirement
- Issue #79 untouched

UNKNOWN never becomes PASS.

**Current rollout state:** evaluator + shadow tests are on main via #621/#627. Actual automatic merge execution is still OFF until #625 completes TEAM_STATE/#99/TEAM_RULES alignment and shadow evidence confirms dangerous false-positive = 0.

## Implementation Capacity / Queue

- Default main executor: ♦️ソラ.
- 🤖カイ is used when available and explicitly routed to an independent Single Owner slice.
- Other members may implement within explicit delegation and Single Implementation Owner boundaries.
- Current global priorities are maintained by 🌊ナギ through Issue #99 Current Active Board and current Issue/PR state.
- Do not rely on stale static priority lists when a newer Flow routing record exists.

### Active implementation WIP semantics — #645

**Open PR count is not active implementation WIP.** WIP capacity follows current work state.

Counts toward implementation WIP:
- `EXECUTION_EVIDENCE`
- `IMPLEMENTING`
- `REVISION_REQUIRED`
- `CONFLICT_RESOLUTION`

Normally releases implementation capacity:
- `DISPATCHED`
- `ACKED`
- `CI_WAIT`
- `REVIEW_WAIT`
- `RESEARCH_GATE_WAIT`
- `DESIGN_GATE_WAIT`
- `OWNER_WAIT`
- `EXTERNAL_WAIT`
- `MERGE_READY`

A waiting PR can still block a new slice through Single Owner or path conflict. That conflict is evaluated separately and fail-closed; it must not be inferred merely from the PR being open.

When non-conflicting READY work exists:
- `active_implementation_wip == 0` → `QUEUE_STARVATION`, route in the same SM run.
- durable implementation output age `>=120m` → `FLOW_STALL_WARNING`.
- durable implementation output age `>=240m` → `FLOW_STALL_CRITICAL`, same-run reroute required.
- same blocker for 2 consecutive runs → `BLOCKED_ESCAPE` mandatory.

PR count is not a productivity KPI. These guards only detect available safe work that is not moving.

### Dispatch Activation Lease — #556 PR2 / #690 YELLOW pilot

Canonical execution state machine:

`READY → DISPATCHED → ACKED → EXECUTION_EVIDENCE → PR_OPEN → CI_WAIT/REVISION_REQUIRED → MERGE_READY → MERGED`

- `DISPATCHED` is an offer/lease only and does **not** count as active implementation WIP.
- `ACKED` reserves the slice briefly but is not implementation evidence and does **not** count as active implementation WIP.
- Active implementation WIP starts only after `EXECUTION_EVIDENCE` exists.
- Execution evidence means a slice-linked branch, non-empty commit, implementation workflow evidence, or equivalent durable mutation evidence. A comment, ACK, or verification-only action is insufficient.
- Default ACK deadline is 10 minutes after dispatch.
- Default execution-evidence deadline is 20 minutes after ACK.
- No ACK by deadline → `DISPATCH_ACK_EXPIRED`; release the reservation and reroute after fresh duplicate/conflict preflight.
- ACK but no execution evidence by deadline → `ACK_STALLED → BLOCKED_ESCAPE`; release the reservation and reroute after fresh duplicate/conflict preflight.
- Late ACK must never revive an expired lease. A fresh `lease_id` is required.
- If provider evidence makes ACK and execution evidence observable atomically, intermediate states may be traversed immediately.
- FREE_FIRST remains the default routing policy; paid duplicate dispatch is prohibited.

Operational telemetry should distinguish reservation from real work, including `dispatch_to_ack_minutes`, `ack_to_execution_minutes`, `dispatch_ack_expired_count`, `ack_stalled_count`, `execution_activation_rate`, `reroute_success_rate`, and `false_active_wip_minutes`.

This is a #690 YELLOW operational-change pilot. It must be validated with production evidence before `EFFECT_CONFIRMED`; permanent-rule promotion to TEAM_RULES requires the normal PR/review path.

## Product / Design Guardrails

- #324 is the Sitemap & Evolution Roadmap / build-order reference.
- #320 is the Visual Design System v1 authority for shared tokens/primitives/semantic states.
- Approved or review-critical Visual Prototypes must be persisted to GitHub and linked from their Issue.
- Do not create parallel CSS/component systems when shared primitives can be used.

## Active Process Guardrails

- Single Implementation Owner per Issue/slice. No parallel implementation of the same file/logic.
- `TECHNICAL_INVESTIGATION` is normally work, not a reason to wait for the user.
- Real blockers should classify Authority / Dependency / CI / Missing Artifact / Technical Investigation / External and state next action.
- CI/external wait should trigger another safe non-conflicting item when available.
- Active implementation WIP is normally capped at 2 per implementation owner/lane; waiting PRs do not consume that capacity unless they still require active code mutation. Reduce merge distance while also continuing safe independent work.
- Issue #79: do not modify/comment/close/implement unless a later explicit authoritative instruction supersedes this constraint.

## Startup Sync v2

Normal fast path:
1. Check `TEAM_RULES.md` identity. If changed/unknown, read it fully.
2. Read this `TEAM_STATE.md`.
3. Fetch Issue #99 body and authoritative `broadcast-head`.
4. Process only the Broadcast delta needed for `To: ALL` and own addressee instructions.
5. If latest head cannot be verified, use `BROADCAST_SYNC_UNVERIFIED`; do not infer “no new Broadcast”.
6. After minimal sync, move directly to productive work.

Fallback: if this file is missing/stale/inconsistent with #99 or TEAM_RULES, use `TEAM_RULES.md → #99 Current Active Board → verified Broadcast delta` and report drift.

## Maintenance Ownership

🌊ナギ owns drift detection among TEAM_STATE, TEAM_RULES, Issue #99, current IMPLEMENTING declarations, lane routing, and Authority state.

During AWAY, ♦️ソラ does **not** run a periodic global Process Check. Delegated Flow Authority activates only for the explicit traffic-control triggers above when 🌊ナギ is unavailable.
