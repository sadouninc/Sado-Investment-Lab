# #414 Primary Evidence Source Library — Visual Prototype Contract

担当: ⭐️ミナ  
種別: Product UI Design / Evidence Retrieval  
Status: IMPLEMENTATION_HANDOFF_READY  
Related: #414 / #144 / #113 / #320

## Goal
Company Researchの重要Factから一次資料へ戻れ、原資料からResearchへ戻れるread-only Source Libraryを、Evidence Archiveの状態を誤認せず使える形で設計する。

## Responsibility boundary
- Company Research = 企業理解 / 仮説 / Scenario
- Source Library = 一次資料の所在・状態・provenanceを確認
- Source LibraryはResearch本文や判断を複製しない
- Archive stateを投資判断statusへ変換しない

## Owner first-view
1. 対象企業 / fiscal period
2. Primary coverage summary
3. Source cards
4. Missing / recovery state
5. Researchへ戻る

## Source card hierarchy
各資料はcompact cardで表示:
- document type + fiscal period
- published_at
- access state
- primary / verification state
- 原資料を開く CTA（利用可能時のみ）
- Researchへ戻る CTA
- original URL / hash / source_id等はdetailsへ

## Access state semantics
- ARCHIVED: Labから再取得可能
- URL_ONLY: 公式URLのみ。保存済みと見せない
- NEEDS_RECOVERY: 過去利用の形跡はあるがArchive未回収
- UNAVAILABLE: 現在アクセス不能

状態は色だけでなくlabelを必須にする。URL_ONLY / NEEDS_RECOVERY / UNAVAILABLEを成功状態と同じvisual weightにしない。

## Mobile 390px
- 1 source = 1 vertical card
- first viewportで対象企業 / fiscal period / coverage / 最初のsourceが見える
- filenameやsource_idを主見出しにしない
- filterはType / Periodの2軸をcompact controlへ
- page-level horizontal scroll禁止

## Design Gate
### BLOCKER
- URL_ONLYをARCHIVED相当に表示
- missing/unavailableを正常・確認済みに見せる
- ResearchとSource Libraryで第二Research truthを作る
- mobileで巨大tableのみ
- source_id / hash / filenameがfirst-viewを支配
- 個別Company専用CSSを作る

### SHOULD_FIX
- fiscal period / document typeより内部pathが先に見える
- Researchへのreturn pathがない
- access stateが色のみ
- recovery対象が通常資料に埋もれる

### NICE_TO_HAVE
- coverage summary（例: 3 archived / 1 recovery）
- source type / fiscal period filter
- page/section deep-link（取得可能時）

Result: **PASS_WITH_NOTES — Pages implementationはRegistry/read contract成立後に進行可。**

Issue #79 untouched.
Broadcast checked through: comment_id=5276694845 — VERIFIED
TEAM_STATE User Mode: ACTIVE
