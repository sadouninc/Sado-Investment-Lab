# #477 Quantum Policy Lead-Time — Pages Visual Prototype Contract

担当: ⭐️ミナ  
種別: Product UI Design / Policy Visualization  
Status: IMPLEMENTATION_HANDOFF_READY  
Related: #477 / #255 / #459 / #320

## Goal

Quantum固有の第二UIを作らず、既存Policy Lead-Time rendererへread-only追加する時の30秒理解性と因果誤認防止を固定する。

## Owner first-view

1. Theme identity + freshness / as_of
2. Current classification
3. Policy checkpoint → Market response timing
4. Limitations
5. Details / evidence

## Classification contract

表示対象:
- POLICY_LEADS
- MARKET_LEADS
- POLICY_CONFIRMATION
- REACCELERATION_AFTER_POLICY
- INCONCLUSIVE
- DATA_LIMITED

重要:
- classificationはbrowserで再計算しない。
- `REACCELERATION_AFTER_POLICY` は「政策後に再加速を観測」であり、政策が原因という意味にしない。
- `DATA_LIMITED` / missing / unavailableをnegativeやCOLDへ丸めない。

## Timeline hierarchy

各checkpointは以下を1 unitとして表示:
- policy date / user-facing label
- market state before / at policy
- first reliable WARMING / INFLOW
- policy_to_warming_days / policy_to_inflow_days
- strongest post state
- classification

Mobileでは横長timelineを縮小せず、checkpointごとのvertical cardへ変換する。

## Human-readable limitations

Canonical 4 limitations:
- RETROSPECTIVE_MEMBERSHIP → 現在の採択basketを過去年にも遡って比較しています
- THEME_SCOPE_PROXY → 日本の量子産業全体ではなくsystem/component proxyです
- CONGLOMERATE_EXPOSURE → 各社は量子以外の事業規模が大きく、株価要因を量子だけへ帰属できません
- NARROW_MEMBERSHIP → 上場5社の狭いbasketです

内部codeだけをfirst-viewへ露出しない。日本語説明を主、codeはdetailsへ。

## Mobile 390px

- first viewportに `Quantum / as_of / classification / 因果ではない` が見える。
- 1 checkpoint = 1 vertical card。
- policy dateとmarket reaction dateの視覚差を明確にする。
- days deltaは大きな数値で見せても「効果」や「impact」と呼ばない。
- limitationsは最低1つのsummaryをfirst-view近傍に表示し、完全版はdetails可。

## Design Gate

### BLOCKER
- `REACCELERATION_AFTER_POLICY` を因果表現へ変換
- Policy EvidenceをMoney Flow scoreの一部に見せる
- classificationをbrowser/UI側で再計算
- missing/unavailableを0/COLD/negativeへ変換
- Quantum専用CSS/themeを新設
- mobileで横長timeline/tableだけを提供

### SHOULD_FIX
- limitation codeだけで人間向け説明がない
- policy checkpointとmarket stateの時間軸が視覚的に混同
- classificationより企業名一覧が先に主役になる
- as_of / freshnessがfirst-viewから遠い

### NICE_TO_HAVE
- theme switcherでFusion / Physical AI / Quantumを同じrenderer内比較
- checkpoint details accordion
- evidence source count / traceability summary

Result: **PASS_WITH_NOTES — PR4 implementation may proceed after canonical artifact is available.**

## Responsibility boundary

Policy Lead-Time Pages = Learning / observation。Company Research = individual business interpretation。Cockpit = investment decision context。

PagesはBUY/SELL/HOLD、winner、政策恩恵スコアを生成しない。

Issue #79 untouched.
Broadcast checked through: comment_id=5276694845 — VERIFIED
TEAM_STATE User Mode: ACTIVE
