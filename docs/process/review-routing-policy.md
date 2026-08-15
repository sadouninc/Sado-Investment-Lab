# Risk / Scope-driven Review Routing

担当: 🌊ナギ  
種別: Process / Review Flow Reliability

## 目的

全PRへProduct / Research / Design / Technical等を機械的に要求してREVIEW_WAITを増幅させない。PRが実際に変更するrisk / authority surfaceだけをblocking reviewとする。

## Default blocking review

原則1〜2系統。

| Change surface | Blocking Gate |
| --- | --- |
| backend / test / refactor | Technical 1 |
| Process / Flow tooling | Technical / Flow 1 |
| UI / visual | Technical + Design |
| Market / Research truth | Technical + Research |
| Product / valuation semantics | Technical + Product |
| workflow / secrets / security-sensitive | Technical + Security / Flow |
| docs-only / non-semantic | relevant reviewer 1 |

Product semanticsとmarket truthを同時変更する場合、Owner Authorityやsecurity-sensitive等、Authority上必要なGateは2系統上限を理由に削除しない。`blocking_gate_count > 2` は明示exceptionとして記録する。

Scope外specialistは `FYI / NON_BLOCKING`。UNKNOWN surfaceは推測せずfail closedでreview surfaceを確定する。

## Latest-head contract

- CIは常にlatest head必須。
- Review GateはそのGateが担当するsemantic surfaceへ最新差分が触れた場合だけ再review。
- 差分がGate surfaceへ影響しないと明示でき、prior evidenceがPASS/PASS_WITH_NOTESならcarry-forward可。
- changed surface / prior evidenceがUNKNOWNならcarry-forward禁止。
- reviewer自身の指摘修正だけでauthority surfaceを増やしていない場合、そのreviewer + required Technical/CIでclose可能を基本とする。

## Review SLA / Escape

- Primary blocking review target: 60分
- Specialist blocking review target: 120分
- SLA超過かつqualified alternate reviewerが存在 → `REROUTE_REVIEW`
- 必須Gateでalternate不在 → Gateを勝手に削除せず `BLOCKED_ESCAPE_KEEP_REQUIRED_GATE`。implementation capacityは解放し別workへ進む。
- REVIEW_WAITはactive implementation WIPを消費しない。

## Specialist fallback

### Design
1. Primary: ⭐️ミナ
2. Existing Visual Contract / Design System / approved baselineへの適合確認のみなら、⭐️ミナ不在時に🌙ルナへfallback可能。
3. 新規Design System / visual identity /大きなUX authority surfaceは🌙ルナへ暗黙委譲しない。`DESIGN_AUTHORITY_REQUIRED`としてfail closedするが、実装lane自体はBLOCKED_ESCAPEして別workへ進む。

Principle: `reviewer unavailable != lane stop`。

### Research
Primary/fallback候補は明示されたResearch Authority（例: 🌅アサヒ / ❤️レイ）から選ぶ。どちらも不在ならResearch Gate自体を削除せずBLOCKED_ESCAPE。

## Telemetry

#479 / #645へ以下をoptional projectionする。

- `blocking_gate_count`
- `review_fanout_count`
- `review_wait_age_minutes`
- `unnecessary_gate_wait_count`
- `review_reroute_count`
- `carry_forward_gate_count`
- `specialist_unavailable_count`
- `design_fallback_reroute_count`
- `design_authority_wait_count`

レビュー件数最大化/最小化をKPIにしない。必要Authorityを維持しながらunnecessary waitを減らす。

## Validation

#645の5〜10 `SM_FLOW_SAMPLE`で以下を確認する。
- `missed_stall = 0`
- 重大false positive = 0
- `blocking_gate_count`が通常PRで原則<=2
- `unnecessary_gate_wait_count`が増えない
- REVIEW_WAITによってimplementation laneが停止しない
- specialist unavailable時にsafe fallbackまたはBLOCKED_ESCAPEが実行される

条件未達なら#645をCloseせずpolicy/routingを修正する。

## Safety

- Review品質を下げるためのGate削除は禁止。
- Owner / Investment / Research truth / Design Authority / security-sensitiveの必要Gateは維持する。
- UNKNOWNはPASS/NON_BLOCKINGへ推測変換しない。
- actual AUTO_GREEN activationとは独立。
- Issue #79 untouched。

Refs: #647 #645 #646 #602 #479 #556 #593
