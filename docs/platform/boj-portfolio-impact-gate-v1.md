# BOJ Portfolio Impact Gate v1 Platform Contract

担当: 🌅アサヒ / 🤖 Jules
種別: Product / Platform Contract
Issue: #512
Status: ACTIVE

## 1. Executive Summary & Purpose
`BOJ Portfolio Impact Gate v1` (`scripts/boj_portfolio_impact_gate.py`) provides an early-warning, read-only projection of Bank of Japan (BOJ) monetary policy rate hike risk onto canonical portfolio holdings (`data/portfolio/current.json`).

The gate consumes existing market weather, intraday delta, and canonical research evidence artifacts without creating a second market collector, trading control plane, or static facts database. It projects per-position impact actions (`HOLD`, `WATCH`, `REDUCE_CANDIDATE`, `EXIT_REVIEW`) for review in the Morning Portfolio Check (#46).

**Key Invariant**: The gate generates **NO automated orders** (no BUY/SELL) and does not alter Owner Authority. Final investment decisions remain strictly with Owner Authority.

---

## 2. Signal State Contract & Primary Evidence Requirement

| Signal State | Description & Criteria | De-risk Action Eligibility |
|---|---|---|
| **GREEN** | Weak primary evidence; no significant market probability surge. | Default `HOLD`. No BOJ de-risk actions. |
| **ORANGE** | Inflation/import price surge, hawkish BOJ committee breadth, or rising market OIS probability. | High-sensitivity long positions set to `WATCH` (or `REDUCE_CANDIDATE` if overlapping with position-scoped weak Market Phase/event risk). |
| **RED** | **Requires Primary BOJ Evidence**: Governor/Board explicit guidance, Summary of Opinions/Outlook statement, actual rate decision, or explicit Market Weather RED threshold. | High-sensitivity long positions set to `REDUCE_CANDIDATE` review (or `EXIT_REVIEW` if overlapping with position-scoped thesis invalidation/liquidity/leverage risk). |
| **UNKNOWN** | **Fail-Closed Default**: Missing, unparseable, or invalid signal state. | Fails closed to `WATCH` (or `HOLD` if GREEN). Never coerced to `PASS` or `ORANGE`. |

### Fail-Closed Capping Rule
- **Market-implied probability alone CANNOT produce `RED`.**
- If an input signal requests `RED` but lacks primary evidence (`probability_only: true`), the gate automatically caps the effective signal state at `ORANGE` with `[CAPPED_AT_ORANGE]` recorded in signal provenance.

---

## 3. Position Sensitivity Schema & Fail-Closed Rules

Each position is dynamically evaluated against 5 sensitivity dimensions loaded read-only from canonical research evidence (`06_Research/boj_evidence/*.md`):
1. `rate_sensitivity`: `LOW` \| `MEDIUM` \| `HIGH` \| `UNKNOWN`
2. `yen_sensitivity`: `BENEFIT` \| `NEUTRAL` \| `HEADWIND` \| `MIXED` \| `UNKNOWN`
3. `energy_input_sensitivity`: `LOW` \| `MEDIUM` \| `HIGH` \| `UNKNOWN`
4. `valuation_duration`: `LOW` \| `MEDIUM` \| `HIGH` \| `UNKNOWN`
5. `balance_sheet_rate_risk`: `LOW` \| `MEDIUM` \| `HIGH` \| `UNKNOWN`

### Fail-Closed Invariants
- Missing or ambiguous sensitivity data defaults strictly to `UNKNOWN`. No hard-coded fact databases exist in runtime code.
- `UNKNOWN` sensitivity is **NEVER coerced to `LOW` or `HOLD`**.
- A position with incomplete/mixed sensitivity facts (any dimension `UNKNOWN`) **CANNOT produce `REDUCE_CANDIDATE` or `EXIT_REVIEW`**. It fails closed to `WATCH` for monitoring.

---

## 4. Position Side Preservation & Risk Scoping

### Short Positions
- Position side is preserved as `position_side: "SHORT"` (mapped from `margin_short`).
- **Short positions do NOT inherit long de-risk actions** (`REDUCE_CANDIDATE` or `EXIT_REVIEW`). Their BOJ risk action remains `HOLD` or `WATCH`.

### Unknown Position Types
- Unrecognized or unsupported position types map to `position_side: "UNKNOWN"`.
- Action fails closed to `WATCH`.

### Position-Scoped Risk Context
- Risk context flags (`thesis_invalidation`, `liquidity_risk`, `leverage_risk`, `market_phase_weak`, `event_risk`) are **strictly scoped per position identity (`security_code`)**.
- Overlapping risk for one holding cannot leak globally to trigger `EXIT_REVIEW` on unrelated positions.

### Long Positions Action Derivation
- **GREEN**: Action remains `HOLD`.
- **ORANGE**:
  - High sensitivity + complete facts => `WATCH`.
  - High sensitivity + position-scoped weak Market Phase/event risk => `REDUCE_CANDIDATE`.
  - Low/Medium sensitivity => `HOLD`.
  - Incomplete/unknown sensitivity => `WATCH` (fail-closed).
- **RED**:
  - High sensitivity + complete facts => `REDUCE_CANDIDATE`.
  - High sensitivity + complete facts + position-scoped thesis invalidation/liquidity/leverage risk => `EXIT_REVIEW`.
  - **BOJ RED alone CANNOT produce `EXIT_REVIEW`**.
  - Incomplete/unknown sensitivity => `WATCH` (fail-closed).

---

## 5. System Integration & Execution Guardrails

- **Read-Only Integration**: Output is projected into Morning Portfolio Check (#46) and Home dashboard.
- **Canonical SSoT**: Holdings are loaded strictly from `data/portfolio/current.json` (verified SBI holdings SSoT).
- **Execution Off**: `AUTO_GREEN` execution remains OFF.
- **Issue #79**: Hard deny — Issue #79 remains completely untouched.

---

## 6. CLI Execution

```bash
# Execute read-only impact projection using canonical defaults
python3 scripts/boj_portfolio_impact_gate.py

# Execute with explicit holdings or signal input
python3 scripts/boj_portfolio_impact_gate.py --holdings data/portfolio/current.json --signal path/to/signal.json --out /tmp/impact.json
```
