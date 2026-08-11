# TEAM_STATE — Current Operational State

> Compact SSoT for **current, frequently-changing operating state**.
> Permanent rules remain in `TEAM_RULES.md`. Broadcast history remains in Issue #99.
> Do not copy detailed Issue specifications or historical Broadcasts here.

Last updated: 2026-08-11  
Sources: Issue #99 Current Active Board; #338  
Broadcast head at snapshot: `comment_id=5247406486`

## User Mode

- Mode: **ACTIVE**
- Meaning: 👑サド is currently available to drive decisions/requests. Prepare Authority questions compactly and surface them promptly; do not invent Authority decisions.

## Current Operating Model

| Member | Current role / capacity |
| --- | --- |
| ♦️ソラ | **Main Implementation Owner** |
| 🌊ナギ | Scrum Master / maintenance; **secondary implementation capacity when an independent READY slice exists** |
| 🌙ルナ | Product / IA / Issue Design; prioritize queue refinement and dependency clarity |
| ⭐️ミナ | **Design Authority / Product UI Designer**; create visual prototypes, persist them to GitHub, handoff, Design Gate |
| ❤️レイ | AI Key Person Watch / #124 Operational Heartbeat |
| 🌅アサヒ | Policy Collection / Policy Radar |
| 🍁カエデ | Policy Intelligence / Hypothesis Builder |
| 🤖カイ | Implementation Engineer only when explicitly assigned; do not enter an existing Single Owner scope |

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

🌊ナギ checks for drift between this file, Issue #99 Current Active Board, active IMPLEMENTING declarations, and current Authority/handoff state. State changes that materially affect future runs should update this snapshot through the repository change flow.
