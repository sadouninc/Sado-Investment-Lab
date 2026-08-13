# #537 Home Mobile Regression Fixture

担当: ⭐️ミナ
種別: Design / UX Regression Fixture
Parent: #418
Refs: #320

390px / 320pxで、Homeのpage purpose・主要status/action・次sectionへの到達性を維持するためのregression contract。

## BLOCKER
- page-level horizontal overflow
- H1 / theme toggle / navigation collision
- heroだけでfirst viewportを使い切る
- blank scrollを生むspacing二重適用
- page-specific第二CSS体系
- primary actionが内部情報の後ろへ押し出される

## SHOULD_FIX
- H1の不自然な3行以上wrap
- leadが長く主要actionがfirst viewportから消える
- section gapとcard gapの差が弱い

## Shared contract
- #320 PageShell / PageHeader / shared heading scale / section stack / SummaryCardを再利用
- Homeの責務は「市場 → 自分への影響 → 今日のaction」
- Codex MapのOS説明、Cockpitの詳細判断材料、内部Issue refをfirst-viewへ複製しない

Result: PASS_WITH_NOTES / REGRESSION_CONTRACT_READY

Issue #79 untouched.
Broadcast checked through: comment_id=5281996507 — VERIFIED
