---
layout: site
title: Investment Decision Cockpit — 見方ガイド
permalink: /concepts/investment-decision-cockpit/
---

# Investment Decision Cockpit — 見方ガイド

## この機能は何のため？
前回の判断から何が変わったかを確認し、現在の投資仮説と評価を一つの流れで点検するための画面です。

## 最初に見る3点
1. 前回判断からの変化
2. 市場期待との差
3. 仮説・Valuation・売買前ポートフォリオ影響の状態

## なぜ見る？
変化、期待差、仮説と評価を分断せずに見ることで、判断の前提がどこで変わったかを追跡できます。

### 判断の流れ
`前回判断 → 現在との差 → 市場期待との差 → 仮説確認 → Valuation → 売買前PF影響 → 判断Snapshot → 次checkpoint`

## 状態の意味
- **UNKNOWN** — 必要な情報を確認できず、状態を確定できません。正常や中立とは扱いません。
- **UNAVAILABLE** — 参照先または必要な情報を現在利用できません。推測値で補完しません。
- **STALE** — 情報の鮮度が基準を満たしていません。最新情報として扱わず、更新元を確認します。

## 次に進む
- [売買前の影響を確認する]({{ '/risk-preflight/' | relative_url }})
- [判断を記録する]({{ '/trade-journal/' | relative_url }})

## 根拠を見る
- [企業研究]({{ '/companies/' | relative_url }})
- [投資Framework]({{ '/framework/' | relative_url }})

<details class="sil-disclosure">
<summary>この機能がしないこと</summary>
<div class="sil-disclosure__body">

- BUY / SELL / ADD / REDUCEを自動決定しない
- Ownerのconfidence・threshold・投資思想を推測補完しない
- Canonical Research / Scenario / Hypothesis / Decisionを変更しない

</div>
</details>

> 最終確認: 2026-08-11 / Contract: #313 / #317 / #312 / #320
