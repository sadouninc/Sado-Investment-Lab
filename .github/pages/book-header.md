---
layout: site
title: Framework Web Edition
description: 市場と企業を理解し、自分自身の投資理論を磨き続けるためのFramework
permalink: /framework/
---

<header class="book-hero" id="framework-top">
  <p class="eyebrow">SADO INVESTMENT LAB</p>
  <h1>投資という、終わりのない研究。</h1>
  <p class="lead">市場を理解し、企業を理解し、自分自身の投資理論を磨き続けるためのFramework。</p>
  <p class="edition">Framework Web Edition</p>
</header>

<section class="framework-overview" aria-labelledby="framework-overview-title">
  <p class="toc-label">30 SECOND OVERVIEW</p>
  <h2 id="framework-overview-title">読みたい章から始める</h2>
  <p>Frameworkは8つの大章で構成されています。最初から通読するだけでなく、いま必要な判断基準へ直接移動できます。</p>
  <div class="framework-chapter-cards">
    <a class="framework-chapter-card" href="#philosophy"><strong>01 Investment Philosophy</strong><span>投資の目的と、企業価値・市場評価をどう捉えるか。</span></a>
    <a class="framework-chapter-card" href="#psychology"><strong>02 Market Psychology</strong><span>市場参加者の期待・恐怖・評価変化をどう読むか。</span></a>
    <a class="framework-chapter-card" href="#thinking"><strong>03 Thinking Process</strong><span>事実・解釈・仮説を分け、判断へつなげる思考手順。</span></a>
    <a class="framework-chapter-card" href="#rules"><strong>04 Investment Rules</strong><span>売買・リスク管理・意思決定で守る実践ルール。</span></a>
    <a class="framework-chapter-card" href="#evaluation"><strong>05 Evaluation Framework</strong><span>企業・成長性・市場評価を同じ尺度で比較する枠組み。</span></a>
    <a class="framework-chapter-card" href="#allocation"><strong>06 Capital Allocation</strong><span>資金配分・余力・ポジションサイズを管理する考え方。</span></a>
    <a class="framework-chapter-card" href="#lessons"><strong>07 Lessons Learned</strong><span>過去の判断から再利用可能な教訓を蓄積する章。</span></a>
    <a class="framework-chapter-card" href="#metrics"><strong>08 Original Metrics</strong><span>Sado Investment Lab独自の評価軸・観測指標。</span></a>
  </div>
</section>

<nav class="framework-jump-nav" aria-label="Framework章ナビゲーション">
  <a href="#framework-top" class="framework-jump-home">目次</a>
  <div class="framework-jump-scroll">
    <a href="#philosophy" data-framework-target="philosophy">01 Philosophy</a>
    <a href="#psychology" data-framework-target="psychology">02 Psychology</a>
    <a href="#thinking" data-framework-target="thinking">03 Thinking</a>
    <a href="#rules" data-framework-target="rules">04 Rules</a>
    <a href="#evaluation" data-framework-target="evaluation">05 Evaluation</a>
    <a href="#allocation" data-framework-target="allocation">06 Allocation</a>
    <a href="#lessons" data-framework-target="lessons">07 Lessons</a>
    <a href="#metrics" data-framework-target="metrics">08 Metrics</a>
  </div>
</nav>

<p class="reading-note">このWeb書籍は、リポジトリ内の各Framework文書を唯一の元データとして自動生成しています。表示上のナビゲーションだけを追加し、Framework本文は変更しません。</p>

<style>
  .framework-overview {
    margin: clamp(3rem, 8vw, 6rem) 0 3rem;
    padding: clamp(1.3rem, 4vw, 2.2rem);
    border: 1px solid var(--line);
    background: var(--card);
  }
  .framework-overview h2 { margin: .35rem 0 1rem; }
  .framework-overview > p:last-of-type { color: var(--muted); }
  .framework-chapter-cards {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: .8rem;
    margin-top: 1.5rem;
  }
  .framework-chapter-card {
    display: flex;
    flex-direction: column;
    gap: .45rem;
    min-height: 8rem;
    padding: 1rem;
    border: 1px solid var(--line);
    color: var(--ink);
    text-decoration: none;
    background: color-mix(in srgb, var(--card) 78%, transparent);
  }
  .framework-chapter-card:hover,
  .framework-chapter-card:focus-visible { border-color: var(--accent); }
  .framework-chapter-card strong { font-family: "Noto Serif JP", serif; line-height: 1.45; }
  .framework-chapter-card span { color: var(--muted); font-size: .82rem; line-height: 1.7; }
  .framework-jump-nav {
    position: sticky;
    z-index: 12;
    top: 64px;
    display: flex;
    align-items: center;
    gap: .7rem;
    margin: 2rem 0 4rem;
    padding: .7rem;
    border: 1px solid var(--line);
    background: color-mix(in srgb, var(--paper) 94%, transparent);
    backdrop-filter: blur(14px);
  }
  .framework-jump-home,
  .framework-jump-scroll a {
    display: inline-flex;
    align-items: center;
    min-height: 2.2rem;
    padding: .35rem .65rem;
    color: var(--muted);
    border: 1px solid transparent;
    text-decoration: none;
    font-size: .74rem;
    line-height: 1.25;
    white-space: nowrap;
  }
  .framework-jump-home { color: var(--ink); font-weight: 700; border-color: var(--line); }
  .framework-jump-scroll { display: flex; gap: .25rem; overflow-x: auto; scrollbar-width: thin; }
  .framework-jump-scroll a[aria-current="location"] {
    color: var(--ink);
    border-color: var(--accent);
    background: var(--accent-soft);
  }
  .book-chapter { scroll-margin-top: 9rem; }
  .book-chapter blockquote {
    position: relative;
    padding-top: 2rem;
    color: var(--ink);
    background: color-mix(in srgb, var(--accent-soft) 45%, transparent);
  }
  .book-chapter blockquote::before {
    content: "KEY PRINCIPLE";
    position: absolute;
    top: .45rem;
    left: 1.5rem;
    color: var(--accent);
    font-size: .68rem;
    font-weight: 700;
    letter-spacing: .16em;
  }
  .framework-chapter-footer {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    gap: .7rem;
    margin: 4rem 0 1rem;
    padding-top: 1.2rem;
    border-top: 1px solid var(--line);
  }
  .framework-chapter-footer a {
    padding: .7rem .8rem;
    border: 1px solid var(--line);
    color: var(--ink);
    text-decoration: none;
    font-size: .78rem;
    line-height: 1.45;
  }
  .framework-chapter-footer .next { text-align: right; }
  @media (max-width: 640px) {
    .framework-chapter-cards { grid-template-columns: 1fr; }
    .framework-jump-nav { top: 112px; margin-left: -15px; margin-right: -15px; border-left: 0; border-right: 0; }
    .framework-jump-scroll { padding-right: .5rem; }
    .framework-chapter-footer { grid-template-columns: 1fr 1fr; }
    .framework-chapter-footer .contents { grid-column: 1 / -1; grid-row: 1; text-align: center; }
    .framework-chapter-footer .previous { grid-column: 1; grid-row: 2; }
    .framework-chapter-footer .next { grid-column: 2; grid-row: 2; }
  }
</style>

<script>
(() => {
  const setupFrameworkNavigation = () => {
    const sections = Array.from(document.querySelectorAll('.book-chapter[id]'));
    const jumpLinks = Array.from(document.querySelectorAll('[data-framework-target]'));
    if (!sections.length || !jumpLinks.length) return;

    sections.forEach((section, index) => {
      if (section.querySelector(':scope > .framework-chapter-footer')) return;
      const footer = document.createElement('nav');
      footer.className = 'framework-chapter-footer';
      footer.setAttribute('aria-label', '章移動');

      const previous = index > 0
        ? `<a class="previous" href="#${sections[index - 1].id}">← 前の章</a>`
        : '<span></span>';
      const next = index < sections.length - 1
        ? `<a class="next" href="#${sections[index + 1].id}">次の章 →</a>`
        : '<span></span>';
      footer.innerHTML = `${previous}<a class="contents" href="#framework-top">目次へ戻る</a>${next}`;
      section.appendChild(footer);
    });

    const byId = new Map(jumpLinks.map(link => [link.dataset.frameworkTarget, link]));
    const setCurrent = id => {
      jumpLinks.forEach(link => link.removeAttribute('aria-current'));
      const current = byId.get(id);
      if (current) current.setAttribute('aria-current', 'location');
    };

    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver(entries => {
        const visible = entries
          .filter(entry => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]) setCurrent(visible[0].target.id);
      }, { rootMargin: '-18% 0px -62% 0px', threshold: [0, .1, .25] });
      sections.forEach(section => observer.observe(section));
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupFrameworkNavigation, { once: true });
  } else {
    setupFrameworkNavigation();
  }
})();
</script>
