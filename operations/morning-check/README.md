# Morning Check v1

This directory is the human-readable operating procedure for the Morning Check. The machine-readable semantic SSoT is `data/config/morning-check-v1.json`; this document explains that contract and MUST NOT override or reinterpret it.

## Canonical report order

Every Morning Check keeps these eight sections, in this exact order:

1. **Overnight** — current-market overnight evidence.
2. **Japan Setup** — current-market evidence for the Japan session setup.
3. **Money Flow** — derived money-flow evidence.
4. **Portfolio Risk** — portfolio state read from the GitHub SSoT.
5. **Watchlist** — watchlist state read from the GitHub SSoT.
6. **Events** — relevant official-IR event evidence.
7. **Morning Hypothesis** — a derived hypothesis from the available evidence.
8. **Confidence+Invalidation** — confidence and explicit invalidation conditions for the hypothesis.

The stable mobile-friendly presentation is: section heading → compact evidence → status/unknown marker → interpretation where applicable. The order is fixed so the report can be understood quickly and compared across days.

## Evidence and source classes

Inputs fall into three operational classes:

- **Automatically retrievable:** current-market and official-IR evidence obtained from authoritative/current sources.
- **Repository-derived:** GitHub SSoT state such as portfolio and watchlist truth.
- **Derived or manual:** calculations, hypotheses, confidence/invalidation, and any evidence that requires human collection or confirmation.

Existing analytics and repository truth are consumed as inputs. Morning Check does not reimplement collectors, portfolio logic, analytics, or investment thresholds.

## Fail-closed missing-data rule

The contract's `missing_data_policy` is `UNKNOWN_OR_MISSING_NO_SILENT_ZERO_OR_NEUTRAL`.

If a required input cannot be established, show **UNKNOWN** or **MISSING** as specified by the machine-readable contract. Never silently substitute zero, neutral, unchanged, or a guessed value. Missing evidence cannot become PASS.

## Decision boundaries

Keep **fact**, **hypothesis**, and **action-candidate** separate:

- **Fact:** observed or repository-backed evidence.
- **Hypothesis:** an interpretation derived from facts, with uncertainty visible.
- **Action-candidate:** a possible action for consideration; it is not an automated order or final investment decision.

`owner_final_judgment_required=true` is authoritative. The Owner makes the final judgment. Morning Check does not generate or execute BUY/SELL/HOLD decisions.

## Version and change management

The procedure version follows `routine_version` in the machine-readable SSoT. Semantic changes start with the JSON contract and its validator/tests, then the human-readable procedure is updated to match. Documentation-only clarification must not change machine semantics. Record procedure/version changes in `changelog.md` with provenance.

Daily-journal integration, schedulers/workflows, data collectors, report generators, and portfolio/trade mutation are outside v1 procedure scope.
