# TEAM_STATE — Current Operational State

> Compact SSoT for **current, frequently-changing operating state**.
> Permanent rules remain in `TEAM_RULES.md`. Broadcast history remains in Issue #99.
> Do not copy detailed Issue specifications or historical Broadcasts here.

Last updated: 2026-08-12  
Sources: Issue #99 Current Active Board; #338; #354; AWAY transition comment 5255385557; Owner return to ACTIVE  
Broadcast head at snapshot: `comment_id=5255385557`

## User Mode

- Mode: **ACTIVE**
- Meaning: 👑サド is available. Restore normal role priority; Owner Authority decisions may be surfaced directly to 👑サド rather than accumulated under AWAY delegation.
- Mode contract: #354. `ACTIVE` keeps normal roles. `AWAY` activates delegated autonomous operations below.

## Mode Transition Contract

### ACTIVE → AWAY
The transition owner records one transaction before treating AWAY delegation as active:
1. Set this file's User Mode to `AWAY`.
2. Snapshot open implementation WIP, green Merge Gate items, unresolved Authority items, and material blockers in the transition record.
3. Initialize ♦️ソラ's AWAY cadence at `AWAY_SORA_RUN_MOD3=1` on the first AWAY run. Every third AWAY run (`0`) includes `Delegated Nagi Process Check`.
4. Verify `docs/handoffs/kaede-policy-intelligence.md` freshness and unresolved Next Checkpoints.
5. 🌅アサヒ takes Policy Collection/Evidence continuity; ❤️レイ takes Policy Analysis/Hypothesis continuity.
6. Never resolve Owner Authority merely because the Owner is AWAY; add it to the Authority backlog.

### AWAY → ACTIVE
1. Set User Mode to `ACTIVE`.
2. Stop AWAY-only delegation/cadence and restore normal role priority.
3. Summarize unresolved Authority items, green Merge Gates, material blockers, and delegated Process Check findings accumulated during AWAY.
4. Summarize material Policy Intelligence changes from the Kaede handoff state.
5. Present Owner decisions first; do not bury them behind routine progress.

Transition evidence should be durable in GitHub (Issue #99 or the relevant process Issue). Chat history alone is not sufficient.

## Current Operating Model

| Member | ACTIVE role / capacity | AWAY delegation |
| --- | --- | --- |
| ♦️ソラ | **Main Implementation Owner** | Main implementation + every 3rd run Delegated Nagi Process Check |
| 🌊ナギ | Scrum Master / maintenance; **secondary implementation capacity when an independent READY slice exists** | No periodic dependency required; delegated checks handled by Sora |
| 🌙ルナ | Product / IA / Issue Design; prioritize queue refinement and dependency clarity | Same role; avoid READY oversupply |
| ⭐️ミナ | **Design Authority / Product UI Designer**; create visual prototypes, persist them to GitHub, handoff, Design Gate | Same role; unblock implementation flow |
| ❤️レイ | AI Key Person Watch / #124 Operational Heartbeat | Same + Kaede Policy Analysis/Hypothesis continuity |
| 🌅アサヒ | Policy Collection / Policy Radar | Same + Kaede Policy Collection/Evidence continuity |
| 🍁カエデ | Policy Intelligence / Hypothesis Builder | Continuity is delegated to Asahi/Rei using GitHub handoff state |
| 🤖カイ | Implementation Engineer only when explicitly assigned; do not enter an existing Single Owner scope | Same |

## AWAY Authority Backlog Contract

During AWAY, record but do not decide:
- Owner-only Merge/Acceptance decisions
- investment philosophy / risk threshold / BUY-SELL-HOLD Authority
- ambiguous product choices explicitly reserved for 👑サド

Each backlog item should contain: `ref`, `decision_needed`, `why_owner`, `safe_work_completed`, `next_action_on_active`. On ACTIVE return, these items are the first decision queue.

## Implementation Capacity / Queue

Default: ♦️ソラ leads implementation. 🌊ナギ joins implementation only when capacity is needed and the candidate is independent in Issue/slice/file/logic.

Current priority order (compact reference; read each Issue before work):
1. P0 Reliability / Process — #286, #296 when unowned/non-conflicting
2. Design System foundation — #320
3. Investment OS entry — #312
4. Concept / Cockpit — #313 + #317
5. Global Navigation — #314
6. Practical UX — #307, #308
7. Money Flow operation — #305

## Current Product / Design Guardrails

- #324 is the Sitemap & Evolution Roadmap / build-order reference.
- #320 is the Visual Design System v1 authority for shared tokens/primitives/semantic states.
- Approved or review-critical Visual Prototypes must be persisted to GitHub and linked from their Issue; chat-only artifacts are an incomplete handoff.
- Do not create parallel CSS/component systems when shared primitives can be used.

## Active Process Guardrails

- Single Implementation Owner per Issue/slice. No parallel implementation of the same file/logic.
- `TECHNICAL_INVESTIGATION` is normally work, not a reason to wait for the user.
- Real blockers should classify Authority / Dependency / CI / Missing Artifact / Technical Investigation / External and state next action.
- CI/external wait should trigger safe work on another non-conflicting READY/review/investigation item when available.
- Open implementation PR WIP is normally capped at 2 per implementation owner/lane; it is not a team-wide PR cap. When an owner/lane is at cap, reduce merge distance before creating another implementation PR.
- Issue #79: do not modify/comment/close/implement unless a later explicit authoritative instruction supersedes this constraint.

## Startup Sync v2

Normal run fast path:
1. Check `TEAM_RULES.md` identity. If unchanged since the agent's verified prior read, full semantic reread may be skipped; if changed/unknown, read it fully.
2. Read this `TEAM_STATE.md`.
3. Fetch Issue #99 body and read `broadcast-head`.
4. If own verified `last_seen_comment_id` equals head, no comment-history fetch is needed.
5. If behind, fetch/process only the delta needed to reach head, applying `To: ALL` and own addressee instructions.
6. Update cursor only after actual latest comment read equals authoritative head.
7. If head cannot be reached/verified, use `BROADCAST_SYNC_UNVERIFIED`; never infer “no new Broadcast”.

Fallback: if this file is missing/stale/inconsistent with #99 or TEAM_RULES, use `TEAM_RULES.md → #99 Current Active Board → verified Broadcast delta` and report drift.

## Maintenance Ownership

🌊ナギ checks for drift between this file, Issue #99 Current Active Board, active IMPLEMENTING declarations, and current Authority/handoff state while ACTIVE/when invoked. During AWAY, ♦️ソラ performs the delegated cross-team Process Check every third run. State changes that materially affect future runs should update this snapshot through the repository change flow.
