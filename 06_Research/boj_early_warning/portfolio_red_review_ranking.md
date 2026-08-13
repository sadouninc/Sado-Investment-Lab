# BOJ Early Warning — Portfolio RED Review Ranking

Status: REVIEW CONTRACT / no automatic trading
Owner: 🌅アサヒ
Refs: #512

## Purpose
When BOJ Early Warning moves ORANGE → RED, prioritize **human review of current positions before broad market drawdown**. This is not a SELL list and must not generate orders automatically.

## Ranking dimensions
Use the canonical portfolio snapshot plus verified company evidence. Review priority is determined by the combination of:

1. rate_sensitivity
2. valuation_duration
3. balance_sheet_rate_risk
4. yen_sensitivity
5. energy_input_sensitivity
6. position_side (LONG / SHORT)
7. portfolio impact (position size / leverage / concentration)

UNKNOWN never receives a guessed score. UNKNOWN increases review uncertainty and triggers evidence follow-up.

## RED review lanes

### Tier A — immediate review on BOJ RED
- さくらインターネット — HIGH direct funding / capex sensitivity + HIGH valuation duration.
- Aiロボティクス — HIGH funding sensitivity + HIGH valuation duration; bridge / short-term financing is a key transmission path.
- GENDA — HIGH balance-sheet / M&A funding sensitivity.
- 日東紡 — direct rate sensitivity is not the highest, but portfolio impact is elevated by the canonical leveraged LONG position; capex and valuation channels matter.
- ispace — HIGH valuation duration and future funding environment sensitivity.

Action: `REDUCE_CANDIDATE_REVIEW` only. No automatic reduction.

### Tier B — conditional RED review
- オンコリスバイオファーマ — HIGH valuation duration; escalate if funding/runway or biotech risk-off evidence overlaps.
- サンバイオ — HIGH valuation duration; same overlap rule.
- フィックスターズ — financially resilient in verified evidence, but HIGH valuation duration can compress under higher discount rates.
- 浜松ホトニクス — valuation + FX + energy overlap.
- ダイヘン — FX + input-cost overlap; company planning assumptions must be compared with actual JPY and materials environment.
- 古河電工 — FX / industrial-cycle / financing evidence follow-up required where UNKNOWN remains.
- 富士通 — valuation / FX / financing channels; direct debt sensitivity requires latest verified debt structure.

Action: `WATCH` → `REDUCE_CANDIDATE_REVIEW` only when BOJ RED overlaps with company-specific or market-confirmation evidence.

### Tier C — monitor / lower direct BOJ sensitivity
- 信越化学 — strong verified balance sheet; monitor valuation, JPY and energy rather than direct debt stress.
- 積水化学 — domestic demand / housing / FX transmission more important than immediate funding stress.
- NTT — large financing/capex footprint but recurring telecom cash flow is a buffer; fixed/variable debt evidence remains an important checkpoint.
- 三菱重工 — monitor JPY translation / export economics and funding, not rate shock alone.
- 日本ギア工業 — retain fail-closed treatment until latest debt structure is fully verified.

Action: WATCH; BOJ RED alone is insufficient for reduction review unless portfolio or company evidence materially changes.

### Separate SHORT lane
- 飯田グループホールディングス — canonical position is SHORT. Higher mortgage rates can weaken housing demand, so the portfolio direction differs from LONG positions.

Action: `SHORT_THESIS_REVIEW`; never mechanically increase the short solely because BOJ becomes RED.

## RED confirmation gate
BOJ RED should require more than a single market-implied probability. Use corroboration across primary-policy evidence and/or multiple market sensors such as short JGB/OIS repricing, JPY regime shift, and equity factor rotation. Market probability alone does not create RED.

## Execution guardrails
- No BUY / SELL / HOLD order generation.
- No automatic position mutation.
- Canonical portfolio snapshot is the only source for side/quantity.
- Re-rank whenever canonical holdings change materially.
- If a position has UNKNOWN evidence, surface the UNKNOWN explicitly rather than infer it.

## Next checkpoints
1. Resolve remaining UNKNOWN fixed/variable debt and maturity-ladder evidence from primary IR.
2. Connect BOJ RED state to Portfolio Check as a read-only review trigger.
3. Surface Tier A first in owner-facing alert output, with the specific evidence that caused RED.
4. Recalculate portfolio-impact ordering after every VERIFIED holdings snapshot.