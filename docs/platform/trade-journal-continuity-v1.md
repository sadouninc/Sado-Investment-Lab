# Trade Journal Continuity v1

## Problem
August 2026 trade/decision journals are split across multiple canonical-looking locations and merge states.

Observed on production Pages / main as of 2026-08-20 JST:
- `01_Portfolio/Transactions/2026-08-19.md` exists and is listed.
- `01_Portfolio/Transactions/2026-08-14.md` exists and is listed.
- 2026-08-17 journal exists only in open PR #696 under `05_Decision_Log/2026-08-17_Trade_Journal.md`, so production Pages cannot show it yet.
- 2026-08-18 has no confirmed daily journal artifact on main; do not fabricate one without evidence.
- Some dates such as 2026-08-11 / 2026-08-13 are represented from the monthly aggregate `01_Portfolio/Transactions/2026-08.md`, which creates inconsistent filename/source semantics in the Journal index.

## Product contract
1. Daily Journal index must derive from one deterministic daily-entry contract.
2. A daily entry may consume execution facts from Transactions and decision context from Decision Log, but the index must expose one day-level record per date.
3. Missing dates must remain explicitly missing/unknown; do not synthesize trades or decisions.
4. Open/unmerged PR content is not production truth.
5. Monthly aggregate files are historical compatibility inputs, not preferred new daily journal storage.
6. Facts, owner judgments, hypotheses, and unexecuted orders remain distinct.
7. SBI/other broker evidence outranks chat approximation when exact execution facts exist.

## Immediate reconciliation targets
- 2026-08-17: merge/reconcile #696 into the daily Journal path/index without losing its verified executions.
- 2026-08-18: search durable evidence first; create a daily journal only when evidence/context is sufficient. Otherwise show `記録なし / 未取得` rather than silently skipping if the product chooses calendar continuity.
- 2026-08-19: preserve current reconciled execution fact (Fujitsu 100 shares margin buy at average 3,614 JPY).

## Acceptance
- August index no longer gives a misleading impression that durable journals vanished when they merely live in another path/open PR.
- 2026-08-17 becomes reachable after its canonical PR is merged/reconciled.
- 2026-08-18 is never invented.
- index source filename/title semantics are consistent.
- deterministic regression covers mixed monthly legacy + daily files + missing day + open-PR exclusion.
- no portfolio mutation from the index builder.
- no BUY/SELL authority generation.
- Issue #79 untouched.
