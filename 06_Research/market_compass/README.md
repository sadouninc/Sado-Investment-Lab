# Market Compass Research Evidence

This directory stores prospective, machine-readable observation artifacts for the Market Compass research lane.

## Authority
- Sensor/state contract: Issue #568
- BOJ precursor contract: Issue #512
- First live prospective case: Issue #590
- Portfolio execution/position evidence: Issue #564

## Rules
- Do not rewrite frozen thresholds after outcomes are known.
- Observation facts and inference must remain separable.
- `UNKNOWN` is not zero.
- Stock/benchmark relative-return observations require same-source/same-close basis.
- A price decline alone is not a re-entry signal.
- `RE_ENTRY_READY` requires the #568 risk-stabilization gate.

## Current artifact
- `w33_reentry_watch_v0_1.json`: W33 confirmed exits, fixed benchmark assignment, exit anchors, initial integrity state, and next checkpoints for the first BOJ RED live case.
