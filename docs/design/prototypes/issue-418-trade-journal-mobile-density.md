# #418 Trade Journal Index — Mobile Density Prototype

担当: ⭐️ミナ  
種別: Design / UX Prototype + Implementation Handoff  
Status: REVIEW_READY  
Related: #418 / #320 / #533

## Goal

`/trade-journal/` を `intro → year → month → first entry` の余白累積から、日付を主役にしたcompact chronological listへ収束する。

## Root cause

生成構造は `H1 + intro → h2 year → h3 month → .content-grid → .content-card`。現行mobileではdesktop用の大きな `h2/h3/grid` marginが残り、最初の日誌までの縦距離が長い。

## 390px contract

```text
Trade Journal
市場認識、判断、売買、反省、改善を時系列で振り返ります。

2026
August
┌────────────────────────────┐
│ 2026-08-05                 │
│ 2026-08-05.md              │
└────────────────────────────┘
┌────────────────────────────┐
│ 2026-08-04                 │
│ 2026-08-04.md              │
└────────────────────────────┘
```

## Hierarchy

1. 日付 = primary (16–18px)
2. year = section context。H1より弱くする
3. month = local grouping。yearより弱くcardへ近づける
4. source filename = secondary metadata (12–14px / muted)

390pxで `Trade Journal → 2026 → August → first entry` が連続して見えること。

## Shared implementation target

Companies #533で固定したshared mobile primitivesを再利用し、第二CSS体系を作らない。

```css
@media (max-width: 640px) {
  .book-shell > h2 { margin: 1.5rem 0 .45rem; font-size: clamp(1.4rem, 6vw, 1.6rem); line-height: 1.3; }
  .book-shell > h3 { margin: .9rem 0 .45rem; font-size: 1.05rem; line-height: 1.35; }
  .content-grid { gap: .65rem; margin: .55rem 0 1.6rem; }
}
```

`.content-card`のpadding / wrap / min-widthはCompanies contractと共通化する。

## Responsibility

Home = 今日の市場と自分への影響。Cockpit = 現在の判断。Trade Journal = 実行後の記録・振り返り。一覧はchronological navigationに集中し、Home/Cockpitのsummaryを複製しない。

## Design Gate

### BLOCKER
- 390px / 320px page-level overflow
- intro→year→month→first entryのblank scroll
- year/monthがH1級に強い
- source filenameが日付より強い
- page-specific第二CSS体系
- theme toggle / title collision

### SHOULD_FIX
- month→cardとcard→cardのgrouping差が弱い
- 長いsource filenameで幅が崩れる
- 余白だけでyear/month hierarchyを表現する

### NICE_TO_HAVE
- `August · 3` のcompact count
- 履歴量増加後の年/月local index

Result: **PASS_WITH_NOTES / IMPLEMENTATION_HANDOFF_READY**

Published acceptance: 390px / 320px。Issue #79 untouched.  
Broadcast checked through: comment_id=5281762495 — VERIFIED
