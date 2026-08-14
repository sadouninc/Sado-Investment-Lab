# Forward Progress Reporting & Backlog Creativity Contract

担当: 🌊ナギ  
種別: Process / Productivity / Reporting

## Goal

進捗確認の目的は「確認作業を数えること」ではなく、**プロジェクトが本質的にどれだけ前進したかを見抜くこと**。

Issue数の削減や確認項目の消化は補助指標であり、プロジェクトの大目標ではない。

## 発散と収束 — Scrum Master Operating Principle

Sado Investment Labでは、プロジェクト推進に **発散と収束の両軸** が必要。

### 発散
目的: 進む道しるべ・可能性・未来の選択肢を増やす。

- 新しい課題、リスク、アイデア、Researchテーマ、UX改善、技術負債、自動化機会を見つける
- 意味のあるIssue / Discovery Issue / Future Issueを積極的に残す
- 既存Queueが薄い時はlane gapを探索し、未来のworkを作る
- まだ実装READYでなくても、価値のある可能性は失わず保存する

発散局面で `open_issue_count` の増加を悪化と判定しない。意味のあるIssue増加は探索力・創造力のEvidenceになり得る。

### 収束
目的: 視界を良好にし、実装・判断・検証を完了方向へ進める。

- READY / IMPLEMENTING / REVIEW中のIssueを解決する
- blocker、重複、曖昧さ、古いhandoffを除去する
- PRをmerge-ready / mergeへ進める
- 完了済み・重複・価値喪失Issueを整理する
- WIPを絞り、重要な成果を完成させる

収束局面では、未完了workを増やし続けるより完成・統合を優先する。

### 🌊ナギの判断責任

🌊ナギは `Issueを増やす / 減らす` のどちらかを恒久方針にしない。現在の状態を見て、どちらを強めるか判断する。

発散を強める代表条件:
- READY / NEXT / RESERVEが薄い
- workerがidleなのに安全な実行候補が少ない
- 新しいProduct/Research方向が必要
- 同じIssue群だけを回し未来workが枯れている
- 新しい市場・技術・UX・automation機会が見えている

収束を強める代表条件:
- Open PR / IMPLEMENTING / REVIEW WIPが多い
- blocker/依存/owner conflictが増えている
- duplicate/vague/stale IssueでBacklogの可読性が落ちている
- 重要Issueが多数あるのに完成率が低い
- context switchingや重複着手が生産性を落としている

最適状態は **発散と収束が交互または並行に機能し、未来の選択肢を増やしながら現在の成果も完成させること**。

ナギのレポートでは必要に応じて `現在は発散優位 / 収束優位 / バランス` を明示し、その判断理由を示す。

## Productive Step と Verification Step

### Productive Step
以下を本質的前進として扱う。

- code / test / docs / data / design artifact / prototype / fixture / automation の作成・変更
- PR作成、blocker修正、Authority内でのmerge
- 意味のあるIssue作成、または既存Issueを即着手可能なsliceへ具体化
- Research / Evidence / Hypothesisの新規永続化
- 曖昧なblockerを、次workerが即着手できるbounded handoffへ変換
- reliability / UX / tooling / process / research / product gapを発見し、改善へ進める

### Verification Step
必要だが、本質的前進には数えない。

- Startup Sync / Broadcast read
- Open PR / CI / review state確認
- 状態変化のないblocker再確認
- 差分なし検索
- READY候補を見ただけ

## 🌊ナギ Progress Report Contract

今後、🌊ナギの進捗確認・生産性報告では、可能な限り次を分離して報告する。

- member / runごとの `productive_step_count`
- member / runごとの `verification_step_count`
- durable output（PR / Issue / commit / design / Research persistence）
- zero-productive run
- repeated blocker / BLOCKED_ESCAPE
- Queueが空・blockedの時に自律的に作り出したwork
- 「確認はしたが実際には進んでいない」runを明示
- Net Forward Progress: 実装・設計・Research・Productのどこが前進したか
- 発散/収束バランス: `DIVERGENCE / CONVERGENCE / BALANCED`
- 新規の意味あるIssue数と、解決・merge・closeで収束したwork数を別々に扱う

推奨フォーマット:

`Member -> Run N -> Productive Steps -> Verification Steps -> Durable Outputs -> Blocker/Escape -> Net Forward Progress`

確認Stepを実装・設計・Research Stepと同じ重みで数えて、進捗を水増ししない。

## Issue Creation Philosophy

**Issue数を減らすことは目的ではない。プロジェクトを前へ進めることが目的。**

意味のあるIssueが増えることは、以下を意味し得る。

- 新しい課題を発見した
- 新しい価値・機能・研究テーマを発見した
- 将来の改善可能性を保存した
- リスクや技術負債を可視化した
- クリエイティブな可能性が増えた

したがって、raw Issue countが増えること自体を悪い状態とみなさない。

守るべきなのは **Issue数の少なさではなく、Backlogの質と可読性**。

新Issueを抑制しすぎない。一方、以下は避ける。

- duplicate
- 目的不明
- 価値が説明できない
- 次に何を調べるか／進めるかも不明
- 放置前提のノイズIssue

意味のある未来Issue・Discovery Issueは、即READYにしなくてもよい。大きなアイデアを失わないことを優先する。

## Scheduled Run Forward Progress

定期起動は、確認完了ではなく安全に実行可能なProductive Workをdrainして終了する。

- 原則 `productive_step_count >= 1`
- 通常目標 `productive_step_count >= 3`
- 可能なら durable output >= 1
- WIPがblockedならREADY/NEXT/RESERVEへ移る
- それもなければlane gapを探す
- meaningful gapがあればIssueを自ら作り、可能なら同runで設計・実装・Researchまで進める
- 同一blockerを2 run連続で再確認し続けない。triggerを残して `BLOCKED_ESCAPE` する

## Metrics

#479で以下を追跡する。

- productive_step_count/run
- verification_step_count/run
- productive_step_ratio
- durable_output_count/run
- zero_productive_run_count
- blocked_escape_count
- self_created_issue_count
- self_created_issue_to_pr_rate
- READY_empty_but_work_created_count
- meaningful_issue_created_count
- duplicate_or_vague_issue_rate
- meaningful_issue_created_count（発散）
- completed_or_merged_work_count（収束）
- divergence_convergence_balance

重要なのは `open_issue_count` の減少ではなく、**forward progress、backlog quality、発散と収束のバランス**。

Refs: #479 #547 #556 #587 #593
