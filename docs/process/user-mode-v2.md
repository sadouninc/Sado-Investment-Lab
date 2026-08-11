# User Mode v2 — ACTIVE / AWAY Autonomous Operations

Issue: #354

## Purpose

Keep project flow moving while 👑サド is away without allowing agents to invent Owner Authority. `AWAY` is an autonomous operating mode, not a reduced-effort mode.

## Transition record

Each mode change is a durable transaction. A transition record should include:

```text
mode_from: ACTIVE|AWAY
mode_to: AWAY|ACTIVE
changed_at: <timestamp>
implementation_wip: <PR/Issue refs>
green_merge_gates: <refs or none>
authority_backlog: <refs or none>
material_blockers: <refs or none>
kaede_handoff_checked: yes|no
sora_away_run_mod3: 1|2|0|n/a
```

Issue #99 is an acceptable transition-log surface. TEAM_STATE stores only the current mode/contract, not transition history.

## ACTIVE → AWAY

1. Change `TEAM_STATE.md` to `Mode: AWAY` through repository governance.
2. Inventory open implementation PRs and IMPLEMENTING scopes; preserve Single Owner.
3. Snapshot green Merge Gates and unresolved Owner Authority.
4. Verify `docs/handoffs/kaede-policy-intelligence.md` is current enough to resume without chat history.
5. Set first Sora AWAY run to `AWAY_SORA_RUN_MOD3=1`.
6. Activate Asahi Collection/Evidence and Rei Analysis/Hypothesis delegation.
7. Broadcast the completed transition with the snapshot.

## AWAY steady state

### Sora cadence
Every AWAY run advances `1 → 2 → 0 → 1`.

At `0`, run `Delegated Nagi Process Check` covering:
- open implementation PR / WIP cap
- CI / Pages blocker
- READY / IMPLEMENTING and Single Owner conflicts
- stale blockers
- Design → Implementation handoff
- green Merge Gate / Authority backlog
- #124 heartbeat freshness
- READY oversupply

The check is additive: if no material problem exists, return quickly to implementation.

### Authority backlog
Agents may investigate, prepare options, run tests, and remove technical blockers. They must not decide Owner-only questions. Each item records:

```text
ref:
decision_needed:
why_owner:
safe_work_completed:
next_action_on_active:
```

### Policy continuity
Asahi/Rei use `docs/handoffs/kaede-policy-intelligence.md`; detailed evidence remains in the referenced canonical research Issues.

## AWAY → ACTIVE

1. Change TEAM_STATE to ACTIVE.
2. Stop AWAY-only cadence/delegation.
3. Collect green Merge Gates and unresolved Authority backlog.
4. Collect material Process Check findings not yet resolved.
5. Collect material Policy Intelligence changes from the Kaede handoff/research Issues.
6. Present the Owner decision queue before routine status.
7. Broadcast transition completion and resume normal role priority.

## Fail-safe

- If mode is ambiguous, use TEAM_STATE as current operational mode and surface drift.
- If TEAM_STATE contradicts a later explicit Owner instruction, the Owner instruction wins and TEAM_STATE becomes maintenance work.
- AWAY never authorizes BUY/SELL/HOLD, investment philosophy, risk threshold, Owner Acceptance, or Owner-only Merge Gate decisions.
- Issue #79 remains excluded.
