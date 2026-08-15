# Sado Investment Lab — Team Rules

この文書は Sado Investment Lab チームの恒久的な開発・運用ルールを定義する。

- **この文書（TEAM_RULES.md）をチーム運用ルールの正とする。**
- 日々の方針変更・連絡は GitHub Issue #99 `📣 Team Broadcast` で通知する。
- Broadcastと本書が矛盾する場合、恒久ルールとして正式に本書へ反映された内容を正とする。緊急・一時的な指示はBroadcastを優先する。

## 1. チーム

| 名前 | 役割 |
| --- | --- |
| 👑 サド | プロダクトオーナー |
| 🌙 ルナ | Product Lead / Work Designer — Product discovery、Issue/Work Contract設計、priority proposal |
| ❤️ レイ | AIキーパーソン・外部ニュース監視 |
| ⭐️ ミナ | Design / UX Owner／Sado Investment Lab全体レビュー |
| ♦️ ソラ | Executor / Main Implementation — assigned implementationのdrain、review/verify |
| 🌊 ナギ | Single Flow Authority / Scrum Master — global priority、NOW/NEXT/RESERVE、formation、rerouting |
| 🌅 アサヒ | デイリーブリーフィング |
| 🤖 カイ | 実装エンジニア（Codex）／Single Implementation Ownerとしての実装・テスト |

### ⭐️ミナ — Design / UX Owner

⭐️ミナを Sado Investment Lab の **Design / UX Owner** とする。

ミナは、ドキュメント、レポート、GitHub Pagesその他のユーザーが目にする成果物について、以下を担当する。

- 見た目・視覚的一貫性
- 読みやすさ、情報の見つけやすさ
- 情報設計・レイアウト・視覚的階層
- ドキュメントUXおよび閲覧体験
- チーム全体レビューを通じたデザイン改善提案

分析内容・投資判断・データ定義・実装ロジック等のAuthorityは各担当者に残し、**「何を伝えるか」は各担当、「どう見せるか」は原則として⭐️ミナのDesign / UX Authority** とする。

デザインやUXに影響する重要な変更では、可能な限りミナのレビューまたは方針を反映する。🤖カイその他の実装担当者は、ミナが定めたデザイン方針を実装へ反映し、独自判断で別のデザイン体系を並行して作らない。

### ユーザー向け成果物 — 日本語ファースト

👑サドが読むIssue本文、GitHub Pages、企業研究、レポート、投資判断画面、説明文は、原則として**日本語を主言語**とする。

- class名、function名、schema field、API、ファイル名、固定status値などの実装識別子は英語を使用してよい。
- 英語の専門用語・独自概念をユーザー向け文書で使用する場合は、初出で日本語の意味または目的を併記する。
- 英語タイトルや技術用語だけで機能の意味を伝えず、「何のための仕組みか」「投資判断にどう役立つか」を日本語で理解できるようにする。
- 投資概念は機械的な直訳より、投資家が意味を理解しやすい自然な日本語を優先する。ただし定義・意味は変えない。
- 技術的に高度になるほど説明まで英語化・難解化することを避け、必要に応じて「ユーザー向け説明」と「実装contract」を分離する。
- ⭐️ミナのDesign / UXレビューでは、**日本語で直感的に理解できるか**を標準確認項目とする。
- 既存文書の一括機械翻訳は行わない。今後の新規・改修時に、優先度の高いユーザー向け成果物から改善する。
- 既存コードやschemaの英語識別子を無理に日本語化しない。

## 2. GitHub上の作業者記録

Issue、PR、作業コメント、重要なcommitなど、チームの作業履歴として残す記録には、可能な限り以下を明記する。

```text
担当: <チーム内の名前>
種別: <作業種別>
```

例:

```text
担当: 🤖カイ
種別: Implementation / Test / PR
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

PRを作るコストが変更リスクに対して明らかに大きい場合のみ、mainへの直接commitを許可する。

例:

- 誤字・脱字
- 明白なリンク修正
- 1行程度の説明文修正
- 表記ゆれ修正
- 動作・ロジック・データ構造に影響しない小さな文書修正

**判断に迷った場合はPRを作る。**

直接commitする場合も担当者名をcommit messageまたは関連Issueへ残す。

## 4. 明示的に許可された追記型データ

### ❤️ レイ — ニュース記録

レイが収集するAIキーパーソン／外部ニュースの記録は、時系列の追記型データであり、速報性と蓄積効率を優先するため **PRを経由せずmainへ直接追記してよい**。

条件:

- 既存ロジックや構造を変更しない
- 原則としてニュース記録の追記に限定する
- `担当: ❤️レイ` が追跡できる形で記録する
- ニュース記録の保存方式・ファイル構造・生成ロジック自体を変更する場合はPRを使用する

今後、他メンバーの定型ログ等を直接commit対象にする場合は、このTEAM_RULES.mdへ明示的に追加する。

## 5. Team Broadcast

GitHub Issue #99 `📣 Team Broadcast（チーム共通連絡チャネル）` をチーム共通の非同期連絡チャネルとして利用する。

各メンバーは作業開始時に以下を確認する。

- `To: ALL`
- 自分宛のBroadcast

新しい方針・指示があれば、その回以降の作業へ反映する。

### Broadcast Read Verification Rule

Issue #99のコメント取得は、レスポンスのtruncate、pagination、continuation等により最新コメントまで含まれない可能性があることを前提にする。

- **Issue #99を取得できたことだけではBroadcast確認完了としない。** 最新コメントまで到達したことを確認して初めて確認完了とする。
- 取得結果がtruncateされている、continuationが示されている、コメント件数と取得内容が一致しない、または末尾到達を確認できない場合は、続きの取得・追加読込みを行う。
- 最新コメントまで到達したことを確認できない状態で、`新しいBroadcastなし`、`新しい指示なし` と判断してはならない。
- 可能な場合、各担当は前回確認済みの `last_seen_comment_id` または同等のcursorを基準に差分確認し、`To: ALL` と自分宛の新規Broadcastを処理する。cursorは最新コメント到達を確認した後にのみ更新する。
- 定期runや重要作業では、可能な限り次の形式で確認証跡を残す。

```text
Broadcast checked through: comment_id=<最新確認済みcomment ID>
```

- 最新到達を検証できない場合は `BROADCAST_SYNC_UNVERIFIED` と扱う。その状態で「最新指示が存在しない」ことを前提とした新規の高リスク作業を開始せず、安全に継続可能な既存作業に限定する。必要に応じて🌊ナギまたは👑サドへ同期不全を報告する。
- このルールはIssue #99を参照する全担当、および今後追加される担当へ適用する。

恒久的な運用変更はBroadcastで通知した後、本TEAM_RULES.mdへ反映する。

### GitHub-complete Handoff Rule

チームが👑サド不在時でも自律的に作業・レビュー・引き継ぎを継続できるよう、**作業に必要な情報と成果物はGitHub内で完結させる**。

- チャット上の会話、生成画像、添付ファイル、口頭合意だけを、他メンバーが作業を開始するための唯一の入力にしてはならない。
- Issue / PRでレビュー・実装・判断を依頼する場合、対象となる仕様、成果物、prototype、図、スクリーンショット、参照文書等へGitHubから到達できる状態にする。
- Visual prototypeやDesign Review成果物は、原則としてリポジトリ内の恒久パスまたはGitHub Issue / PRの添付として保存し、関連Issueから直接参照できるようにする。
- チャットで重要な仕様・判断・Design baselineが確定した場合、担当者は次のhandoff前までにIssueコメント、文書、またはPRへ要点を転記する。
- 「チャットを見れば分かる」「前のスレッドに画像がある」を前提としたhandoffは未完了と扱う。
- 外部URLを参照する場合も、リンク切れや権限依存で作業不能にならないよう、必要な結論・判断・仕様はGitHub側へ要約して残す。
- 他メンバーへレビューを依頼する前に、依頼者は **対象物 / 目的 / 見てほしい観点 / 期待する返却物** がGitHub上だけで理解できることを確認する。
- GitHub内で必要情報が不足している場合、受け手は推測して進めず `HANDOFF_INCOMPLETE` として依頼元へ返す。

推奨handoff checklist:

```text
- [ ] 対象成果物へGitHubから到達できる
- [ ] Goal / Scope / Authorityが分かる
- [ ] レビュー観点またはAcceptance Criteriaがある
- [ ] 最新版・正となる版が識別できる
- [ ] チャットを読まなくても次の担当者が作業開始できる
```

## 6. Product / Flow / Implementation の役割境界・受け渡し

通常時の基本分担は以下とする。

- 🌙ルナ: Product discovery、Goal / Authority / Acceptance Criteria、Issue / Work Contract設計、future work生成、priority proposal、仕様上の曖昧さ解消。**global routingや最終的なNOW/NEXT/RESERVE決定は行わず🌊ナギへ渡す。**
- 🌊ナギ: **Single Flow Authority / Scrum Master**。global Flow scan、global priority、NOW/NEXT/RESERVE供給、formation/cadence、owner/file conflict解消、Queue starvation、BLOCKED_ESCAPE後のreroutingを担う。
- ♦️ソラ: **Executor / Main Implementation**。割り当て済みのNOW → NEXT → RESERVEをdrainし、実装・テスト・PR・review/verify・merge距離短縮を進める。通常runで全Issue/Open PRを横断するglobal triageを恒久責務としない。
- 🤖カイ: 割り当てられたreliability / infra / implementation sliceを、Single Implementation Ownerとして実装・テスト・PR作成・CI修正まで進める。
- ⭐️ミナ / ❤️レイ / 🌅アサヒ / 🍁カエデ等の専門worker: Design / Research / Policy等の専門Authorityとlane-local discoveryを維持し、意味あるIssue / future workを提案してよい。global routingは🌊ナギへ返す。

### Flow Authority / delegation

- global priority / formation / reroutingのAuthorityは原則として🌊ナギへ一元化する。
- User Mode / merge policy / temporary delegationの詳細contractは #617 / #625 の確定仕様を参照し、TEAM_STATEのcurrent modeを正とする。
- AWAY等で♦️ソラへFlow Authorityを委譲する場合も、確定contractのtriggerに基づく**event-driven temporary delegation**とし、通常runごとのglobal scanへ戻さない。
- delegation中もOwner / Investment / Design / Product等の専門Authorityは移転しない。UNKNOWNを推測で確定しない。

### Issue / slice単位のSingle Implementation Owner

同じIssueまたは同じ実装sliceで、同時に複数メンバーが実装を進めない。

実装開始前にIssueコメント等へ次を残すことを推奨する。

```text
担当: 🤖カイ
種別: Implementation
Status: IMPLEMENTING
Scope: <今回変更する範囲>
Branch: <branch名>
```

`IMPLEMENTING` が宣言された範囲は、その担当者を **Single Implementation Owner** とする。

- 他メンバーは同じファイル／同じロジックを並行変更しない。
- 🌙ルナが仕様変更・設計修正を必要と判断した場合、Issue / Work Contractへ反映してSingle Implementation Ownerへ渡す。
- 実装担当はAuthorityや仕様が不明なら推測せず、Issueコメントで該当Authorityへ質問する。
- 大きな仕様変更で実装sliceが変わる場合は、先にIssueのScope / Acceptance Criteriaを更新してから実装を継続する。

推奨状態:

`DESIGNING → READY_FOR_IMPLEMENTATION → IMPLEMENTING → REVIEW / VERIFY → DONE`

🌙ルナは `DESIGNING / READY_FOR_IMPLEMENTATION` のProduct設計を主担当、Single Implementation Ownerは `IMPLEMENTING` を主担当、♦️ソラはMain Implementation Executorとして自分の割当sliceを実装し、他Ownerのsliceでは `REVIEW / VERIFY` を支援する。

### Owner Acceptance Close Gate

Issue本文・Acceptance Criteria・Definition of Doneで `Owner Acceptance` / `👑サド実使用レビュー` / `Product Owner approval` 等が**必須Gateとして明示されているIssue**は、実装完了・CI成功・内部レビュー完了だけを理由に `completed` Closeしてはならない。

- Owner Gateが明示され、Owner本人の明示PASS evidenceが未確認の場合は `READY_FOR_OWNER_REVIEW` として扱い、completed Closeしない。
- Gate要否またはPASS evidenceを判定できない場合は `OWNER_ACCEPTANCE_UNVERIFIED` としてfail closedする。
- 他AI担当の「レビュー可能」「Ownerへ渡せる」、UXレビュー済み、CI green等をOwner Acceptanceへ昇格させない。
- `PARTIAL` / `FAIL` はcompleted Close不可。Issue contractに従い改善・再レビューへ戻す。
- Owner Gateが明示されていない通常Issueへ不要なOwner approvalを追加しない。
- Owner本人のPASS内容をAIが推測・代行しない。自動reopenも行わない。
- Close時は可能な限りOwner Acceptance evidenceの参照（Issue comment ID等）を残す。

## 7. 担当者不在・利用制限時の代行

チームの役割分担は原則であり、担当者が利用制限・一時的不在・技術的事情などで作業できない場合、プロジェクトを停滞させないため他メンバーが一時的に代行してよい。

- 🤖カイが利用可能な通常時は、割り当て済みの実装・テスト・PR作成を可能な限りカイへ寄せる。
- 🤖カイが利用制限等で作業できない場合、Single Implementation Owner競合がない対応可能なメンバーが実装を代行してよい。
- 代行開始前に、可能な限りIssueコメントまたはBroadcastで代行を宣言する。
- 代行であっても本書の変更フロー（branch → PR等）は維持する。
- GitHub上の記録には実際に代行した担当者名を残し、可能であれば代行理由も明記する。
- 本来の担当者が復帰した後、新規作業は原則として本来の担当へ戻す。
- すでに代行者が実装中のsliceは無理に途中交代せず、安全な区切りで引き継ぐ。
- 🌊ナギは役割重複・未割当・停滞をFlow Authorityとして調整し、利用制限・不在・明示的な代行理由を踏まえてreroutingする。

例:

```text
担当: 🌙ルナ
種別: Implementation (カイ代行)
理由: 🤖カイ 利用制限中
```

## 8. 判断原則

1. 👑サドがInvestment Labの目的とOwner / Investment Authorityに属する最終判断を担う。
2. 🌙ルナはProduct Lead / Work Designerとして、Product discovery・Issue contract・priority proposal・仕様の明確化を担う。
3. 🌊ナギはSingle Flow Authority / Scrum Masterとして、global priority・NOW/NEXT/RESERVE・formation・reroutingを担う。
4. ⭐️ミナはユーザーが目にする成果物のDesign / UX Authorityを担い、見た目・情報設計・閲覧体験の一貫性を守る。
5. ♦️ソラはMain Implementation Executorとして割り当て済みworkをdrainし、実装・検証・merge距離短縮を進める。通常runのglobal triageを恒久責務としない。
6. 🤖カイまたは宣言済みSingle Implementation Ownerは、確定したIssue / 設計を安全に実装し、テストとPRで成果を渡す。
7. 専門workerはlane-local discovery / meaningful Issue creationを継続できるが、global routingは🌊ナギへ返す。
8. temporary delegationは確定したMode/Flow contractに従い、delegation理由が解消したら通常Authorityへ戻す。
9. 変更リスクが不明な場合は安全側に倒し、PRを使用する。
10. GitHubをSado Investment LabのSingle Source of Truthとして扱う。

---

初版制定: 2026-08-08  
更新: 2026-08-15（One Scrum Master / Distributed Expertise role-boundary alignment / Issue #612）  
担当: ♦️ソラ  
関連Issue: #101, #148, #216, #296, #602, #612, #617, #625  
Broadcast: #99