---
layout: site
title: Design System Fixture
description: Sado Investment Codex Visual Design System v1の決定論的fixture
permalink: /design-system-fixture/
---

<div class="codex-page-shell codex-design-fixture">
  <header class="codex-page-header">
    <span class="codex-instrument-icon" aria-hidden="true">⌖</span>
    <p class="codex-card-question">Design regression fixture</p>
    <h1>Sado Investment Codex — 共通UI基盤</h1>
    <p>同じ意味を同じprimitiveで表現し、Home / Navigation / Cockpitへ安全に再利用するための確認ページです。</p>
    <div class="codex-page-header__meta">
      <span>基準日: 2026-08-11</span>
      <span>Freshness: fixture / deterministic</span>
    </div>
  </header>

  <section aria-labelledby="fixture-summary">
    <h2 id="fixture-summary">重要な状態と数値</h2>
    <div class="codex-summary-grid">
      <article class="codex-summary-card">
        <span class="codex-card-question">現在の判断材料は読めるか</span>
        <span class="codex-status-chip" data-state="normal">通常</span>
        <div class="codex-kpi">
          <strong class="codex-kpi__value">12,480</strong>
          <span class="codex-kpi__unit">円</span>
          <span class="codex-kpi__basis">Base想定 / 2026-08-11</span>
        </div>
        <div class="codex-delta" aria-label="前回11500円から現在12480円へ上昇">
          <span>前回 11,500円</span><span class="codex-delta__arrow">→</span><strong>現在 12,480円</strong>
          <span class="codex-delta__label">+980円</span>
        </div>
      </article>
      <article class="codex-summary-card">
        <span class="codex-card-question">追い風となるEvidenceはあるか</span>
        <span class="codex-status-chip" data-state="supportive">追い風</span>
        <p>既存仮説を支える材料が確認されています。価格上昇そのものを意味するstatusではありません。</p>
      </article>
      <article class="codex-summary-card">
        <span class="codex-card-question">注意すべき変化はあるか</span>
        <span class="codex-status-chip" data-state="challenging">要確認</span>
        <p>前提の一部に確認事項があります。売買判断へ自動変換しません。</p>
      </article>
      <article class="codex-summary-card">
        <span class="codex-card-question">仮説を壊し得る警告はあるか</span>
        <span class="codex-status-chip" data-state="critical">重要警告</span>
        <p>反証候補がある場合の表示例です。理由と根拠を必ず併記します。</p>
      </article>
    </div>
  </section>

  <section aria-labelledby="fixture-data-quality">
    <h2 id="fixture-data-quality">データ品質</h2>
    <div class="codex-status-grid">
      <div class="codex-alert" data-state="stale">
        <strong><span class="codex-status-chip" data-state="stale">更新が古い</span></strong>
        <p>最終更新が確認基準を超えています。古い値を最新値として見せません。</p>
      </div>
      <div class="codex-alert" data-state="unavailable">
        <strong><span class="codex-status-chip" data-state="unavailable">現在取得できません</span></strong>
        <p>データが取得できない状態です。0や正常値へ置き換えません。</p>
      </div>
      <div class="codex-alert" data-state="unknown">
        <strong><span class="codex-status-chip" data-state="unknown">まだ判断できません</span></strong>
        <p>情報不足または未定義です。弱気・中立・問題なしの意味にはしません。</p>
      </div>
    </div>
  </section>

  <section aria-labelledby="fixture-scenario">
    <h2 id="fixture-scenario">Bear / Base / Bull</h2>
    <p>シナリオはsystem success/errorとは別semantic namespaceで表現します。</p>
    <div class="codex-scenario-grid">
      <article class="codex-scenario-card" data-scenario="bear">
        <span class="codex-scenario-card__label">Bear</span>
        <h3>下振れシナリオ</h3>
        <p>需要鈍化や利益率悪化など、成立条件を明示します。</p>
      </article>
      <article class="codex-scenario-card" data-scenario="base">
        <span class="codex-scenario-card__label">Base</span>
        <h3>中心シナリオ</h3>
        <p>現時点で最も妥当とみる前提を記録します。</p>
      </article>
      <article class="codex-scenario-card" data-scenario="bull">
        <span class="codex-scenario-card__label">Bull</span>
        <h3>上振れシナリオ</h3>
        <p>追加成長や利益率改善など、成立条件を分離します。</p>
      </article>
    </div>
  </section>

  <section aria-labelledby="fixture-actions">
    <h2 id="fixture-actions">次に確認する</h2>
    <div class="codex-action-row">
      <a class="codex-action codex-action--primary" href="#fixture-evidence">根拠を詳しく見る</a>
      <a class="codex-action codex-action--secondary" href="#fixture-data-quality">データ品質を確認する</a>
    </div>

    <div class="codex-evidence" id="fixture-evidence">
      <a href="#fixture-summary">判断の背景と元データを見る</a>
      <div class="codex-evidence__meta">Source: deterministic fixture / as_of 2026-08-11 / Canonical mutationなし</div>
    </div>

    <details class="codex-disclosure">
      <summary>なぜこの表示なのか</summary>
      <div class="codex-disclosure__body">
        まず要約を読み、必要な時だけ理由とsourceへ降ります。UNKNOWN / STALE / UNAVAILABLEを正常値へ丸めず、BUY / SELLも生成しません。
      </div>
    </details>
  </section>
</div>
