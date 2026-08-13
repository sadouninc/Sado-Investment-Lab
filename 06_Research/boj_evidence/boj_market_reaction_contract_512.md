# BOJ Market Reaction Contract — Issue #512

担当: 🌅アサヒ
種別: Research Contract / Policy Intelligence

## Four-layer model
1. fundamental_rate_sensitivity
2. boj_market_reaction_sensitivity
3. boj_anticipation_beta
4. positioning_follower_risk

## Benchmark rule
- Prime: TOPIX
- Growth: Growth250
- event_excess_return = stock_return - benchmark_return

## Event context
Each event keeps:
- event_type
- surprise/pricing context
- stock return
- benchmark return
- excess return
- JGB / FX context when available
- confounded flag
- company-specific catalyst refs

## Classification guard
- Do not classify HIGH from one event
- Opposite-sign reactions across events imply CONTEXT_SENSITIVE / UNRESOLVED
- Missing benchmark or corporate-action normalization => UNKNOWN
- Anticipation window is more important than announcement day for Early Warning

## Anticipation window schema
```yaml
window_start: YYYY-MM-DD
window_end: YYYY-MM-DD
hike_probability_start: UNKNOWN
hike_probability_end: UNKNOWN
stock_return: UNKNOWN
benchmark_return: UNKNOWN
excess_return: UNKNOWN
jgb_2y_change: UNKNOWN
usd_jpy_change: UNKNOWN
confounded: false
```

BUY/SELL自動生成なし。Issue #79 untouched。
