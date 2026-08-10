# Sado Investment Codex — Design System v1

担当: ⭐️ミナ  
種別: Design / UX Specification  
関連: #309, #312, #313, #314

## 1. Product Philosophy

> **未来を予言するための機械ではない。**  
> **不確実な未来を、より良く航行するための道具である。**

市場の兆候を観測し、企業を理解し、仮説を立て、判断し、行動する。そして、その判断と行動、その後に起きた結果を記録し続ける。

Codexは次の問いを継続的に検証する。

- なぜそう判断したのか
- その判断は正しかったのか
- 何を見落としたのか
- 次は何を改善すべきか

検証対象は投資判断だけではない。判断を支える分析、仮説、仕組み、そしてCodex自身も検証対象とする。

日々の投資活動を通じて、**投資家とプラットフォームが共に学び、共に改善し続ける自己成長型 Investment Research Platform** を目指す。

## 2. Canonical Investment Loop

ユーザーへ示す上位循環は以下を正とする。

`1 観測 → 2 発見 → 3 理解 → 4 仮説 → 5 判断 → 6 行動 → 7 記録 → 8 学習 → 9 再観測 → 1 観測 ↻`

| # | 段階 | English | ユーザーの問い | 意味 |
|---|---|---|---|---|
| 1 | 観測 | Observe | 何が起きている？ | 市場・ニュース・政策・資金フローを観測する |
| 2 | 発見 | Discover | 次に何を見る？ | 調べる価値のあるテーマ・銘柄を見つける |
| 3 | 理解 | Understand | この企業は何者？ | 事業・利益ドライバー・Evidenceを理解する |
| 4 | 仮説 | Hypothesize | 何が起きると考える？ | Bear/Base/Bull、利益予想、市場期待との差を仮説化する |
| 5 | 判断 | Decide | What do I think? | 投資妙味を評価し、現在のスタンスを判断する |
| 6 | 行動 | Act | What will I do? | Trade Intentを具体化し、Portfolio影響を確認して実行・見送りを最終決定する |
| 7 | 記録 | Record | What did I do? | 判断時点の理由、Snapshot、実際の取引・見送りを記録する |
| 8 | 学習 | Learn | What did I learn? | 判断と結果の差、改善点、再現可能なパターンを検証する |
| 9 | 再観測 | Re-observe | What changed? | 新しいEvidence・checkpointから次の観測へ戻る |

### Decide / Act の境界

**Decide = 市場・企業に対する自分の見解。**  
Bullish / Neutral / Bearish、買い候補、保有継続、縮小検討などを判断する。ここでは注文そのものを決めない。

**Act = その見解を自分の資産へどう反映するか。**  
Trade Intent、数量・タイミング、Portfolio Risk、資金余力を確認し、実行または見送りを最終決定する。

例: 「ダイヘンにはBullishだが、現在のPortfolio集中度が高いため今日は買い増さない」は矛盾しない。

## 3. Visual Philosophy

### Core statement

**知的で静か。分析は深い。重要な変化だけが鋭く光る。**

Visual metaphorは、最新AIと市場データを搭載しながら、長い航海を続けてきた**知的探査船の研究室 / 操縦室**。

目指す感覚:

- 古典的なのに高度
- 機械なのに温度がある
- 過去を記録しながら、まだ見えない未来を探索する
- 派手なトレーディング画面ではなく、静かな研究環境
- Material change / warning / thesis break / opportunityだけが視覚的に浮かぶ

**世界観は古典、UXは現代。**

操作名称まで物語化しない。「航行開始」等のゲーム的表現は避け、UIラベルは日本語で明快にする。物語は思想・質感・図像に宿す。

## 4. Visual Tokens — Direction

実装時はCSS custom properties等のtokenへ落とす。v1では意味と役割を固定し、最終HEX値は実画面でAccessibilityを確認して調整する。

| Token role | Direction | 意味 |
|---|---|---|
| Canvas / Paper | warm parchment / 生成り | 蓄積された知識・研究ノート |
| Primary Ink | dark charcoal / brown-black | 長文・見出しの可読性 |
| Deep Green | muted forest green | 静かな研究、navigation、操作卓 |
| Brass | muted antique brass | 精密な計器、選択状態、ブランドaccent |
| Divider | warm gray-brown | 古い図面の罫線。強すぎない |
| Positive signal | muted green | 良好・改善。ただし価格上昇だけを意味しない |
| Negative signal | muted red / rust | 警戒・悪化・流出 |
| Attention | muted amber / brass | 要確認・変化・pending |
| Unknown | neutral gray / desaturated | UNKNOWN / PARTIAL / NOT_RUN等。悲観色にしない |
| Corporate accent | muted brand-derived color | 企業識別を残しつつCodex世界観へ調和 |

### Signal rule

色は装飾ではなく意味を持つ。赤/緑を単純な株価上下だけに固定せず、状態・警戒・確信・変化を一貫したVisual Languageとして使用する。

`UNKNOWN / PARTIAL / NOT_RUN / UNAVAILABLE / STALE` は「悪い企業」「弱気」を意味しないため、negative signal色と混同しない。

## 5. Typography — D案

「研究を読む文字」と「データを読む文字」を分ける。

| 用途 | Direction |
|---|---|
| Brand / `SADO INVESTMENT CODEX` | Classic Roman Serif |
| 日本語大見出し | Japanese Serif |
| セクション見出し | Serif中心。UI密度に応じSans併用 |
| 本文 / 説明 / navigation | Japanese Sans Serif |
| 数値 / status / ticker / market data | Monoまたはtabular numeralを優先 |

原則:

- 小さい本文をSerifだけで埋めない。モバイル可読性を優先する。
- 数値列は桁が追いやすいことを優先する。
- 英語statusをユーザーへ露出する場合、日本語の意味を併記または日本語をPrimaryにする。

## 6. Sado Instrument Icon Set

Navigation iconは既製Web UI感を避け、**古い科学・航海・研究器具の線画**を共通言語とする。

写実画にはせず、全アイコンで線の太さ、細部量、陰影量、抽象度を揃える。

| Navigation | Instrument metaphor | 意味 |
|---|---|---|
| Home | 羅針盤 | 今日どちらを見るべきか方向を知る |
| 銘柄を探す | 望遠鏡 | 遠くの機会・兆候を発見する |
| 企業を理解する | 顕微鏡 | 企業を深く調べる |
| 判断する | 天秤 | 根拠・リスク・リターンを比較する |
| 記録する | Ledger / 研究台帳 | 保有・取引・判断の事実を残す |
| 振り返る | 羽根ペン | 考察し、学びを知識化する |

### Icon abstraction rule

Ledgerだけがリアルな革表紙、他が単純線画、といった抽象度差を作らない。原則は**engraved instrument icon / simplified line illustration**の中間。

## 7. Corporate Identity Adaptation

企業ロゴや企業色を原色のまま大量に持ち込むとCodexの世界観が崩れる。

- 元企業の識別性は残す
- 彩度を落とし、Sepia / Muted toneへ適応する
- ブランドそのものを誤認させる改変はしない
- 企業名テキストを必ず併用し、色だけに識別を依存しない
- 例: ダイヘンの青は鮮やかなWeb blueではなく、セピア世界観に馴染むMuted Blueを使用する

## 8. Global Navigation Baseline

第一階層は内部機能名ではなく、ユーザーの行動で統一する。

`Home → 銘柄を探す → 企業を理解する → 判断する → 記録する → 振り返る`

旧「保有・売買」は「保有するか売買するかを判断する場所」と誤解され、`判断する` と意味が重複するため採用しない。

`記録する` 配下にPortfolio / 保有 / Trade records / Journal等を配置し、実際の発注機能があるような誤認を避ける。

## 9. Page Hierarchy / Information Architecture

### Home

Homeは**今日の司令塔**。

基本順序:

1. 市場で何が起きている？ — Money Flow / Heatmap
2. 自分の保有銘柄にどう関係する？ — Portfolio impact / related news
3. では今日何を見る？ — 最大3件程度の優先action

30秒で「なぜ今日見るか」「何が変わったか」「次に何をするか」へ到達できること。

### Codex Map

Codex Mapは**全体の地図 / Product Philosophy**。

- 9段階Investment Loop
- 各段階の問い
- Codex Philosophy
- Data Flow
- Safety / Authority
- 主要Journey
- 各機能への入口

HomeとCodex Mapを同じ役割にしない。

### Research

企業を理解する場所。事業、利益ドライバー、Evidence、決算、Revisionを中心にする。

### Cockpit

判断材料を比較し、前回判断との差を理解する**意思決定室**。Research本文を重複掲載する場所ではない。

### Record

保有・取引・Decision Snapshot等、起きた事実を確認する場所。

### Review

Outcome / Opportunity Cost / Pattern / Forecast calibration等から「何を学んだか」へ到達する場所。

## 10. Component Principles

### Cards

- 1 card = 1 question / 1 responsibilityを基本とする
- Card内で説明・手順・Evidence・分析を無制限に混在させない
- 最重要結論をcard上部に置く
- 詳細はProgressive Disclosureで下へ降ろす

### Status

statusは英単語だけで理解を要求しない。

推奨例:

- `STALE` → `更新が古い` + 補助status
- `UNAVAILABLE` → `現在取得できません`
- `NOT_RUN` → `まだ実行されていません`
- `PARTIAL` → `一部データのみ`
- `UNKNOWN` → `まだ判断できません`

技術status値は補助表示として保持してよい。

### Tables

- 比較が目的なら文章より表を優先
- モバイルでは横スクロールだけに頼らず、重要列の優先表示またはcard化を検討
- 数値の単位、基準日、前回値を明示する

### Charts / Diagrams

- 時系列 → chart / timeline
- 比較 → table / scenario matrix
- 因果関係 → flow / causal diagram
- 資金移動 → heatmap + flow arrows
- 文章だけで構造を説明しない

## 11. UX Principles

1. **30-second comprehension** — 最初のviewportで重要な変化と次actionが分かる
2. **Progressive Disclosure** — 概要 → 根拠 → sourceへ段階的に降りる
3. **Scannable Content** — 見出し、短い段落、card、tableでチャンク化する
4. **Japanese First** — ユーザー向け意味を日本語で理解できる
5. **Evidence Traceability** — 根拠へ自然に降りられる
6. **Canonical First** — UI都合で新しいtruthを作らない
7. **Mobile First** — desktopの縮小版ではなく、重要度順に再配置する
8. **Consistent Hierarchy** — Home / Research / Cockpit / Record / Reviewで同じ視覚階層を使う
9. **Accessible Meaning** — 色だけでstatus・増減・警告を伝えない
10. **Quiet by default, sharp on change** — 通常状態は静かに、判断を変える情報だけ強くする

## 12. Mobile Baseline

- First viewport: Page title + current context + 最重要1〜3点
- Primary actionはthumb reachを意識するが、固定bottom navigationで本文を過度に隠さない
- 6 primary navigationはicon + 短い日本語labelを基本とする
- 長いCodex Mapは1枚絵を縮小して読ませず、mobileでは9段階を縦timeline / step cardsへ再構成する
- 高密度Cockpitはsummary → scenario → evidenceの順にProgressive Disclosureする
- 44px相当以上のtouch targetを目安にし、近接リンクを詰め込みすぎない

## 13. Implementation Contract

- このDesign Systemは表示・UXのAuthorityであり、既存Canonical dataのAuthorityを変更しない
- 既存URL / deep-linkを一括破壊しない
- Design System変更とCanonical logic変更を同一PRへ混ぜない
- 画像生成prototypeはVisual reference。画像内の文字・番号・数値はCanonicalではない
- 実装文字列はHTML/CSS等の実テキストとし、日本語の誤記・画像生成文字崩れを持ち込まない
- #312 / #313 / #314 はこの文書をVisual Contractとして参照する

## 14. Acceptance Checklist

- [ ] 一部分のスクリーンショットでもSado Investment Codexと認識できる
- [ ] 生成り / 深緑 / 真鍮 / Instrument iconが装飾ではなく意味を持っている
- [ ] Typographyが研究・UI・数値で役割分離されている
- [ ] 6 primary navigationの名称・icon抽象度が統一されている
- [ ] UNKNOWN/PARTIAL等をnegative signalと誤認しない
- [ ] Corporate accentが原色のまま浮いていない
- [ ] Homeで市場 → 自分への影響 → 今日のactionへ30秒で到達できる
- [ ] Codex Mapの9段階が `1→2→3→4→5→6→7→8→9→1` の順である
- [ ] Decide / Act / Record / Learnの責務が混ざっていない
- [ ] Mobileで最重要情報がfirst viewportへ出る
- [ ] 根拠・sourceへ自然にdrill-downできる
- [ ] 既存Canonical / SSoT / deep-linkを壊していない

---

Design baseline approved by 👑サド with ⭐️ミナ.  
**Worldview: Classical. UX: Modern.**
