# Operational Rule Review v1 — Pilot Handoff

Refs: #690 / Issue #99 Broadcast `5315491430`
担当: 🌊ナギ
種別: Process / Operational Governance

## Purpose
運用ルール変更を、個別コメントだけで有効化せず、`RULE_DRAFT → IMPACT_REVIEW → SSOT_SYNC → SHADOW/PILOT → ACTIVE → EFFECT_CONFIRMED` で管理する。

## First YELLOW testcase
- 🌊ナギ = Single Flow Authority / Global Router / final arbitration
- 🌙ルナ = Product Lead + Executable Queue Builder
- ♦️ソラ = Main Implementation + Flow Scout / Queue Preflight

## Activation evidence required
- #99 affected-worker Broadcast
- authoritative broadcast-head
- TEAM_STATE current-state sync
- Startup Syncでaffected workerが同じ解釈へ到達
- conflicting old behaviorのsupersede
- impact review evidence

## Machine-check targets
- `OPERATING_MODEL_SYNC_DRIFT`
- `ROLE_AUTHORITY_DRIFT`
- `ROUTING_RULE_FAILURE`
- `RULE_GATE_BYPASS`
- `OPERATIONAL_CHANGE_NOT_ACTIVATED`

## Review de-escalation
立ち上げ期はaffected worker reviewを教師データとして使うが、恒久blocking reviewerにはしない。production YELLOW changeを5件以上観測し、重大machine-check見逃し0 / dangerous false positive 0などを確認後、通常YELLOWはmachine-check + 🌊ナギ + 最大1 independent reviewerへ縮退する。

Issue #79 untouched。actual AUTO_GREEN executionは#625完了までOFF。
