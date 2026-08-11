---
layout: site
title: Home
description: 投資判断の流れと今日見る入口を30秒で把握するSado Investment OS
permalink: /
---

<link rel="stylesheet" href="{{ '/assets/design-system.css' | relative_url }}">
<link rel="stylesheet" href="{{ '/assets/images/home-os-map.css' | relative_url }}">

<div class="codex-page-shell home-os-shell">
  <header class="codex-page-header home-os-header">
    <p class="eyebrow">SADO INVESTMENT OS</p>
    <h1>今日の投資判断を、ここから始める。</h1>
    <p class="lead">市場を観測し、企業を理解し、仮説を立て、判断し、売買前確認と振り返りまでを一つの循環として辿る入口です。</p>
  </header>

  <section class="home-os-section home-today" aria-labelledby="today-title">
    <p class="eyebrow">TODAY</p>
    <h2 id="today-title">今日見る</h2>
    <p>Home独自のBUY/SELL判定や優先順位スコアは作りません。既存のread-only画面へ直接進みます。</p>
    <!-- SIL:TODAY_ENTRIES -->
  </section>

  <section class="home-os-section" aria-labelledby="status-title">
    <p class="eyebrow">STATUS</p>
    <h2 id="status-title">重要な変化・状態</h2>
    <div class="codex-alert" data-state="unavailable">
      <strong>Homeでの鮮度・重要変化の自動集約は未接続です</strong>
      <p>取得できていない状態を「問題なし」「最新」とは扱いません。PR2で既存Morning / Review等のread modelへ接続します。</p>
    </div>
  </section>

  <section class="home-os-section" aria-labelledby="map-title">
    <p class="eyebrow">INVESTMENT LOOP</p>
    <h2 id="map-title">Investment OS 全体像</h2>
    <p class="home-os-loop"><!-- SIL:OS_LOOP_LABEL --></p>
    <p>9段階を一度に暗記する必要はありません。いまの目的に近い入口から入り、必要な情報だけ確認して次へ進みます。</p>
    <!-- SIL:OS_MAP_STAGES -->
  </section>

  <section class="home-os-section" aria-labelledby="entry-title">
    <p class="eyebrow">PRIMARY ENTRIES</p>
    <h2 id="entry-title">主要入口</h2>
    <div class="codex-summary-grid home-primary-grid">
      <article class="codex-summary-card"><h3>銘柄を探す</h3><p>市場フェーズや資金の流れから候補を見る。</p><a class="codex-action codex-action--secondary" href="{{ '/research/market-phase/ai-semiconductor/' | relative_url }}">Market Phase</a></article>
      <article class="codex-summary-card"><h3>企業を理解する</h3><p>事業・利益構造と投資仮説の材料を確認する。</p><a class="codex-action codex-action--secondary" href="{{ '/companies/' | relative_url }}">Company Research</a></article>
      <article class="codex-summary-card"><h3>判断する</h3><p>前回との差と仮説の状態をDecision Cockpitで確認する。</p><a class="codex-action codex-action--secondary" href="{{ '/decision-cockpit/daihen/' | relative_url }}">Decision Cockpit</a></article>
      <article class="codex-summary-card"><h3>売買前確認</h3><p>実行前にポートフォリオへの影響を確認する。</p><a class="codex-action codex-action--secondary" href="{{ '/risk-preflight/' | relative_url }}">Risk Preflight</a></article>
      <article class="codex-summary-card"><h3>振り返る</h3><p>売買記録と実取引分析から次の判断を改善する。</p><a class="codex-action codex-action--secondary" href="{{ '/trade-journal/' | relative_url }}">Trade Journal</a></article>
    </div>
    <!-- legacy build_risk_preflight marker: ## 🛡️ 売買前のポートフォリオ確認 -->
  </section>

  <details class="codex-disclosure home-research-tools">
    <summary>その他の研究・診断ツール</summary>
    <div class="codex-disclosure__body">
      <ul>
        <li><a href="{{ '/research/investor-dna/' | relative_url }}">Investor DNA</a> — 実取引から得意・不得意の原因を確認</li>
        <li><a href="{{ '/research/morning-dataset/' | relative_url }}">Morning Dataset</a> — 朝の分析に使うFact・Featureと鮮度を確認</li>
        <li><a href="{{ '/research/ai-key-person-watch/' | relative_url }}">AI Key Person Watch</a> — AI主要人物の重要差分を確認</li>
        <li><a href="{{ '/architecture/' | relative_url }}">Architecture</a> — Investment Decision OSと分析基盤の設計を確認</li>
      </ul>
    </div>
  </details>

  <details class="codex-disclosure home-os-notes">
    <summary>このHomeがしないこと</summary>
    <div class="codex-disclosure__body">
      <ul>
        <li>Home専用のCanonical truthを作らない</li>
        <li>BUY / SELLや独自priority scoreを生成しない</li>
        <li>missing / stale / unavailableを正常値へ丸めない</li>
        <li>既存URLやdeep-linkを置き換えない</li>
      </ul>
    </div>
  </details>
</div>
