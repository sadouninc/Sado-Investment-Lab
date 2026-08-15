# User Mode v2 — Shadow Rollout Evidence

担当: 🌊ナギ  
種別: Process / Dry-run / Safety Evidence

Refs: #617 #625 PR #621 #479 #602 #587

## Purpose
実際のauto-mergeを有効化する前に、User Mode v2のtransition、AWAY delegated Flow Authority、AUTO_GREEN gateをpure/shadowで検証する。

## Transition shadow matrix
- AWAY → ACTIVE_MANUAL: expected ALLOW
- ACTIVE_MANUAL → ACTIVE_AUTO: expected ALLOW
- ACTIVE_AUTO → ACTIVE_MANUAL: expected ALLOW
- stale expected mode: expected BLOCK
- duplicate transition id: expected BLOCK

## AWAY Delegated Sora shadow matrix
- queue healthy / ordinary implementation available: no delegation
- QUEUE_STARVATION: delegate temporarily
- OWNER_CONFLICT: delegate temporarily
- NO_REROUTE_AFTER_BLOCKED_ESCAPE: delegate temporarily
- ACTIVE modes: never activate Sora delegation from these AWAY triggers

The goal is traffic control, not a return to per-run global scans. Delegation should end after routing is restored.

## AUTO_GREEN shadow matrix
The first deterministic fixture set includes:

| Sample | Expected |
| --- | --- |
| low-risk, CI/review/gates GREEN | ELIGIBLE |
| required Design/Product/Reliability Gate missing | BLOCK |
| CI failure | BLOCK |
| explicit Owner Acceptance required | BLOCK |
| sensitive/workflow/permission-like change | BLOCK |
| latest-head review evidence absent/unknown | BLOCK |

Any uncertainty is represented with the blocking-side input so the evaluator fails closed.

## Activation Gate
Actual auto-merge execution remains disabled until:
1. PR #621 contract is on main.
2. This shadow suite is GREEN.
3. TEAM_STATE / #99 / TEAM_RULES are aligned to the three-mode semantics.
4. Historical/live shadow samples show zero dangerous false-positive candidates.
5. Activation is performed as a separate explicit rollout step.

## Telemetry after activation candidate
Record in #479:
- mode / merge_policy
- shadow eligibility counts and block reasons
- delegated_sora_sm_activation_count
- sora productive steps during delegated windows
- queue starvation recovery
- manual merge wait baseline vs AUTO_GREEN candidate wait

Issue #79 untouched.
