---
layout: site
title: Investment Decision Cockpit — 見方ガイド
permalink: /concepts/investment-decision-cockpit/
---

<link rel="stylesheet" href="{{ '/assets/design-system.css' | relative_url }}">

<div class="codex-page-shell">
  <header class="codex-page-header">
    <span class="codex-instrument-icon" aria-hidden="true">◇</span>
    <p class="codex-card-question">Investment OS / 5 判断する</p>
    <h1>Investment Decision Cockpit — 見方ガイド</h1>
    <p>前回の判断から何が変わったかを確認し、現在の投資仮説と評価を一つの流れで点検するための画面です。</p>
    <div class="codex-page-header__meta">
      <span>最終確認: 2026-08-11</span>
      <span>Concept contract: #313 / #317 / #312 / #320</span>
    </div>
  </header>

  <section aria-labelledby="first-checks">
    <h2 id="first-checks">最初の30秒で見る3点</h2>
    <p>変化、期待差、仮説と評価を分断せずに見ることで、判断の前提がどこで変わったかを追跡できます。</p>
    <div class="codex-summary-grid">
<article class="codex-summary-card"><p class="codex-card-question">最初に見る 1</p><h3>前回判断からの変化</h3></article>
<article class="codex-summary-card"><p class="codex-card-question">最初に見る 2</p><h3>市場期待との差</h3></article>
<article class="codex-summary-card"><p class="codex-card-question">最初に見る 3</p><h3>仮説・Valuation・売買前ポートフォリオ影響の状態</h3></article>
    </div>
  </section>

  <section aria-labelledby="decision-flow">
    <h2 id="decision-flow">判断の流れ</h2>
    <div class="codex-evidence">
      <strong>前回判断 → 現在との差 → 市場期待との差 → 仮説確認 → Valuation → 売買前PF影響 → 判断Snapshot → 次checkpoint</strong>
      <div class="codex-evidence__meta">CockpitはDecideの画面です。売買前確認・記録の詳細は次の既存画面へ進みます。</div>
    </div>
  </section>

  <section aria-labelledby="state-meaning">
    <h2 id="state-meaning">状態の意味</h2>
    <p>取得不能や古い情報を、正常・中立・悲観へ丸めません。</p>
<article class="codex-alert" data-state="unknown"><strong><span class="codex-status-chip" data-state="unknown">UNKNOWN</span></strong><p>必要な情報を確認できず、状態を確定できません。正常や中立とは扱いません。</p></article>
<article class="codex-alert" data-state="unavailable"><strong><span class="codex-status-chip" data-state="unavailable">UNAVAILABLE</span></strong><p>参照先または必要な情報を現在利用できません。推測値で補完しません。</p></article>
<article class="codex-alert" data-state="stale"><strong><span class="codex-status-chip" data-state="stale">STALE</span></strong><p>情報の鮮度が基準を満たしていません。最新情報として扱わず、更新元を確認します。</p></article>
  </section>

  <section aria-labelledby="next-actions">
    <h2 id="next-actions">次に進む</h2>
    <div class="codex-action-row">
      <a class="codex-action codex-action--primary" href="{{ '/decision-cockpit/daihen/' | relative_url }}">Live Cockpitを開く</a>
<a class="codex-action codex-action--secondary" href="{{ '/risk-preflight/' | relative_url }}">売買前の影響を確認する</a>
<a class="codex-action codex-action--secondary" href="{{ '/trade-journal/' | relative_url }}">判断・取引の記録を見る</a>
    </div>
  </section>

  <section aria-labelledby="evidence-links">
    <h2 id="evidence-links">根拠を見る</h2>
<div class="codex-evidence"><a class="codex-action codex-action--secondary" href="{{ '/companies/' | relative_url }}">企業研究の根拠を見る</a><div class="codex-evidence__meta">Canonical source / route truthを参照</div></div>
<div class="codex-evidence"><a class="codex-action codex-action--secondary" href="{{ '/framework/' | relative_url }}">投資Frameworkを確認する</a><div class="codex-evidence__meta">Canonical source / route truthを参照</div></div>
  </section>

  <details class="codex-disclosure">
    <summary>この機能がしないこと</summary>
    <div class="codex-disclosure__body">
      <ul>
<li>BUY / SELL / ADD / REDUCEを自動決定しない</li>
<li>Ownerのconfidence・threshold・投資思想を推測補完しない</li>
<li>Canonical Research / Scenario / Hypothesis / Decisionを変更しない</li>
      </ul>
    </div>
  </details>
</div>
