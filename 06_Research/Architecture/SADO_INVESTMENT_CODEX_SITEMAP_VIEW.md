# Sado Investment Codex — 建築図面

> 担当: 🌊ナギ  
> 種別: Architecture / Pages Read Model  
> Canonical: `00_Framework/SADO_INVESTMENT_CODEX_SITEMAP.md`  
> Product / IA Authority: 🌙ルナ  
> Visual Authority: ⭐️ミナ / Issue #324 comment `5249241479`  
> Design System: #320 / Navigation Authority: #314

<section class="codex-page-shell">
<header class="codex-page-header">
<p class="codex-eyebrow">Sitemap / Evolution Roadmap</p>

この画面は、日常の投資プロセスを案内するCodex Mapではなく、**Codexそのものをどう育てているかを見る建築図面**です。Canonical Sitemapをread-onlyに投影し、Issueのopen/closedだけでPages完成状態を決めません。

<div class="codex-page-header__meta">
<span>Architecture v1.3-runtime-sync-pr4-open</span>
<span>Canonical review: 2026-08-11</span>
</div>
</header>

## まず30秒で見る

<div class="codex-summary-grid">
<article class="codex-summary-card">
<span class="codex-card-question">いまどこまで出来ている？</span>
<h3>主要な入口はLIVE</h3>
<span class="codex-status-chip" data-state="supportive">LIVE / DONE</span>
<p>Home、Company Research、Decision Cockpit、Risk Preflight、Trade Journalは到達可能。Git-Native Runtime Architectureも完成済みです。</p>
</article>

<article class="codex-summary-card">
<span class="codex-card-question">次に何を作る？</span>
<h3>#324 PR4 — この建築図面</h3>
<span class="codex-status-chip" data-state="normal">NEXT</span>
<p>現在地・Build Order・EvolutionをPagesから短時間で追えるようにする正式な残sliceです。</p>
</article>

<article class="codex-summary-card">
<span class="codex-card-question">その先どこを育てる？</span>
<h3>Concept → Navigation → 実戦UX → Money Flow</h3>
<span class="codex-status-chip" data-state="unknown">PLANNED</span>
<p>未実装routeをliveに見せず、Canonical Build Orderに沿って段階的に進化させます。</p>
</article>
</div>

<div class="codex-alert" data-state="normal">
<strong>NEXTは「チーム全体の唯一の次作業」ではありません</strong>
<p>node-local NEXTとImplementation Laneの順番は別物です。既存IMPLEMENTING laneを割り込まず、依存順とSingle Ownerを優先します。</p>
</div>

## 現在のBuild Order

<ol>
<li><strong>Home / OS Map</strong> — #312</li>
<li><strong>Concept Architecture + Cockpit Concept</strong> — #313 / #317</li>
<li><strong>Global Navigation</strong> — #314</li>
<li><strong>Practical Decision UX</strong> — #307 / #308</li>
<li><strong>Money Flow daily operation</strong> — #305</li>
</ol>

## Codex concept map — 9-stage loop

> ⭐️ミナの合意済みCodex概念図をreference visualとして、巨大な横長図を縮小せず、stageごとのprogressive disclosureへ変換しています。

<details class="codex-disclosure" open>
<summary>1. Observe / 観測 <span class="codex-status-chip" data-state="unknown">PLANNED</span></summary>
<div class="codex-disclosure__body">
Market Intelligence / News / Daily Context / Money Flow。Money Flow daily operationは #305 で継続。
</div>
</details>

<details class="codex-disclosure">
<summary>2. Discover / 発見 <span class="codex-status-chip" data-state="unknown">DESIGNED</span></summary>
<div class="codex-disclosure__body">
Candidate Selector / Developing Signals。専用routeはこのCanonical snapshotではLIVE確認していません。
</div>
</details>

<details class="codex-disclosure">
<summary>3. Understand / 理解 <span class="codex-status-chip" data-state="supportive">LIVE</span></summary>
<div class="codex-disclosure__body">
Company Research。verified entry: <a href="{{ '/companies/' | relative_url }}">Companiesを開く</a>。
</div>
</details>

<details class="codex-disclosure">
<summary>4. Hypothesize / 仮説 <span class="codex-status-chip" data-state="unknown">DESIGNED</span></summary>
<div class="codex-disclosure__body">
Investment Hypothesis / Earnings Engine / Bear・Base・Bull。専用routeを推測生成しません。
</div>
</details>

<details class="codex-disclosure" open>
<summary>5. Decide / 判断 <span class="codex-status-chip" data-state="supportive">LIVE</span></summary>
<div class="codex-disclosure__body">
Company Decision CockpitはLIVE。Cockpit Conceptはnode-local NEXTです。
<div class="codex-action-row"><a class="codex-action codex-action--primary" href="{{ '/decision-cockpit/daihen/' | relative_url }}">Decision Cockpitを開く</a></div>
</div>
</details>

<details class="codex-disclosure">
<summary>6. Act / 行動 <span class="codex-status-chip" data-state="unknown">MIXED</span></summary>
<div class="codex-disclosure__body">
Trade IntentはPLANNED。Portfolio PreflightはLIVEです。
<div class="codex-action-row"><a class="codex-action codex-action--secondary" href="{{ '/risk-preflight/' | relative_url }}">Risk Preflightを開く</a></div>
</div>
</details>

<details class="codex-disclosure">
<summary>7. Record / 記録 <span class="codex-status-chip" data-state="supportive">LIVE</span></summary>
<div class="codex-disclosure__body">
Decision Journal / Snapshot / History。zero-trade / NOT_EXECUTED semanticsの最終sliceは別途追跡します。
<div class="codex-action-row"><a class="codex-action codex-action--secondary" href="{{ '/trade-journal/' | relative_url }}">Trade Journalを開く</a></div>
</div>
</details>

<details class="codex-disclosure">
<summary>8. Learn / 振り返り <span class="codex-status-chip" data-state="unknown">DESIGNED</span></summary>
<div class="codex-disclosure__body">
Decision Review / Pattern Lab / Investment Episode。専用LIVE routeは未確認です。
</div>
</details>

<details class="codex-disclosure">
<summary>9. Re-observe / 再観測 <span class="codex-status-chip" data-state="unknown">PLANNED</span></summary>
<div class="codex-disclosure__body">
Catalyst / Checkpoint Timelineから再び市場観測へ戻るloop。routeは未確認です。
</div>
</details>

## Status legend

<div class="codex-status-grid">
<article class="codex-summary-card"><span class="codex-status-chip" data-state="supportive">LIVE / DONE</span><p>現在使える、または成果物として完成。</p></article>
<article class="codex-summary-card"><span class="codex-status-chip" data-state="challenging">BUILDING</span><p>実装中。Owner / sliceを確認して競合を避けます。</p></article>
<article class="codex-summary-card"><span class="codex-status-chip" data-state="normal">NEXT</span><p>そのnodeで次に進める意味のある変化。</p></article>
<article class="codex-summary-card"><span class="codex-status-chip" data-state="unknown">DESIGNED / PLANNED / IDEA</span><p>準備済み、予定、または未確定。LIVE routeとは扱いません。</p></article>
<article class="codex-summary-card"><span class="codex-status-chip" data-state="critical">BLOCKED / DEFERRED / RETIRED</span><p>例外状態。理由と次actionを確認します。</p></article>
</div>

## Verified live entries

<div class="codex-action-row">
<a class="codex-action codex-action--primary" href="{{ '/' | relative_url }}">Home / Codex Map</a>
<a class="codex-action codex-action--secondary" href="{{ '/companies/' | relative_url }}">Company Research</a>
<a class="codex-action codex-action--secondary" href="{{ '/decision-cockpit/daihen/' | relative_url }}">Decision Cockpit</a>
<a class="codex-action codex-action--secondary" href="{{ '/risk-preflight/' | relative_url }}">Risk Preflight</a>
<a class="codex-action codex-action--secondary" href="{{ '/trade-journal/' | relative_url }}">Trade Journal</a>
</div>

<div class="codex-alert" data-state="unknown">
<strong>未確認routeはリンクにしません</strong>
<p>Concept / Candidate / Hypothesis / Learn等は、destinationの存在と到達性が確認されるまでplanned textとして表示します。</p>
</div>

## Architecture plane

- **Codex Map / Home:** 投資プロセスを理解する地図
- **このSitemap / Evolution Roadmap:** Codexを育てる建築図面
- **Runtime Architecture:** Git-native Investment OSがどう動くかを見る仕組み図

詳細なnode registry、Evidence、Evolution itemの正は `00_Framework/SADO_INVESTMENT_CODEX_SITEMAP.md` に残します。このPages viewはCanonical truthを複製する新しいAuthorityではありません。

</section>
