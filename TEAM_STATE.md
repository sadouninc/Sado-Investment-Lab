# TEAM_STATE — Current Operational State

> Compact SSoT for **current, frequently-changing operating state**.
> Permanent rules remain in `TEAM_RULES.md`. Broadcast history remains in Issue #99.
> Do not copy detailed Issue specifications or historical Broadcasts here.

Last updated: 2026-08-17  
Sources: Issue #99 Current Active Board; Broadcast `5315491430`; #602; #617; #625; #645; #690; merged PR #605; merged PR #621; merged PR #627  

## Operating Model Identity

```yaml
operating_model_version: 2
operating_model_status: YELLOW_PILOT
effective_from_broadcast: 5315491430
governance_issue: 690
flow_authority_primary: NAGI
queue_builder: LUNA
main_executor: SORA
sora_idle_mode: FLOW_SCOUT
```

- This identity is machine-readable current-state evidence for Startup Sync and drift detection.
- `operating_model_status: YELLOW_PILOT` means the role update is in bounded production pilot under #690 Operational Rule Review v1; it is not yet `EFFECT_CONFIRMED`.
- If this identity conflicts with the authoritative active Broadcast, report `OPERATING_MODEL_SYNC_DRIFT` and fail closed on ambiguous role/authority behavior.
- Broadcast `5315491430` supersedes the older current-state interpretation that ♦️ソラ must remain idle when no direct NOW is assigned and that 🌙ルナ only designs work without preparing executable queue snapshots.

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

### 🌊ナギ — Single Flow Authority / Global Router / Scrum Master

Global flow work is centralized here to avoid duplicate cross-team scans:
- global Issue / PR / WIP flow scan
- NOW / NEXT / RESERVE global routing and final arbitration
- DIVERGENCE / CONVERGENCE / BALANCED judgment
- lane / formation / scheduled-run cadence adjustment
- queue starvation / owner conflict / duplicate-start detection
- rerouting after `BLOCKED_ESCAPE`
- productivity telemetry and process improvement

🌊ナギ retains final global priority, owner/provider/timing, and cross-lane conflict authority during this pilot.

### ♦️ソラ — Main Implementation + Flow Scout / Queue Preflight

Implementation remains the primary duty.

When assigned work is `IMPLEMENTING`, `REVISION_REQUIRED`, or `CONFLICT_RESOLUTION`, prioritize reducing implementation/merge distance within the assigned Single Owner scope.

When implementation WIP is 0, or assigned work is released into `CI_WAIT` / `REVIEW_WAIT`, do **not** wait idly for another direct assignment. Enter bounded `FLOW_SCOUT` mode and help prepare routing evidence.

Flow Scout may inspect at most 3 supplied/relevant candidates per run for:
- current main state
- open / merged PR evidence
- stale READY metadata
- duplicate target / duplicate branch risk
- dependency / Owner Authority blockers
- same-file / semantic conflict
- residual DoD and focused tests

Return one of:
- `FLOW_SCOUT_RESULT`
- `EXECUTABLE_READY_RECOMMENDED`
- `CONTRACT_GAP`
- `WAIT_EXISTING_PR`

Flow Scout does **not** grant authority to:
- change global priority
- self-claim Single Implementation Owner without routing
- issue paid AI dispatch
- create duplicate branch / PR for an existing canonical path

Final routing remains 🌊ナギ Authority.

During AWAY, ♦️ソラ still receives temporary Delegated Flow Authority only when a traffic-control event occurs and 🌊ナギ is not executable:
- `QUEUE_STARVATION`
- `OWNER_CONFLICT`
- `NO_REROUTE_AFTER_BLOCKED_ESCAPE`
- `PRIORITY_CONFLICT`
- `STATE_DRIFT`
- `GLOBAL_BLOCKER`

Flow Scout is normal anti-idle support and is distinct from Delegated Flow Authority. After routing is restored, Sora returns to implementation first.

### 🌙ルナ — Product Lead / Executable Queue Builder

🌙ルナ keeps Product discovery / Work Design responsibility and additionally prepares executable queue supply.

Responsibilities:
- Product discovery / future-work divergence
- Feature / experiment / Work Contract design
- meaningful Issue creation and READY-quality refinement
- current main / open PR / merged PR freshness audit before queue recommendation
- reject stale READY / duplicate target / unresolved dependency
- convert fresh residual DoD into `EXECUTABLE_QUEUE_SNAPSHOT` with NOW / NEXT / RESERVE
- Product priority proposals

GREEN bounded direct replenishment is allowed only under the active pilot contract when all safety conditions are satisfied; global priority and final cross-lane arbitration remain with 🌊ナギ. Ambiguous owner/provider/timing or conflict returns to 🌊ナギ rather than being inferred.

### Other specialist members

❤️レイ / 🌅アサヒ / ⭐️ミナ / 🍁カエデ / 🤖カイ retain lane-local expertise, discovery, Issue creation, implementation/review authority as defined by TEAM_RULES. They may propose global priority changes but do not routinely duplicate global routing scans.

## Operational Rule Review — #690 pilot

Worker-behavior changes are not considered fully activated merely because they were written in an individual Issue or PR comment.

Current lifecycle:

`RULE_DRAFT → IMPACT_REVIEW → SSOT_SYNC → SHADOW/PILOT → ACTIVE → EFFECT_CONFIRMED`

For YELLOW/RED worker-behavior changes, activation completeness includes:
1. authoritative rule location
2. To: ALL / affected-worker Broadcast
3. Issue #99 authoritative `broadcast-head` update
4. TEAM_STATE sync when current operating behavior changes
5. TEAM_RULES PR when the rule becomes permanent
6. Startup Sync reachability for affected workers
7. explicit supersede of conflicting old behavior

Missing required propagation is `OPERATIONAL_CHANGE_NOT_ACTIVATED`.

Bootstrap reviews are intentionally heavier while #690 gathers machine-check teacher data. The target steady state is machine-check majority + 🌊ナギ final judgment + exception-only human review; ♦️ソラ must not become a permanent Operational Rule blocking reviewer.

## Continuous Execution / Forward Progress

Each scheduled or invoked run should maximize safe **productive progress**, not verification volume.

1. Verification/startup work is a bounded precondition, not the goal of the run.
2. Execute assigned `NOW → NEXT → RESERVE` continuously when safe.
3. Completing one item or creating one PR is not a stop condition; reduce merge distance and continue safe work.
4. If assigned work is blocked, attempt bounded self-resolution; then `BLOCKED_ESCAPE` and continue the next supplied item.
5. If implementation work is waiting or exhausted, ♦️ソラ uses bounded Flow Scout instead of ending with idle capacity.
6. If lane-local work is exhausted, discover a meaningful gap and create/advance a bounded Issue or slice rather than end with zero productive steps.
7. A new meaningful Issue is not a failure. Capture broadly, execute selectively.
8. Stop only for explicit Authority/high-risk gates or when no safe productive action can be found after the fallback sequence.

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
- 🌙ルナ supplies fresh executable queue proposals; 🌊ナギ performs final global routing.
- ♦️ソラ uses Flow Scout when implementation capacity is released by idle / CI_WAIT / REVIEW_WAIT.
- 🤖カイ is used when available and explicitly routed to an independent Single Owner slice.
- Other members may implement within explicit delegation and Single Implementation Owner boundaries.
- Current global priorities are maintained by 🌊ナギ through Issue #99 Current Active Board and current Issue/PR state.
- Do not rely on stale static priority lists when a newer Flow routing record exists.

### Active implementation WIP semantics — #645

**Open PR count is not active implementation WIP.** WIP capacity follows current work state.

Counts toward implementation WIP:
- `IMPLEMENTING`
- `REVISION_REQUIRED`
- `CONFLICT_RESOLUTION`

Normally releases implementation capacity:
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
- unacknowledged agent dispatch at lease expiry → expire/reroute instead of holding the queue indefinitely.
- same blocker for 2 consecutive runs → `BLOCKED_ESCAPE` mandatory.

PR count is not a productivity KPI. These guards only detect available safe work that is not moving.

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
2. Read this `TEAM_STATE.md`, including `operating_model_version` and `effective_from_broadcast`.
3. Fetch Issue #99 body and authoritative `broadcast-head`.
4. Process only the Broadcast delta needed for `To: ALL` and own addressee instructions.
5. If the active operating-model Broadcast conflicts with TEAM_STATE, report `OPERATING_MODEL_SYNC_DRIFT`; do not silently choose a role interpretation.
6. If latest authoritative head cannot be verified, use `BROADCAST_SYNC_UNVERIFIED`; do not infer “no new Broadcast”.
7. After minimal sync, move directly to productive work.

Fallback: if this file is missing/stale/inconsistent with #99 or TEAM_RULES, use `TEAM_RULES.md → #99 Current Active Board → verified Broadcast delta` and report drift.

## Maintenance Ownership

🌊ナギ owns drift detection among TEAM_STATE, TEAM_RULES, Issue #99, current IMPLEMENTING declarations, lane routing, Authority state, and operating-model identity.

During AWAY, ♦️ソラ does **not** run a periodic full global Process Check. Flow Scout is bounded to queue-preflight support; Delegated Flow Authority activates only for the explicit traffic-control triggers above when 🌊ナギ is unavailable.
