# #317 Investment Decision Cockpit — Visual Prototype

担当: ⭐️ミナ  
種別: Design Artifact / Owner Review  
Status: OWNER_REVIEW_CANDIDATE  
Version: v1  
Authority: Visual Design = ⭐️ミナ / Product・IA = 🌙ルナ / Product Owner最終判断 = 👑サド

## Prototype

- [`cockpit-concept-v1.svg`](./cockpit-concept-v1.svg)
- Review target: **v1**

## Purpose

#317「Investment Decision Cockpit Concept」のVisual directionを、チャット依存なしでGitHub上から確認・レビューできる恒久成果物として残す。

CockpitはResearch全文を読む画面ではなく、Ownerが投資判断を行うために必要な計器を集約する「意思決定室」。最初の30秒で以下を読める構造を狙う。

1. 対象と鮮度
2. 前回との差
3. 市場期待との差
4. Warning / Thesis Health
5. Scenario比較
6. Decide → Act → Record

## Visual Contract

`Sado Investment Codex` の共通方向性に従う。

- 知的で静か
- セピア / 生成りを基調
- 深緑を主要accent
- 真鍮色を境界・instrument感の補助に使用
- 世界観は古典、UXは現代
- 装飾より情報階層を優先
- 重要な変化だけが鋭く目立つ
- statusは色だけに依存しない

## Prototype mapping

- Header / context rail: 対象・鮮度・Thesis status
- Primary instrument 01: 前回との差
- Primary instrument 02: 市場期待との差
- Primary instrument 03: Warning / Thesis Health
- Scenario Instruments: Bear / Base / Bull
- Decide: 見解を決める
- Act & Record: Portfolio影響を見て実行 / 見送り、Decision Snapshotへ記録

## Non-goals

このprototypeは以下を確定しない。

- 実データschema
- BUY / SELL推奨ロジック
- Ownerのrisk threshold
- Canonical artifactのmutation
- 航空比喩を全UI操作名へ展開すること
- #313共通Concept architectureの再定義

## 🌙ルナ Product / IA Reviewで見てほしい点

1. **30秒優先順位** — 最初に見る順序が「前回との差 → 市場期待との差 → Warning / Thesis Health」で妥当か
2. **責務境界** — CockpitがResearch / Portfolio / Decision Journalを侵食していないか
3. **Decide → Act → Record** — 見解・行動・記録の境界がProduct modelとして自然か
4. **航空比喩の範囲** — Concept理解を助けるが、操作性を損なうほど強くなっていないか
5. **次実装slice** — #313 fixtureとして実装する際に不足しているProduct contractがないか

## ⭐️ミナ Design Gate

### BLOCKER
- 最初の30秒で主要3点に到達できない
- UNKNOWN / STALE / UNAVAILABLE等を色だけで表現する
- Research全文をCockpitへ持ち込む
- Home / Codex Map / Cockpitの責務を混在させる
- #320 Visual Design Systemと別系統のcomponent / token体系を作る

### SHOULD_FIX
- mobileで主要3点がfirst screenから遠い
- Brass accentが装飾過多になり重要度を誤認させる
- Decide / Act / Recordが一つのCTAに潰れて意味境界が不明
- 根拠drill-downからCockpitへ戻りづらい

### NICE_TO_HAVE
- Instrument iconographyの追加
- Scenario間の差分をより直感的に見せるmicro-visual
- Decision Snapshotへの履歴感を示す軽いmotif

## Owner Review note

v1は**方向性確認用prototype**。👑サドAuthorityが必要な選択（航空計器感をどこまで強くするか、装飾密度、最終Typography比率）は未確定。比較案が必要な場合はv2として追加し、v1を上書きしない。

## Related

- #317 Investment Decision Cockpit Concept
- #313 Concept / How-to Architecture
- #320 Visual Design System v1
- #312 Home / OS Map
- #314 Global Navigation
- #329 prototype persistence

Broadcast checked through: comment_id=5246936719 — VERIFIED
