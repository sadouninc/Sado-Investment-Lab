# AWAY Autonomy Hardening v1

Related: #354 #547 #556 #479 #480 #429

## 1. AWAY Queue Auto-Promotion

During `USER_MODE=AWAY`, an implementation run must not stop merely because its current work is complete.

When an implementation worker is `available` or `idle` and its open implementation PR count is `0`, run the read-only Queue Auto-Promotion selector before ending the run.

Selection remains fail-closed and must reuse the existing #480 Work Contract preflight and #556 selector. Do not create assignments, comments, dispatches, or merges solely from selector output.

Workers in `quota_blocked`, `blocked`, or unavailable states are excluded. Existing Single Implementation Owner, dependency, allowed-path, WIP, and Authority guards remain mandatory.

Result must be either one safe `SELECTED` candidate or a fail-closed reason such as `NO_SAFE_CANDIDATE`, `OWNER_CONFLICT`, `DEPENDENCY_BLOCKED`, `WORKER_BLOCKED`, or `PREFLIGHT_INVALID`.

## 2. User Mode transition CAS guard

Mode transition is a compare-and-set operation, not a normal stale mergeable edit.

Every transition record should carry:

- `transition_id`: unique per requested transition
- `expected_current_mode`: mode observed immediately before mutation
- `target_mode`: requested mode
- evidence timestamp / source

A transition must fail closed when:

- current mode differs from `expected_current_mode`
- `transition_id` has already been applied
- target equals current mode
- mode value is invalid

A stale ACTIVE/AWAY PR or delayed write must never overwrite a newer mode. `TEAM_STATE.md` on the default branch remains current-mode Authority; #99 mirrors it for routing visibility.

## 3. AWAY blocker classification

Every material AWAY blocker is classified before it is allowed to stop flow:

- `OWNER_AUTHORITY` — only class that must enter the Owner Authority backlog
- `REVIEW_WAIT`
- `CI_FAILURE`
- `DEPENDENCY`
- `MISSING_ARTIFACT`
- `TECHNICAL_INVESTIGATION`
- `TOOL_LIMIT`
- `EXTERNAL`
- `OWNER_CONFLICT`

Only `OWNER_AUTHORITY` may be treated as an Owner wait by default. All other classes require a concrete autonomous next action or a safe move to another non-conflicting READY item.

Authority backlog records contain:

- `ref`
- `class=OWNER_AUTHORITY`
- `decision_needed`
- `why_owner`
- `safe_work_completed`
- `next_action_on_active`

Do not bury `REVIEW_WAIT`, `CI_FAILURE`, dependency investigation, or quota/tool limits in the Owner backlog.

## Metrics

Feed #479 where available:

- `away_replenish_triggered`
- `queue_replenish_latency`
- `no_safe_candidate_count`
- `duplicate_start_prevented_count`
- `mode_transition_stale_rejected_count`
- blocker counts by class
- `owner_authority_backlog_count`

Unknown values remain `UNKNOWN`; do not infer them.

Issue #79 untouched.
