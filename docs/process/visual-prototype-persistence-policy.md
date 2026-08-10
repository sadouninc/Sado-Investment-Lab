# Visual Prototype Persistence Policy

Status: Proposed
担当: 🌊ナギ
種別: Process / Design Handoff

## Purpose

承認済みVisual Prototypeがチャット内だけに残り、Product/IA Review・Implementation・Design QAで参照不能になることを防ぐ。

## Rule

⭐️ミナが作成し、👑サドが承認した、または実装contract / Product Reviewの基準として使用するVisual Prototypeは、チャットだけを正としない。

1. GitHub上の恒久成果物として保存する。
2. 対応Issueから、その成果物を直接参照できるようにする。
3. 🌙ルナへのProduct / IA Review依頼、♦️ソラ・🤖カイへのImplementation handoffでは、その恒久参照先を明記する。
4. 実装後のDesign Gateでも同じ成果物を比較基準として使用する。
5. チャット内画像のみで `READY_FOR_IMPLEMENTATION` / Design handoffを完了扱いにしない。

## Preferred persistence

- 可能ならrepository管理下のdesign/prototype assetとして保存し、履歴・clone・PR reviewで追跡可能にする。
- Issue添付を使う場合も、対応Issue本文またはコメントに恒久参照を残し、成果物の版・対象画面・Authority状態が追えるようにする。
- prototype更新時は、旧版を無言で置換せずversion / superseded関係を追跡可能にする。

## Handoff checklist

Visual Design → Product / IA Review または Implementationへ渡す前に:

- [ ] prototypeのGitHub恒久参照先がある
- [ ] 対象Issueから参照できる
- [ ] version / statusが分かる
- [ ] 👑サド承認済みか、未承認ならその旨が分かる
- [ ] 🌙ルナ / 実装担当がチャット履歴なしで成果物を確認できる

## Immediate application

Issue #317については、合意済みCockpit prototypeをGitHub上の恒久成果物として保存し、#317から参照可能にした上で、🌙ルナへProduct / IA Reviewを再依頼する。

この文書はTEAM_RULES.mdへの恒久反映候補。TEAM_RULES.mdは重要運用文書のため、正式反映はbranch → PRで行う。
