# Development Diary Daily Snapshot Collector v1

**Contract Reference**: `data/contracts/development-diary-daily-v1.schema.json`  
**Issue**: #730  
**Related**: #725 (Schema Validation), #645 (TEAM_STATE Implementation Start Definition)

---

## Purpose

The Development Diary Collector is a fail-closed telemetry system that captures daily GitHub activity evidence within precise JST day-boundaries. It generates validated JSON snapshots for productivity analysis, executor performance tracking, and flow health monitoring.

**Key Contracts**:
- **Half-open JST Window**: `[00:00 JST, next-day 00:00 JST)` – 23:59:59 JST is IN, 00:00:00 next day is OUT
- **Close Time**: Next day 00:10 JST (10-minute grace period)
- **Deduplication**: Stable event identities (PR/issue numbers) prevent double-counting on reruns
- **Implementation Start**: EXECUTION_EVIDENCE state only (DISPATCHED/ACKED are lease states, per TEAM_STATE #645)
- **Unavailable Metrics**: `null` not `0` (distinguishes absence from observed zero)
- **Late Evidence**: Correction audit trail (no silent rewrite)

---

## Architecture

### Data Collection Flow

```
GitHub API
   ↓ (fetch issues/PRs since window start)
   ↓
DailyCollector
   ├─ Event Deduplication (PR/Issue number tracking)
   ├─ JST Boundary Filtering [start, end)
   ├─ Executor Classification (COPILOT/DEPENDABOT/human)
   ├─ Task Class Mapping (labels → DOCS/BUGFIX/FEATURE...)
   └─ Statistics Aggregation by (executor, task_class)
   ↓
Snapshot Generation
   ├─ factory_output (ready → impl → pr → merge flow)
   ├─ executor_performance (per executor×task_class metrics)
   ├─ flow_health (WIP, starvation, conflicts)
   └─ economics (credits, costs, fallback)
   ↓
Schema Validation (fail-closed)
   ↓
JSON Persistence
```

### JST Boundary Precision

**Window Calculation**:
```python
def calc_window(diary_dt: date) -> tuple[datetime, datetime]:
    start = datetime.combine(diary_dt, time.min, tzinfo=JST)  # 00:00:00
    end = start + timedelta(days=1)                            # next day 00:00:00
    return start, end
```

**Half-Open Interval**:
```python
def in_range(ts: datetime | None, start: datetime, end: datetime) -> bool:
    return ts is not None and start <= ts < end
```

**Examples** (diary_date_jst = 2026-08-19):
- ✅ `2026-08-19T23:59:59+09:00` → IN (last second of day)
- ❌ `2026-08-20T00:00:00+09:00` → OUT (first second of next day)
- ❌ `2026-08-18T23:59:59+09:00` → OUT (previous day)

---

## Event Processing

### GitHub API Pagination

**Fetch Strategy**:
```python
def fetch_items(repo: str, token: str, since: datetime) -> list[dict]:
    """
    GET /repos/{owner}/{repo}/issues?state=all&sort=updated&since={since_utc}
    - Fetches ALL issues/PRs (closed/merged included via state=all)
    - Pagination: 100 items/page, max 50 pages
    - Filter: updated_at >= window start (in UTC)
    """
```

**Why `since` parameter**:  
Efficient API query – only fetches items with `updated_at >= window_start_jst`.  
This captures:
- New items created during window
- Existing items merged/closed during window
- Items with label changes during window

### Deduplication Mechanism

**Stable Identity**: PR/Issue number (unique per repository)

```python
class DailyCollector:
    def __init__(self, start, end):
        self.seen_pr: set[int] = set()
        self.seen_issue: set[int] = set()
    
    def process_pr(self, pr: dict) -> None:
        num = int(pr["number"])
        if num in self.seen_pr:
            return  # Already processed
        
        # ... process events ...
        self.seen_pr.add(num)
```

**Why deduplication matters**:  
GitHub API may return same item multiple times (e.g., PR #42 updated twice during window).  
Without deduplication: metrics double-count.  
With deduplication: exact counts even on reruns.

### Event Types & Timestamp Checks

**PR Events** (via `pull_request` key in issue response):
1. **PR Opened**: `created_at` in window → `pr_opened++`, executor `pr_count++`
2. **PR Merged**: `merged_at` in window → `pr_merged++`, executor `merge_count++`, `success_count++`
3. **PR Closed Unmerged**: `closed_at` in window AND `merged_at` is null → `pr_closed_unmerged++`

**Issue Events** (no `pull_request` key):
- **Ready Issue Created**: `created_at` in window + label "ready" or "ready-for-implementation" → `ready_count++`

**State Tracking Events** (manual calls, not from API):
- **DISPATCHED**: `record_dispatch(executor, task_class)` → `dispatch_count++`, `waiting_count++`
- **ACKED**: `record_ack(executor, task_class)` → `ack_count++`
- **EXECUTION_EVIDENCE**: `record_execution_evidence(executor, task_class)` → `execution_evidence_count++`, `impl_start++`, `active_wip++`

---

## Implementation Start Contract (TEAM_STATE #645)

**Question**: When does implementation actually start?

**Answer**: At EXECUTION_EVIDENCE state, NOT at DISPATCHED/ACKED.

### State Definitions

| State | Meaning | Counts as Implementation Start? |
|-------|---------|--------------------------------|
| **DISPATCHED** | Executor received lease (GH issue assignment) | ❌ NO |
| **ACKED** | Executor reserved work (GH comment acknowledgment) | ❌ NO |
| **EXECUTION_EVIDENCE** | Executor opened PR or committed code | ✅ YES |
| **PR_MERGED** | Work accepted | ✅ YES (completion) |

**Why this matters**:  
- **DISPATCHED/ACKED**: Work is queued/reserved but not started → `waiting_work_count` tracking
- **EXECUTION_EVIDENCE**: Actual coding begins → `implementation_start_count`, `active_implementation_wip`

**Code Implementation**:
```python
def record_dispatch(self, executor: str, task_cls: str) -> None:
    """DISPATCHED - lease only, NOT implementation (TEAM_STATE #645)."""
    key = (executor, task_cls)
    self.exec_stats[key]["dispatch_count"] += 1
    self.waiting_cnt += 1  # Waiting state, not WIP

def record_execution_evidence(self, executor: str, task_cls: str) -> None:
    """EXECUTION_EVIDENCE state - actual implementation start (TEAM_STATE #645)."""
    key = (executor, task_cls)
    self.exec_stats[key]["execution_evidence_count"] += 1
    self.impl_start_cnt += 1  # NOW counts as implementation start
    self.active_wip += 1      # Now in active WIP
```

**Metric Impact**:
```json
{
  "factory_output": {
    "implementation_start_count": 5  // ONLY EXECUTION_EVIDENCE state
  },
  "flow_health": {
    "active_implementation_wip": 3,   // EXECUTION_EVIDENCE in progress
    "waiting_work_count": 2           // DISPATCHED/ACKED waiting
  }
}
```

---

## Executor Classification

**Purpose**: Track performance by executor type (human vs bot vs copilot)

### Classification Logic

```python
def get_executor(pr: dict) -> str:
    user = pr.get("user", {})
    login = str(user.get("login", "")).lower()
    
    if "copilot" in login:    return "COPILOT"
    if "dependabot" in login: return "DEPENDABOT"
    if not login:             return "UNKNOWN"
    return login              # Preserve actual username
```

**Examples**:
- `copilot-bot` → `"COPILOT"`
- `github-copilot-autofix` → `"COPILOT"`
- `dependabot[bot]` → `"DEPENDABOT"`
- `alice` → `"alice"`
- `null` user → `"UNKNOWN"`

### Task Class Mapping

**Purpose**: Categorize work by label → task type

```python
def get_task_class(labels: list[dict]) -> str:
    names = {lbl.get("name", "").lower() for lbl in labels}
    
    if "documentation" in names or "docs" in names: return "DOCS"
    if "bug" in names or "bugfix" in names:         return "BUGFIX"
    if "feature" in names or "enhancement" in names: return "FEATURE"
    if "test" in names:                              return "TEST"
    if "refactor" in names:                          return "REFACTOR"
    if "performance" in names:                       return "PERFORMANCE"
    if "security" in names:                          return "SECURITY"
    return "GENERAL"
```

**Label Priority**: First match wins (order matters)

### Lossless (Executor, Task Class) Preservation

**Key Contract**: Same executor working on different task classes → separate performance records

```python
self.exec_stats: dict[tuple[str, str], dict] = defaultdict(...)
# Key: (executor, task_class)
# Value: { pr_count, merge_count, success_count, ... }
```

**Example**:
```python
coll.record_execution_evidence("alice", "DOCS")  # (alice, DOCS) → 1 impl
coll.record_execution_evidence("alice", "CODE")  # (alice, CODE) → 1 impl

# Snapshot output:
{
  "executor_performance": [
    {"executor": "alice", "task_class": "DOCS", "execution_evidence_count": 1, ...},
    {"executor": "alice", "task_class": "CODE", "execution_evidence_count": 1, ...}
  ]
}
```

**Why lossless matters**: Enables analysis like "alice is faster at DOCS than CODE" or "COPILOT excels at TEST tasks"

---

## Null vs Zero Semantics

**Contract**: `null` = unavailable/not yet tracked, `0` = observed zero

### When to use `null`

```python
{
  "factory_output": {
    "lead_time_minutes": None  # Not computed yet (requires PR pairing)
  },
  "flow_health": {
    "queue_replenish_latency_minutes": None,  # Requires historical data
    "durable_output_interval_minutes": None   # Needs time-series analysis
  },
  "economics": {
    "copilot_credits": None,           # API not available
    "ai_cost_per_merge": None          # Requires cost provider
  },
  "executor_performance": [
    {
      "elapsed_minutes": None,         # Timing data not captured
      "lead_time_minutes": None
    }
  ]
}
```

### When to use `0`

```python
{
  "factory_output": {
    "ready_count": 0,                  # Observed: no ready issues today
    "pr_opened": 0,                    # Observed: no PRs opened
    "pr_closed_unmerged": 0            # Observed: no unmerged closes
  },
  "flow_health": {
    "path_owner_conflict_count": 0,    # Observed: no conflicts
    "blocked_escape_count": 0          # Observed: no unblock events
  },
  "economics": {
    "paid_fallback_count": 0           # Observed: no paid API calls
  }
}
```

**Why this distinction matters**:  
- Downstream analysis can differentiate "haven't measured yet" vs "measured and found zero"
- Query: `WHERE lead_time IS NOT NULL` only includes records with measurements

---

## Late Evidence Correction Audit

**Problem**: Event arrives AFTER snapshot close time (e.g., PR merged at 00:15 JST for 00:10 JST close)

**Anti-Pattern**: Silent rewrite of past snapshots

**Solution**: Correction audit trail

### Correction Record Structure

```python
def add_correction(self, reason: str, evidence_refs: list[str], recorded: datetime) -> None:
    ev_str = "|".join(sorted(evidence_refs))
    corr_hash = hashlib.sha256(ev_str.encode()).hexdigest()[:16]
    corr_id = f"corr-{corr_hash}"
    
    if corr_id in self.seen_corr:  # Deduplication
        return
    
    self.corrections.append({
        "correction_id": corr_id,           # Stable identity (hash of evidence refs)
        "reason": reason,                   # Why correction needed
        "evidence_refs": evidence_refs,     # ["pr:#999", "issue:#123"]
        "recorded_at": recorded.isoformat() # When detected (UTC)
    })
```

**Example Correction**:
```json
{
  "diary_date_jst": "2026-08-19",
  "corrections": [
    {
      "correction_id": "corr-a1b2c3d4e5f6g7h8",
      "reason": "late merge detected: PR #999 merged at 00:15 JST, after 00:10 close",
      "evidence_refs": ["pr:#999"],
      "recorded_at": "2026-08-20T00:20:00+09:00"
    }
  ]
}
```

**Workflow**:
1. Snapshot closes at 00:10 JST
2. PR merges at 00:15 JST (late by 5 minutes)
3. Next collection run detects late evidence
4. Correction audit record appended to snapshot
5. Analyst reviews correction, adjusts analysis if needed

**Benefits**:
- Preserves original snapshot integrity (no silent mutation)
- Provides audit trail for data forensics
- Enables correction factor calculation

---

## Snapshot Schema Structure

**Contract Reference**: `data/contracts/development-diary-daily-v1.schema.json`

```json
{
  "schema_version": "1.0",
  "diary_date_jst": "2026-08-19",
  "closed_at_jst": "2026-08-20T00:10:00+09:00",
  "source_window_start_jst": "2026-08-19T00:00:00+09:00",
  "source_window_end_jst": "2026-08-20T00:00:00+09:00",
  
  "factory_output": {
    "ready_count": 5,                    // Issues marked ready today
    "implementation_start_count": 3,     // EXECUTION_EVIDENCE events
    "pr_opened": 4,                      // PRs created today
    "pr_merged": 2,                      // PRs merged today
    "pr_closed_unmerged": 1,             // PRs closed without merge
    "durable_output_count": 2,           // Alias for pr_merged
    "productive_step_count": 6,          // pr_opened + pr_merged
    "lead_time_minutes": null            // Not computed yet
  },
  
  "executor_performance": [
    {
      "executor": "alice",
      "task_class": "FEATURE",
      "dispatch_count": 1,
      "ack_count": 0,
      "execution_evidence_count": 1,     // Started 1 implementation
      "pr_count": 1,
      "merge_count": 1,
      "success_count": 1,
      "failure_count": 0,
      "terminal_noop_count": 0,
      "elapsed_minutes": null,
      "lead_time_minutes": null,
      "rework_count": 0,
      "duplicate_conflict_waste_count": 0
    }
  ],
  
  "flow_health": {
    "active_implementation_wip": 1,      // EXECUTION_EVIDENCE in progress
    "waiting_work_count": 2,             // DISPATCHED/ACKED waiting
    "ready_nonconflicting_count": 5,     // Ready issues no path conflicts
    "starvation_state": "UNKNOWN"
  },
  
  "economics": { ... },
  "factory_capability_changes": [],
  "corrections": []
}
```

---

## Usage Examples

### CLI Invocation

```bash
# Collect snapshot for 2026-08-19
python scripts/development_diary_collector.py \
  --repo owner/repo \
  --diary-date 2026-08-19 \
  --output data/diary/2026-08-19.json

# Validate existing snapshot
python scripts/development_diary_collector.py \
  --validate-only \
  --output data/diary/2026-08-19.json
```

### Programmatic Usage

```python
from scripts.development_diary_collector import collect
from datetime import date

snap = collect(
    repo="owner/repo",
    token=os.environ["GITHUB_TOKEN"],
    diary_dt=date(2026, 8, 19),
    close_at=None  # Default: next day 00:10 JST
)

print(f"PRs merged: {snap['factory_output']['pr_merged']}")
print(f"Impl started: {snap['factory_output']['implementation_start_count']}")
```

---

## Fail-Closed Validation

**Contract**: MUST validate snapshot before persistence

```python
def collect(...) -> dict:
    # ... build snapshot ...
    
    # Fail-closed: raises ValidationError if invalid
    validate_snapshot(snap)
    
    return snap  # Only valid snapshots returned
```

**What gets validated** (via JSON Schema):
- Required fields present
- Integer counts non-negative
- Timestamps well-formed (ISO 8601 with timezone)
- Enum fields (e.g., `starvation_state`) valid values
- Executor/task_class arrays well-formed

**Why fail-closed**:  
Prevents corrupt data from entering analysis pipeline. Better to fail loudly than silently persist invalid data.

---

## Test Coverage

**File**: `tests/test_development_diary_collector.py`

**Key Test Classes**:
1. **TestJSTBoundaries** – Half-open interval correctness
2. **TestEventDeduplication** – Rerun safety
3. **TestDispatchedAcked** – TEAM_STATE #645 contract
4. **TestExecutionEvidence** – Implementation start counting
5. **TestUnavailableMetrics** – Null vs zero semantics
6. **TestLateEvidenceCorrection** – Audit trail generation
7. **TestInvalidSnapshot** – Fail-closed validation

---

## Future Enhancements

1. **Lead Time Calculation**: Pair issue creation → PR merge timestamps
2. **WIP Age Tracking**: Measure how long PRs stay open
3. **Cost API Integration**: Populate `economics.copilot_credits` from GitHub Copilot API
4. **Path Conflict Detection**: Count executor collisions on same files
5. **Automated Correction Application**: Replay corrections into corrected snapshot versions

---

## See Also

- **Schema Definition**: `data/contracts/development-diary-daily-v1.schema.json`
- **Test Suite**: `tests/test_development_diary_collector.py`
- **TEAM_STATE #645**: Implementation start state machine
- **Issue #725**: Schema validation infrastructure
- **Issue #730**: This documentation (Issue reference)
