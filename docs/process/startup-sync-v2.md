# Startup Sync v2 — Differential Team Context Read

担当: 🌊ナギ  
種別: Process / Reliability / Performance  
Issue: #338

## Problem

`TEAM_RULES.md` and Issue #99 are safety-critical, but repeatedly re-reading/re-interpreting permanent rules and a growing append-only Broadcast history consumes startup context and time on every scheduled run.

Existing protections remain authoritative:
- #148 Broadcast Read Verification
- #150 Current Active Board + Archive
- #265 Broadcast Head Marker

Startup Sync v2 adds a fast path; it does **not** weaken those controls.

## Three Layers

### 1. `TEAM_RULES.md` — permanent rules
Read fully when its identity changed or when prior verified identity is unavailable. A run may reuse its previously verified interpretation only when it can establish the file is unchanged.

### 2. `TEAM_STATE.md` — compact current state
Small snapshot of frequently-changing operational facts: User Mode, roles/capacity, compact priority queue, current design/process guardrails, temporary prohibitions, and Broadcast head snapshot.

This is not an audit log and must not accumulate history.

### 3. Issue #99 — change log + verification target
Issue body keeps the human-readable Current Active Board and authoritative `broadcast-head`. Comments remain append-only audit/change events.

## Fast Path Algorithm

```text
rules_identity = identify(TEAM_RULES.md)
if rules_identity unknown OR rules_identity != last_verified_rules_identity:
    fully_read_and_apply(TEAM_RULES.md)
    last_verified_rules_identity = rules_identity

read(TEAM_STATE.md)
head = read(issue_99.broadcast_head)

if last_seen_comment_id == head:
    broadcast = VERIFIED
else:
    comments = fetch_delta(last_seen_comment_id -> head)
    apply(To: ALL + own addressee)
    if actual_latest_comment_id == head:
        update(last_seen_comment_id = head)
        broadcast = VERIFIED
    else:
        broadcast = BROADCAST_SYNC_UNVERIFIED
```

A connector may return all comments rather than a server-side delta. In that case the reader should filter/process only IDs newer than its cursor, but it still must prove the returned sequence reaches `broadcast-head` before advancing the cursor.

## Fail-Closed Conditions

Use `BROADCAST_SYNC_UNVERIFIED` when:
- `broadcast-head` is missing/malformed/stale,
- response is truncated and continuation cannot reach head,
- actual latest fetched comment does not equal head,
- cursor is ahead of head / appears rolled back,
- TEAM_STATE materially contradicts TEAM_RULES or #99 and the authoritative source cannot be resolved.

Never interpret an unverified read as “no new Broadcast”.

## TEAM_STATE Update Contract

Update TEAM_STATE only for changes that matter across future runs, for example:
- User Mode ACTIVE/AWAY
- role/capacity change
- implementation priority order change
- new temporary prohibition/guardrail
- durable handoff/Authority state

Do not update it for every heartbeat, ordinary Issue progress comment, CI status, or per-agent Broadcast cursor.

Changes should follow normal repository governance. This keeps writes low-frequency and reviewable.

## Drift Check

🌊ナギ maintenance compares:
1. TEAM_STATE roles/capacity vs #99 Active Board
2. compact queue vs active READY/IMPLEMENTING ownership
3. User Mode vs latest authoritative user-mode instruction
4. design handoff state vs GitHub-persisted artifacts
5. temporary constraints vs later superseding instructions

Material drift should be corrected; uncertain Authority conflicts are surfaced rather than guessed.

## Performance Principle

Startup cost should scale mainly with **current state + new Broadcast delta**, not total historical Broadcast size.
