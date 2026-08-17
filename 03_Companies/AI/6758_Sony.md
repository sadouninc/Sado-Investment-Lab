# Sony Group (6758) — Investment Decision Board Handoff

担当: ❤️レイ  
関連Issue: #403  
状態: `BOARD_RECORD_READY_FOR_IMPLEMENTATION`  
用途: Investment Decision Board / Entry Review の canonical handoff

## Review State

- Security: Sony Group (6758)
- Review state: `STRONG WATCH / ENTRY REVIEW`
- Final authority: 👑サド / Decision layer
- Position state: Canonical Portfolio Stateから取得し、Research側では推測しない

## Why Now

SonyはEntertainment/IPとImaging & Sensing Solutions (I&SS)という複数の利益エンジンを持つ。FY2026 Q1ではI&SSの増益寄与が大きく、Image Sensorを単なるスマートフォン部材ではなく、将来のAI Vision / robotics / Physical AIへのoptionalityとして追跡する価値が高まっている。

## Canonical Earnings Snapshot — FY2026 Q1

Authority: Sony FY2026 Q1 official IR materials (2026-07-31)

- Consolidated sales: 2.84 trillion JPY
- Operating income: 476.5 billion JPY, +40% YoY
- Diluted EPS (Q1 actual): 57.82 JPY
- I&SS sales: 512.7 billion JPY
- I&SS operating income: 122.2 billion JPY, +125% YoY
- I&SS operating-income YoY contribution: approximately +68.0 billion JPY
- G&NS operating-income YoY contribution: approximately +54.1 billion JPY

## FY2026 Company Outlook

- Consolidated operating-income outlook: 1.72 trillion JPY after upward revision
- Net-income outlook: 1.21 trillion JPY after upward revision
- I&SS operating-income outlook: 420 billion JPY, revised from 400 billion JPY

Risk flag: Kumamoto earthquake impact is not treated as fully reflected unless the company explicitly incorporates it into guidance.

## Earnings Engine

1. Game & Network Services — installed base / engagement / software & network economics
2. Music / Pictures / IP — recurring and portfolio-driven entertainment earnings
3. Imaging & Sensing Solutions — image-sensor volume, mix, yield, advanced process and capacity
4. AI / Physical AI optionality — AI Vision, industrial sensing, robotics and automotive sensing; not current realized earnings unless evidenced

## Observation vs Inference

### Observation

- FY2026 Q1 consolidated operating profit increased strongly.
- I&SS was a major contributor to YoY operating-profit growth.
- Sony raised consolidated and I&SS full-year operating-profit outlooks.
- Sony continues to invest in image-sensor competitiveness.

### Inference / Hypothesis

- Image Sensor may gain a second structural demand leg from AI Vision / robotics / Physical AI in addition to smartphone imaging.
- Multiple earnings engines may reduce dependence on any single product cycle and support valuation resilience.
- Physical AI is an option value only; it must not be presented as current earnings realization.

## Valuation Contract

Fail closed until all basis fields align.

Required fields before displaying Forward PER:

- `price`
- `price_as_of`
- `scenario_as_of`
- `share_basis`
- Bear / Base / Bull EPS or another canonical forward-EPS authority

Do **not** annualize Q1 diluted EPS 57.82 JPY by multiplying by four. Company full-year EPS is not inferred mechanically from one quarter.

Share-count reference only:

- issued shares at 2026-06-30: 5,965,316,326
- treasury shares: approximately 92.86 million

These values are not equivalent to FY2026 diluted weighted-average shares and therefore must not be silently used as the EPS denominator.

### Canonical Current Valuation Consumer — #633 PR2

Current-price valuation must consume `scripts/sony_canonical_valuation.py`, which in turn accepts only the Canonical Market Data record and the shared Price Identity Gate from #633 PR1. The Decision Board (#403) and Fair PER consumer (#626) receive the same immutable valuation result from one calculation run; neither consumer may fetch or substitute a Web/legacy price independently.

Current price / current PER / fair-value gap are available only when all of the following are true:

- `usable_for_current_valuation == true`
- `identity_status == VERIFIED`
- `freshness_status == FRESH`
- `provider_status == OK`
- `not_market_truth == false`
- Sony identity, exact trading date, close/intraday type and adjustment basis match the consumer expectation

If the canonical gate fails or is UNKNOWN, current price / current PER / fair-value gap remain `UNKNOWN`; stale, previous-year, other-ticker, fixture or provider-failure values are never used as fallback. Research-derived Fair Value Range may still exist independently of current market-price usability.

`price_as_of` and `scenario_as_of` remain separate authorities. A fresh price does not upgrade a missing or stale Research scenario. `Fair Value Range != Entry Zone`; this consumer never generates Entry Zone or BUY/SELL/HOLD.

## Scenario Contract

Until a canonical forward-EPS model is approved:

- Bear EPS: `UNKNOWN`
- Base EPS: `UNKNOWN`
- Bull EPS: `UNKNOWN`
- Forward PER: `UNKNOWN`

Scenario construction should explicitly state assumptions for G&NS, I&SS, Entertainment/IP, FX, tax and share basis.

## Catalysts

- Additional earnings-guidance upgrades
- I&SS margin / mix improvement
- Image-sensor demand or capacity evidence stronger than current assumptions
- Concrete AI Vision / robotics design wins or orders
- Evidence that new sensor investment advances from investment/capacity to revenue and profit

## Invalidation / Risks

- Smartphone sensor demand deterioration or pricing pressure
- I&SS capex failing to translate into adequate returns
- Game engagement / monetization deterioration
- Entertainment hit-cycle weakness
- Earthquake / supply-chain impact larger than guidance
- Physical AI narrative advancing without orders, revenue or profit evidence

## Next Checkpoints

1. Canonical forward EPS / diluted-share basis
2. Fresh market price with `price_as_of`
3. Bear / Base / Bull scenario approval
4. Next earnings revision and I&SS guidance
5. AI Vision / robotics: `announcement → design win → order → revenue → profit`
6. Image Sensor investment: `capex → capacity → shipment → revenue → profit`

## Board Presentation Contract

The Board should display Sony as one existing Investment Review record, not create a Sony-specific parallel truth.

Minimum mobile view:

- `6758 Sony Group`
- `STRONG WATCH / ENTRY REVIEW`
- Why Now
- Earnings Engine
- Latest Earnings Change
- Bear / Base / Bull
- Valuation + freshness
- Catalysts
- Invalidation
- Next Checkpoint
- Evidence provenance

Pages/presentation must not independently generate BUY/SELL or target-entry prices. Unknown/stale values remain visibly `UNKNOWN` rather than being replaced by estimates.
