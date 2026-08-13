# #418 Final Cross-page Mobile Density — Visual Prototype Contract

担当: ⭐️ミナ  
種別: Product UI Design / Mobile UX / Visual Prototype  
Status: IMPLEMENTATION_HANDOFF_READY  
Related: #418 / #320 / #313 / #312

## Goal

既に個別sliceで改善済みのTrade Analysis / Market Phase / Sector Rotation / Morning Reportを再実装せず、残るcross-page問題をshared Design Systemへ収束する。

対象fixture:
1. Cockpit見方ガイド
2. Companies一覧
3. Trade Journal一覧
4. Home regression

## 390px first-view contract

### A. Cockpit見方ガイド
- H1は利用者向け日本語を主役にし、内部contract refsはfirst-viewから退避。
- theme toggle / floating controlがH1・leadへ重ならない。
- first viewport内に「最初の30秒で見る3点」の冒頭が見える。

### B. Companies一覧
- intro → first category → first company cardまでを短い縦距離で接続。
- category hierarchyは巨大marginではなくtype scale / divider / weightで表現。
- 長い英語タイトルはmobileでcard heightを過度に増やさない。

### C. Trade Journal一覧
- `年 → 月 → 日付card` を連続した一覧階層として読める。
- 年・月・card間のmargin累積を禁止。
- 内容量の少ない日付cardはcompact padding、tap targetは維持。

### D. Home regression
- Today / 주요 status / primary actionの視線順を保持。
- detailsやsection間で意味のない大余白を作らない。
- #312 / #320で確定したHome責務を変えない。

## Shared responsive contract

- mobile H1: starting range 30–34px / line-height 1.2–1.3。固定値ではなくshared tokenで調整。
- important mobile textを13px未満へ追い込まない。
- `hero → first section`, `section → subsection`, `heading → content`, `card → card` を別spacing roleとして扱う。
- nested container / divider / heading marginの二重加算を禁止。
- controls: `min-width: 0`, `max-width: 100%`, tap target >= 2.75rem相当。
- 320px / 390pxでpage-level horizontal overflowを発生させない。
- internal Issue refs / filenames / implementation diagnosticsはdetails/footer層へ。
- second CSS systemは禁止。canonical `/assets/design-system.css` と `codex-*` primitivesへ収束。

## 30-second hierarchy

`この画面は何か → 今日/現在の主要情報 → 次に見る内容 → 詳細/内部情報`

Mobileで「説明と余白だけをスクロールしてから本題に到達する」構造をNGとする。

## Design Gate

### BLOCKER
- title / theme toggle / controlsが重なる
- 320pxまたは390pxでpage-level horizontal overflow
- first viewportが内部Issue/contract情報だけで占有される
- section/nested marginの二重適用で本題がfirst viewportから押し出される
- page-specific second CSS/themeを追加する

### SHOULD_FIX
- H1が3行超を常態化
- heading→first contentの余白が階層表現を超えて大きい
- year/month/category hierarchyを空白量だけで表現
- compact list/cardでもdesktop paddingをそのまま維持

### NICE_TO_HAVE
- shared `compact-list` / `compact-group` primitive
- mixed Japanese/English titleのresponsive tuning fixture
- 390px + 320px deterministic visual regression

Result: **PASS_WITH_NOTES — implementation may proceed as a shared responsive-system convergence slice.**

## Acceptance

- Cockpit guide: first viewport内に主要3点の導入が見える
- Companies: first category/cardへ短いスクロールで到達
- Trade Journal: 年→月→日付を連続階層として比較可能
- Home: section間の意味のない大余白なし
- 320/390px overflowなし
- desktop hierarchy/regressionを壊さない

Issue #79 untouched.
Broadcast checked through: comment_id=5276694845 — VERIFIED
TEAM_STATE User Mode: ACTIVE
