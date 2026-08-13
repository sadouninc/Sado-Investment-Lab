# #418 Companies Index — Mobile Density Prototype

担当: ⭐️ミナ  
種別: Design / UX Prototype + Implementation Handoff  
Status: REVIEW_READY  
Related: #418 / #320

## Goal

`/companies/` の mobile first-view を、説明文と余白で消費せず、**カテゴリと最初の企業カードまで390pxで短く到達**できる密度へ収束する。

## Root cause

現行 `book.css` はdesktop用の余白がmobileでも残る。

- `h2 { margin-top: 3.5em; }`
- `.content-grid { margin: 2rem 0 4rem; }`
- `.content-card { padding: 1.4rem; }`
- mobileでは1 column化のみで、vertical rhythmは圧縮されない

そのため `intro → category heading → grid top margin → card padding` が累積し、1カテゴリ目の最初の企業へ到達するまでに意味のない縦距離が増える。

## 390px Prototype Contract

```text
Companies
企業の長期的な強さと、現在の投資タイミングを分けて分析します。

Semiconductor
┌────────────────────────────┐
│ 4063 信越化学工業          │
│ 4063_ShinEtsu.md           │
└────────────────────────────┘
┌────────────────────────────┐
│ 3110 日東紡績              │
│ 3110_Nittobo.md             │
└────────────────────────────┘

Energy
...
```

### Density

- page H1 → intro: 8–12px
- intro → first category: 20–28px
- category heading → first card: 10–16px
- card gap: 8–12px
- card padding: 12–16px
- category末尾 → next category: 24–32px

### Typography

- H1: 30–34px, 1.2–1.25 line-height
- category: 22–26px, 1.3
- card title: 16–18px, 1.4
- filename/meta: 12–14px, 1.5
- 13px未満へ圧縮して情報を押し込まない

### Wrapping

- Japanese / English mixed titleは**単語・意味単位でwrap**する
- `overflow-wrap: anywhere` をcard titleへ常用しない
- 1〜2文字単位で縦書き状になるwrapは禁止
- card自身は `min-width: 0; max-width: 100%`

## Shared implementation target

第二CSS体系は作らない。既存 `book.css` のmobile shared primitivesへ寄せる。

推奨差分:

```css
@media (max-width: 640px) {
  .book-shell > h1:first-of-type {
    margin-bottom: .35rem;
    font-size: clamp(1.9rem, 8vw, 2.15rem);
    line-height: 1.22;
  }

  .book-shell > h2 {
    margin-top: 1.5rem;
    margin-bottom: .55rem;
  }

  .content-grid {
    gap: .65rem;
    margin: .65rem 0 1.75rem;
  }

  .content-card {
    min-width: 0;
    max-width: 100%;
    gap: .35rem;
    padding: .85rem 1rem;
  }

  .content-card strong {
    overflow-wrap: break-word;
    word-break: normal;
    line-height: 1.4;
  }

  .content-card span {
    overflow-wrap: anywhere;
    line-height: 1.5;
  }
}
```

このshared primitiveはCompaniesだけでなく、次sliceのTrade Journal一覧にも再利用可能。ただしHome hero / Cockpit専用componentへ影響させない。

## Design Gate

### BLOCKER

- 390px / 320pxでpage-level horizontal overflow
- card titleが1〜2文字単位の縦書き状wrap
- intro→category→first cardで意味のないblank scroll
- page-specificな第二CSS体系の新設
- theme toggle / title collision

### SHOULD_FIX

- category headingがH1並みに強く見える
- filename/metaが企業名より視覚的に強い
- category間隔とcard gapの差が小さく、グルーピングが弱い

### NICE_TO_HAVE

- category count (`Semiconductor · 4`) のcompact meta
- alphabetical / ticker quick filterは企業数増加後に検討

Result: **PASS_WITH_NOTES / IMPLEMENTATION_HANDOFF_READY**

Published acceptanceは390px / 320pxで行う。Issue #79 untouched.  
Broadcast checked through: comment_id=5280941868 — VERIFIED
