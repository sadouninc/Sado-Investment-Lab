# #542 Trade Analysis — Mobile Table / Filter Density Contract

担当: ⭐️ミナ  
種別: Design / UX Contract  
Parent: #418  
Refs: #320

## 30-second hierarchy

1. Page purpose: 取引分析
2. Primary metrics: 区分 / 件数 / 実現損益 / 勝率 / PF
3. Filters: bounded controls, 320pxでは1列
4. Trade detail: compact card (`コード＋銘柄` → `日付・区分・方向` → `損益` → details)

## Responsive contract

- 390px: primary 5 metrics remain directly comparable without page-level horizontal overflow.
- 320px: do not solve by shrinking below 13px. Secondary metrics move to progressive disclosure if necessary.
- Filters own their width (`min-width: 0`, bounded width); controls never overlap borders/tap areas.
- Trade detail becomes card-first on mobile. Desktop may retain row/table presentation using shared responsive primitives.
- Security names must not wrap one or two characters per line. Prefer one-line ellipsis plus explicit detail expansion.
- Card height remains compact enough to show more than one trade within a typical mobile viewport after the section heading.

## Shared primitive intent

Do not add a Trade Analysis-only second CSS system. Implementation should extend/reuse #320 shared primitives for:

- responsive metric table / summary grid
- bounded form controls
- row → card responsive presentation
- compact metadata and semantic P/L emphasis

## Design Gate

### BLOCKER
- page-level horizontal overflow
- security-name vertical-style wrapping
- overlapping filter borders or tap areas
- primary 5 metrics effectively incomparable at 390px
- page-specific second CSS system

### SHOULD_FIX
- filter horizontal scrolling
- secondary columns visually stronger than primary metrics
- one trade card consuming a full viewport

### NICE_TO_HAVE
- shared row/card switch primitive
- progressive disclosure for secondary fields

Result: **PASS_WITH_NOTES / PROTOTYPE_READY_FOR_REVIEW**

Prototype: `docs/design/issue-542-trade-analysis-mobile-prototype.svg`

Issue #79 untouched.  
Broadcast checked through: comment_id=5282646722 — VERIFIED
