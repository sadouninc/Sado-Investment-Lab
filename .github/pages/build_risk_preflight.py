from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site-src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


WHAT_IF_WORKFLOW_URL = "https://github.com/sadouninc/Sado-Investment-Lab/actions/workflows/risk-preflight-what-if.yml"
WHAT_IF_RUNS_API = "https://api.github.com/repos/sadouninc/Sado-Investment-Lab/actions/workflows/risk-preflight-what-if.yml/runs?event=workflow_dispatch&per_page=20"


def interactive_panel() -> str:
    return f"""
## ▶ 実際にWhat-ifを確認する

<div class="content-card" id="what-if-runner" data-runs-api="{WHAT_IF_RUNS_API}">
  <strong>このページで一意なRequest IDを作り、そのrequestだけを追跡します。</strong>
  <span>PagesにはGitHub tokenを置かないため、認証が必要な実行操作はGitHub Actionsで行います。Request IDを貼り付けて実行後、このページへ戻ると対応runだけを追跡できます。</span>

  <div class="what-if-request-box">
    <div>
      <span class="what-if-label">Request ID</span>
      <code id="what-if-request-id">未発行</code>
    </div>
    <div class="codex-action-row">
      <button type="button" class="codex-action codex-action--secondary" id="what-if-generate">Request IDを発行</button>
      <button type="button" class="codex-action codex-action--secondary" id="what-if-copy" disabled>コピー</button>
    </div>
  </div>

  <div class="codex-action-row">
    <a class="codex-action codex-action--primary" href="{WHAT_IF_WORKFLOW_URL}" target="_blank" rel="noopener">GitHub ActionsでWhat-ifを実行</a>
    <button type="button" class="codex-action codex-action--secondary" id="what-if-track" disabled>このRequestを追跡</button>
  </div>

  <div class="what-if-state" aria-live="polite">
    <span class="what-if-label">実行状態</span>
    <strong id="what-if-state-code">NOT_STARTED</strong>
    <span id="what-if-state-message">Request IDを発行してください。</span>
    <a id="what-if-run-link" href="#" target="_blank" rel="noopener" hidden>対応するGitHub runを開く</a>
  </div>
</div>

### iPhoneでの確認手順

1. **Request IDを発行**してコピーする。
2. **GitHub ActionsでWhat-ifを実行**を開き、`request_id`へ貼り付ける。続けて銘柄コード / BUY・SELL / 株数 / 価格を入力して `Run workflow` を押す。
3. このページへ戻り、**このRequestを追跡**を押す。60秒間隔で同じRequest IDのrunだけを確認する。
4. `CALCULATED`になったら、表示された**対応するGitHub run**を開き、Step Summaryでcanonical結果を確認する。

`QUEUED / RUNNING / CALCULATED / FAILED / EXPIRED / RATE_LIMITED / CLIENT_ERROR` は観測状態です。`CALCULATED`は「計算runが正常終了した」という意味で、投資判断の`PASS`や買い推奨を意味しません。`FAILED`は対応run自体の失敗、`RATE_LIMITED`はGitHub APIの取得制限、`CLIENT_ERROR`はnetwork/API取得失敗として分離します。

`SELL` はCASH / MARGINの口座文脈を明示できない場合、信用新規売り等を推測せず `NOT_JUDGABLE` になります。PF評価額・現金余力を入力しなければ、その項目は`UNKNOWN`のままです。

> **重要:** これは注文ではありません。Portfolio、Decision Journal、Execution Intentを変更せず、発注も行いません。Request IDはこのページのメモリ上だけに保持し、reload後にCanonical Decisionとして復元しません。
>
> **認証境界:** Pagesにはtoken / secretを保存しません。実行はGitHub認証済みActions、状態確認は公開run metadataのみを利用します。result JSONをPages内へ直接取得する機能はこのsliceでは実装せず、対応runへの正確な到達までを担当します。
>
> **実装境界:** 計算は既存 #307 / #233 Python calculatorだけを実行します。Pages内に別の計算式を持ちません。

<script>
(() => {{
  const root = document.getElementById('what-if-runner');
  if (!root) return;

  const generateButton = document.getElementById('what-if-generate');
  const copyButton = document.getElementById('what-if-copy');
  const trackButton = document.getElementById('what-if-track');
  const requestCode = document.getElementById('what-if-request-id');
  const stateCode = document.getElementById('what-if-state-code');
  const stateMessage = document.getElementById('what-if-state-message');
  const runLink = document.getElementById('what-if-run-link');
  const runsApi = root.dataset.runsApi;

  const POLL_MS = 60000;
  const EXPIRE_MS = 10 * 60 * 1000;
  let requestId = null;
  let createdAt = null;
  let timer = null;

  const stateText = {{
    NOT_STARTED: 'Request IDを発行してください。',
    QUEUED: '対応runの開始を待っています。GitHub Actionsで同じRequest IDを指定したか確認してください。',
    RUNNING: '対応するWhat-if runを実行中です。',
    CALCULATED: '対応runは正常終了しました。これは投資判断PASSの意味ではありません。Step Summaryで結果を確認してください。',
    FAILED: '対応run自体が失敗または取消になりました。GitHub runを確認してください。',
    EXPIRED: '10分以内に対応runを確認できませんでした。Request IDを作り直して再試行してください。',
    RATE_LIMITED: 'GitHub APIの取得制限に達したため追跡を停止しました。What-if計算失敗ではありません。',
    CLIENT_ERROR: 'GitHub APIの状態取得に失敗しました。What-if計算失敗ではありません。'
  }};

  function setState(code, run) {{
    stateCode.textContent = code;
    stateMessage.textContent = stateText[code] || '状態を判定できません。';
    if (run && run.html_url) {{
      runLink.href = run.html_url;
      runLink.hidden = false;
    }} else {{
      runLink.hidden = true;
      runLink.removeAttribute('href');
    }}
  }}

  function makeRequestId() {{
    const random = (globalThis.crypto && crypto.randomUUID)
      ? crypto.randomUUID().replaceAll('-', '').slice(0, 12)
      : Math.random().toString(16).slice(2, 14);
    return `whatif-ui-${{Date.now()}}-${{random}}`;
  }}

  function stopPolling() {{
    if (timer) window.clearTimeout(timer);
    timer = null;
  }}

  function mapRunState(run) {{
    const status = String(run.status || '').toLowerCase();
    const conclusion = String(run.conclusion || '').toLowerCase();
    if (['queued', 'waiting', 'pending', 'requested'].includes(status)) return 'QUEUED';
    if (status === 'in_progress') return 'RUNNING';
    if (status === 'completed' && conclusion === 'success') return 'CALCULATED';
    if (status === 'completed') return 'FAILED';
    return 'RUNNING';
  }}

  async function poll() {{
    if (!requestId || !createdAt) return;
    if (Date.now() - createdAt > EXPIRE_MS) {{
      stopPolling();
      setState('EXPIRED');
      trackButton.disabled = false;
      return;
    }}

    try {{
      const response = await fetch(runsApi, {{
        method: 'GET',
        headers: {{ 'Accept': 'application/vnd.github+json' }},
        cache: 'no-store'
      }});
      const remaining = Number(response.headers.get('X-RateLimit-Remaining'));
      const resetEpoch = Number(response.headers.get('X-RateLimit-Reset'));
      if (response.status === 403 || response.status === 429 || Number.isFinite(remaining) && remaining <= 1) {{
        stopPolling();
        setState('RATE_LIMITED');
        trackButton.disabled = false;
        if (Number.isFinite(resetEpoch) && resetEpoch > 0) {{
          const resetAt = new Date(resetEpoch * 1000).toLocaleTimeString();
          stateMessage.textContent += ` 再取得目安: ${{resetAt}}`;
        }}
        return;
      }}
      if (!response.ok) throw new Error(`GitHub API ${{response.status}}`);
      const payload = await response.json();
      const prefix = `What-if ${{requestId}} ·`;
      const matchingRuns = (payload.workflow_runs || []).filter((run) =>
        typeof run.display_title === 'string' && run.display_title.startsWith(prefix)
      );
      matchingRuns.sort((a, b) => Number(b.id || 0) - Number(a.id || 0));
      const run = matchingRuns[0];

      if (!run) {{
        setState('QUEUED');
      }} else {{
        const code = mapRunState(run);
        setState(code, run);
        if (code === 'CALCULATED' || code === 'FAILED') {{
          stopPolling();
          trackButton.disabled = false;
          return;
        }}
      }}
    }} catch (error) {{
      stopPolling();
      setState('CLIENT_ERROR');
      trackButton.disabled = false;
      stateMessage.textContent = `状態取得に失敗しました: ${{error.message}}。What-if計算失敗や投資上のPASSとして扱いません。`;
      return;
    }}

    timer = window.setTimeout(poll, POLL_MS);
  }}

  generateButton.addEventListener('click', () => {{
    stopPolling();
    requestId = makeRequestId();
    createdAt = Date.now();
    requestCode.textContent = requestId;
    copyButton.disabled = false;
    trackButton.disabled = false;
    setState('QUEUED');
  }});

  copyButton.addEventListener('click', async () => {{
    if (!requestId) return;
    try {{
      await navigator.clipboard.writeText(requestId);
      copyButton.textContent = 'コピー済み';
      window.setTimeout(() => {{ copyButton.textContent = 'コピー'; }}, 1500);
    }} catch (_) {{
      copyButton.textContent = '長押しでコピー';
    }}
  }});

  trackButton.addEventListener('click', () => {{
    if (!requestId) return;
    stopPolling();
    trackButton.disabled = true;
    setState('QUEUED');
    poll();
  }});

  setState('NOT_STARTED');
}})();
</script>
"""


def page_content() -> str:
    return f"""---
layout: site
title: 売買前のポートフォリオ確認
description: 新規売買前に集中度・現金余力・エクスポージャーとデータ不足を確認する
permalink: /risk-preflight/
---

<p class="breadcrumb"><a href="{{{{ '/' | relative_url }}}}">Home</a> / 売買前のポートフォリオ確認</p>

# 🛡️ 売買前のポートフォリオ確認

新規BUY / ADDなどを検討するとき、銘柄単体の魅力度とは別に、**ポートフォリオ全体の資本リスク**を確認するための画面です。

> この画面は売買指示を生成しません。最終判断はオーナーが行います。

{interactive_panel()}

## 確認する内容

<div class="content-grid">
  <div class="content-card"><strong>個別銘柄の集中度</strong><span>現在と売買後のposition weightを比較します。</span></div>
  <div class="content-card"><strong>Theme / Sector集中度</strong><span>canonical membershipがある場合だけbefore / afterを表示し、不明はUNKNOWNのまま保持します。</span></div>
  <div class="content-card"><strong>現金余力</strong><span>明示されたcashだけを使い、証券会社の買付余力を推測しません。</span></div>
  <div class="content-card"><strong>Gross / Margin Exposure</strong><span>利用可能なcanonical情報だけを表示し、欠損を0扱いしません。</span></div>
</div>

## 判定の読み方

| 表示 | 意味 |
|---|---|
| `PASS` | 定義済みruleの範囲内 |
| `WARN` | 定義済みsoft thresholdへ接近 |
| `BLOCK_REVIEW` | Owner-defined hard rule超過。オーナー再確認が必要 |
| `UNKNOWN` | 必要データまたはruleが不足。PASS扱いしない |

## Decision OSへの接続

- **#133 Decision Journal** — 判断時点の `risk_preflight_snapshot_ref` をsystem snapshotへ保存できる。
- **#141 Investment Review Engine** — `WARN / BLOCK_REVIEW / UNKNOWN` を明示的なreview reason contextとして渡せる。ここからBUY / SELLは生成しない。
- **#186 Opportunity Cost Ledger** — 売買後cash / gross / margin / position contextと、defined rule block・unknown constraintを参照できる。

`PASS`だけを根拠に「資金的に実行可能」と断定しません。SBI等のbrokerage buying powerがcanonicalに検証されていない場合、feasibilityは`UNKNOWN`です。

## 表示イメージ

```text
ダイヘン / BUY

現在の銘柄金額       80万円
売買後の銘柄金額    180万円
売買後の銘柄比率      18%

AI・半導体テーマ
現在                 38%
売買後               46%

現金余力
現在                200万円
売買後              100万円

判定
✓ 個別銘柄ルール: PASS
? 最低現金ルール: UNKNOWN（ルール未設定）

これは売買指示ではありません。
```

## Authority / Safety

具体的な上限値は `OWNER_DEFINED` / `FRAMEWORK_DEFINED` のみ評価します。`UNSET`、stale、missing、unknown membershipは安全側に`UNKNOWN`として残し、AI独自thresholdや推測値で補完しません。
"""


def build() -> None:
    target = SITE / "risk-preflight" / "index.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page_content().rstrip() + "\n", encoding="utf-8")

    home = SITE / "index.md"
    if home.is_file():
        text = home.read_text(encoding="utf-8")
        marker = "## 🛡️ 売買前のポートフォリオ確認"
        if marker not in text:
            text += (
                "\n\n---\n\n"
                f"{marker}\n\n"
                "新規売買前に、集中度・現金余力・Gross / Margin Exposure・データ不足を確認します。\n\n"
                "[売買前のポートフォリオ確認を開く]({{ '/risk-preflight/' | relative_url }})\n"
            )
            home.write_text(text, encoding="utf-8")


def verify_daihen_publish_contract() -> None:
    """Fail closed when the generated Pages artifact cannot expose #257."""
    home = SITE / "index.md"
    cockpit = SITE / "decision-cockpit" / "daihen" / "index.md"

    if not home.is_file():
        raise RuntimeError("#257 publish contract: site-src/index.md is missing")
    if not cockpit.is_file():
        raise RuntimeError("#257 publish contract: Daihen cockpit page is missing")

    home_text = home.read_text(encoding="utf-8")
    cockpit_text = cockpit.read_text(encoding="utf-8")
    required_home = (
        "ダイヘン 投資判断コックピット",
        "/decision-cockpit/daihen/",
    )
    for value in required_home:
        if value not in home_text:
            raise RuntimeError(f"#257 publish contract: Home entry missing: {value}")

    if "permalink: /decision-cockpit/daihen/" not in cockpit_text:
        raise RuntimeError("#257 publish contract: cockpit permalink is missing")
    if "この画面は売買指示を生成しません" not in cockpit_text:
        raise RuntimeError("#257 publish contract: cockpit safety notice is missing")


if __name__ == "__main__":
    build()

    # #257 PR-B/PR-C are presentation-only layers. Keep one stable workflow
    # entry point while generating and then safely enhancing the Cockpit.
    from build_daihen_cockpit import build as build_daihen_cockpit
    from build_daihen_cockpit import load_model as load_daihen_model
    from enhance_daihen_cockpit_links import enhance_file as enhance_daihen_cockpit_links
    from enrich_home_focus import enrich_home_focus
    from enrich_home_today import enrich_home_from_morning

    build_daihen_cockpit()
    enhance_daihen_cockpit_links(load_daihen_model())
    enrich_home_from_morning()
    enrich_home_focus()
    verify_daihen_publish_contract()
