# Sado Investment OS — 仕組みを30秒で理解する

> 担当: 🌊ナギ  
> 種別: Architecture / Pages Read Model  
> Canonical: `00_Framework/Architecture/GIT_NATIVE_AGENTIC_RUNTIME.md` + `00_Framework/Architecture/GIT_NATIVE_AGENTIC_RUNTIME_DIAGRAMS.md`  
> Visual Authority: #320  
> Navigation Authority: #314

<section class="codex-page-shell">
<header class="codex-page-header">
<p class="codex-eyebrow">Architecture / Runtime</p>

Investment OSの本体は、**GitHub上の永続状態・Issue / PR・Actions・履歴**です。AIは意味理解・整理・提案を担い、検証可能な処理はdeterministic logicへ分離します。最終の投資判断Authorityは👑サドに残ります。
</header>

<div class="codex-summary-grid">
<article class="codex-summary-card"><strong>OS本体</strong><p>GitHub Operating Substrate + Canonical State。チャット履歴だけをSSoTにしません。</p></article>
<article class="codex-summary-card"><strong>AIの責務</strong><p>意味理解・整理・提案。AI推論をdeterministic factへsilent promotionしません。</p></article>
<article class="codex-summary-card"><strong>最重要の安全境界</strong><p><strong>CI green / merge ≠ BUY・SELL承認。</strong> Owner AuthorityはGitHub上のsoftware stateとは別です。</p></article>
</div>

<div class="codex-alert" data-state="normal">
<strong>CURRENT と EVOLUTIONを分離</strong>
<p>現在repository / Actions / Pagesで確認できるflowと、将来のPages input・external integration・replayを同じ「実装済み」に見せません。</p>
</div>

<details class="codex-progressive-disclosure" open>
<summary><strong>0. System Overview — User / AI / GitHub</strong><span>誰が、どの入口から、GitHub上のInvestment OSを利用するか。</span></summary>
<div class="codex-progressive-disclosure__content">
<img src="https://raw.githubusercontent.com/sadouninc/Sado-Investment-Lab/main/00_Framework/Architecture/diagrams/349_system_overview.svg" alt="Sado Investment OS全体図。ユーザー、スマートフォンとPC、ChatGPT/Codex、Pages/Cockpit、GitHub上のOS、OpenAI API、BrokerとMarketの責務境界を示す。" loading="lazy" style="width:100%;height:auto">

- **対話UI:** ChatGPT / Codex
- **OS UI:** Pages / Cockpit
- ChatGPT / Codex と OpenAI API / Model は別責務。
- Brokerで約定しただけではOSは未観測。会話・CSV・将来integrationなどで初めてInputになる。
</div>
</details>

<details class="codex-progressive-disclosure">
<summary><strong>1. Runtime Architecture</strong><span>AI Semantic LayerとDeterministic Logicを一本の自動化pipelineに見せない。</span></summary>
<div class="codex-progressive-disclosure__content">
<img src="https://raw.githubusercontent.com/sadouninc/Sado-Investment-Lab/main/00_Framework/Architecture/diagrams/349_runtime_architecture.svg" alt="Runtime Architecture図。AI Semantic Layer、GitHub Operating Substrate、Canonical State、Deterministic Logic、Derived Read Model、Owner judgmentを別レイヤーとして示す。" loading="lazy" style="width:100%;height:auto">

```text
Input / Event
→ AI Semantic Interpretation
→ Proposed Change / GitHub Operating Substrate
→ Review / CI / accepted state transition
→ Canonical State + Deterministic Logic
→ Derived Read Model
→ Pages / Cockpit
→ 👑 Owner judgment
```

すべてのeventが必ず全layerを通るわけではありません。責務境界を示す図です。
</div>
</details>

<details class="codex-progressive-disclosure">
<summary><strong>2. Git as State Machine</strong><span>Issue / branch / commit / PR / review / CI / mergeを監査可能なstate transitionとして読む。</span></summary>
<div class="codex-progressive-disclosure__content">
<img src="https://raw.githubusercontent.com/sadouninc/Sado-Investment-Lab/main/00_Framework/Architecture/diagrams/349_git_state_machine.svg" alt="Git State Machine図。未解決要求からbranch、commit、PR、reviewとCI、acceptedまたはrejected、merge後の次状態への遷移を示す。" loading="lazy" style="width:100%;height:auto">

**重要:** `merge = BUY/SELL承認` ではありません。mergeはsoftware / data / document stateの受理です。投資判断Authorityは別に残ります。
</div>
</details>

<details class="codex-progressive-disclosure">
<summary><strong>3. Versioned Input / Self-evolving Observation</strong><span>データだけでなく「何を観測するか」そのものもGitでversion管理する。</span></summary>
<div class="codex-progressive-disclosure__content">
<img src="https://raw.githubusercontent.com/sadouninc/Sado-Investment-Lab/main/00_Framework/Architecture/diagrams/349_versioned_input.svg" alt="Versioned Input図。新signal requirementからsensor、rule、config、agent contract変更をPRでreviewし、将来の観測dimensionを追加する流れを示す。" loading="lazy" style="width:100%;height:auto">

将来のreplayでは、Past Canonical Stateだけでなく、**Past Logic / config / observation contractのversion**も必要です。PR3ではReplay Engine自体は実装しません。
</div>
</details>

<div class="codex-alert" data-state="warning">
<strong>Canonical truthへの昇格条件</strong>
<p>Pages inputやAI outputを直接Canonical truthへ書き込みません。Validation → Proposed Change / Preview → Owner Approval → Persistenceを経由します。UNKNOWN / UNAVAILABLE / STALEも正常値へ丸めません。</p>
</div>

## 詳細を読む

- `GIT_NATIVE_AGENTIC_RUNTIME.md` — RuntimeのCanonical text
- `GIT_NATIVE_AGENTIC_RUNTIME_DIAGRAMS.md` — 4図のaccessible text explanation
- `SADO_INVESTMENT_CODEX_SITEMAP.md` — #324 建築状態 / Build Order

</section>
