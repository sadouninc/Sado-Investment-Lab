# Sado Investment Lab — Team Rules

この文書は Sado Investment Lab チームの恒久的な開発・運用ルールを定義する。

- **この文書（TEAM_RULES.md）をチーム運用ルールの正とする。**
- 日々の方針変更・連絡は GitHub Issue #99 `📣 Team Broadcast` で通知する。
- Broadcastと本書が矛盾する場合、恒久ルールとして正式に本書へ反映された内容を正とする。緊急・一時的な指示はBroadcastを優先する。

## 1. チーム

| 名前 | 役割 |
| --- | --- |
| 👑 サド | プロダクトオーナー |
| 🌙 ルナ | リーダー／プロジェクト全体の方向性・設計判断 |
| ❤️ レイ | AIキーパーソン・外部ニュース監視 |
| ⭐️ ミナ | Design Authority / Product UI Designer |
| ♦️ ソラ | GitHub Issue確認・実装推進 |
| 🌊 ナギ | スクラムマスター／全体最適 |
| 🌅 アサヒ | デイリーブリーフィング |
| 🤖 カイ | 実装エンジニア（Codex） |

### ⭐️ミナ — Design Authority / Product UI Designer

⭐️ミナはレビュー専任ではなく、Sado Investment Lab の **Design Authority / Product UI Designer** とする。主担当は、Product/UI/UXの実デザイン制作、Visual Design System・画面構造・component contractの設計、実装担当へのREADY handoff、実装後のDesign Gate / reviewである。**制作が主、reviewは品質保証**として扱う。

ミナは、ドキュメント、レポート、GitHub Pagesその他のユーザーが目にする成果物について、見た目・視覚的一貫性、読みやすさ、情報の見つけやすさ、情報設計・レイアウト・視覚的階層、ドキュメントUXおよび閲覧体験を担当する。

分析内容・投資判断・データ定義・実装ロジック等のAuthorityは各担当者に残し、**「何を伝えるか」は各担当、「どう見せるか」は原則として⭐️ミナのDesign / UX Authority** とする。

デザインやUXに影響する重要な変更では、可能な限りミナの方針・成果物を実装へ反映する。実装担当者は、ミナが定めたデザイン方針を実装へ反映し、独自判断で別のデザイン体系を並行して作らない。

### Visual Prototype Persistence Rule

⭐️ミナが作成し、👑サドが承認した、またはProduct/IA Review・Implementation・Design QAの基準として使用するVisual Prototypeは、**チャットだけを正としない**。

- GitHub上の恒久成果物として保存する。
- 対応Issueからその成果物へ直接到達できるようにする。
- 🌙ルナへのProduct / IA Review、♦️ソラ・🤖カイへのImplementation handoffでは恒久参照先を明記する。
- 実装後のDesign Gateでも同じ成果物を比較基準として使用する。
- チャット内画像のみで `READY_FOR_IMPLEMENTATION` / Design handoffを完了扱いにしない。
- prototype更新時は最新版・version・superseded関係を追跡可能にする。
- 次の担当者がチャット履歴なしで対象物、目的、Authority状態、最新版を確認できることをhandoff完了条件とする。

## 2. GitHub上の作業者記録

Issue、PR、作業コメント、重要なcommitなど、チームの作業履歴として残す記録には、可能な限り以下を明記する。

```text
担当: <チーム内の名前>
種別: <作業種別>
```

GitHubアカウント上のauthorが同一であっても、チーム内で誰が判断・作業したか追跡できることを目的とする。

## 3. 変更フローの原則

コード、ロジック、構造、重要文書の変更は原則として以下のフローを使用する。

`Issue → branch → commit → PR → review / CI → merge`

### PR必須

以下は原則としてmainへ直接commitしない。

- 機能追加
- ロジック変更
- アーキテクチャ／構造変更
- 複数ファイルにまたがる実装修正
- 投資ルール、Framework、投資思想など意思決定に影響する重要文書の変更
- データ生成方式や分析方式の変更
- CI / GitHub Actions / Pages build等の設定変更
- 影響範囲が明確でない変更

### main直接commit可能な超軽微修正

PRを作るコストが変更リスクに対して明らかに大きい場合のみ、mainへの直接commitを許可する。誤字・脱字、明白なリンク修正、1行程度の説明文修正、表記ゆれ修正、動作・ロジック・データ構造に影響しない小さな文書修正など。**判断に迷った場合はPRを作る。**

## 4. 明示的に許可された追記型データ

❤️レイが収集するAIキーパーソン／外部ニュースの記録は、既存ロジックや構造を変更しない追記に限り、速報性と蓄積効率を優先してPRを経由せずmainへ直接追記してよい。保存方式・ファイル構造・生成ロジック自体を変更する場合はPRを使用する。

## 5. Team Broadcast

GitHub Issue #99 `📣 Team Broadcast（チーム共通連絡チャネル）` をチーム共通の非同期連絡チャネルとして利用する。各メンバーは作業開始時に `To: ALL` と自分宛のBroadcastを確認し、新しい方針・指示をその回以降へ反映する。

### Broadcast Read Verification Rule

- Issue #99を取得できたことだけではBroadcast確認完了としない。最新コメントまで到達したことを確認して初めて確認完了とする。
- truncate、pagination、continuation、コメント件数不一致、末尾未確認の場合は続きの取得を行う。
- 最新到達未確認で `新しいBroadcastなし` と判断しない。
- cursorは最新コメント到達確認後にのみ更新する。
- 可能な限り `Broadcast checked through: comment_id=<最新確認済みcomment ID>` を残す。
- 最新到達を検証できない場合は `BROADCAST_SYNC_UNVERIFIED` とし、新規の高リスク作業を開始しない。

### GitHub-complete Handoff Rule

チームが👑サド不在時でも自律的に作業・レビュー・引き継ぎを継続できるよう、**作業に必要な情報と成果物はGitHub内で完結させる**。

- チャット上の会話、生成画像、添付ファイル、口頭合意だけを他メンバーが作業開始するための唯一の入力にしない。
- Issue / PRでレビュー・実装・判断を依頼する場合、対象仕様、成果物、prototype、図、スクリーンショット、参照文書等へGitHubから到達できる状態にする。
- チャットで重要な仕様・判断・Design baselineが確定した場合、次のhandoff前までにIssueコメント、文書、またはPRへ要点を転記する。
- 「チャットを見れば分かる」を前提としたhandoffは未完了と扱う。
- GitHub内で必要情報が不足している場合、受け手は推測して進めず `HANDOFF_INCOMPLETE` として依頼元へ返す。

## 6. 役割境界・Single Implementation Owner

通常時の基本分担:

- 🌙ルナ: Goal、Authority、Acceptance Criteria、設計判断、優先順位、仕様上の曖昧さ解消
- 🤖カイ: 実装、テスト、branch作成、PR作成、CI確認、実装上の修正
- ♦️ソラ: Main Implementation OwnerとしてREADY Issueの実装推進、Issueトリアージ、停滞検知
- 🌊ナギ: 役割衝突、未割当、停滞、プロセス違反の監視と担当調整

同じIssueまたは同じ実装sliceで、同時に複数メンバーが実装を進めない。`IMPLEMENTING` が宣言された範囲は、その担当者をSingle Implementation Ownerとする。他メンバーは同じファイル／同じロジックを並行変更しない。

推奨状態:

`DESIGNING → READY_FOR_IMPLEMENTATION → IMPLEMENTING → REVIEW / VERIFY → DONE`

## 7. 担当者不在・利用制限時の代行

担当者が利用制限・一時的不在・技術的事情などで作業できない場合、他メンバーが一時的に代行してよい。代行開始前に可能な限りIssueコメントまたはBroadcastで代行を宣言し、branch → PR等の変更フローを維持する。本来担当の復帰後、新規作業は原則として本来担当へ戻す。すでに代行者が実装中のsliceは安全な区切りで引き継ぐ。

## 8. 判断原則

1. 👑サドがInvestment Labの目的・優先順位を決定する。
2. 🌙ルナはサドと議論し、投資思想・研究・判断・設計の方向性をまとめる。
3. ⭐️ミナはDesign Authority / Product UI Designerとして、実デザイン制作からhandoff、Design Gateまで担う。
4. 実装担当は確定したIssue / 設計を安全に実装し、テストとPRで成果を渡す。
5. 🌊ナギは役割の不足・重複・停滞とプロセス上の問題を監視し、改善を提案する。
6. 変更リスクが不明な場合は安全側に倒し、PRを使用する。
7. GitHubをSado Investment LabのSingle Source of Truthとして扱う。

---

初版制定: 2026-08-08
更新提案: 2026-08-11（⭐️ミナ役割明確化 / Visual Prototype Persistence Rule）
担当: 🌊ナギ
Broadcast: #99
