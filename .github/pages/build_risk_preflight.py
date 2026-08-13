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
## ▶ 売買前のPF影響を確認する

<div class="content-card" id="what-if-runner" data-runs-api="{WHAT_IF_RUNS_API}">
  <strong>売買条件を入力し、Canonical calculatorで確認する準備をします。</strong>
  <span>BUY / SELLは入力する仮定であり推奨ではありません。入力しただけでは注文・Portfolio・Decision・Execution Intentは変更されません。</span>

  <div class="content-grid what-if-inline-grid">
    <label class="content-card">
      <span class="what-if-label">対象銘柄コード</span>
      <input id="what-if-security-code" inputmode="numeric" autocomplete="off" placeholder="例: 6622" aria-describedby="what-if-input-error">
    </label>
    <label class="content-card">
      <span class="what-if-label">売買仮定</span>
      <select id="what-if-action">
        <option value="BUY">BUY</option>
        <option value="SELL">SELL</option>
      </select>
    </label>
    <label class="content-card">
      <span class="what-if-label">数量（株）</span>
      <input id="what-if-quantity" type="number" min="1" step="1" inputmode="numeric" placeholder="100" aria-describedby="what-if-input-error">
    </label>
    <label class="content-card">
      <span class="what-if-label">価格（円）</span>
      <input id="what-if-price" type="number" min="0.01" step="any" inputmode="decimal" placeholder="現在確認できる正の価格" aria-describedby="what-if-input-error">
    </label>
    <label class="content-card">
      <span class="what-if-label">口座文脈</span>
      <select id="what-if-account-type">
        <option value="UNKNOWN">UNKNOWN（推測しない）</option>
        <option value="CASH">CASH</option>
        <option value="MARGIN">MARGIN</option>
      </select>
    </label>
  </div>

  <p id="what-if-input-error" class="what-if-state" aria-live="polite">数量と価格は正の値を入力してください。SELLで口座文脈が不明な場合はshort等へ推測せずNOT_JUDGABLEになり得ます。</p>

  <div class="codex-action-row">
    <button type="button" class="codex-action codex-action--primary" id="what-if-prepare">PF影響の確認を準備</button>
    <button type="button" class="codex-action codex-action--secondary" id="what-if-reset">条件を修正</button>
  </div>

  <div class="content-card" id="what-if-assumption" hidden>
    <span class="what-if-label">入力した仮定</span>
    <strong id="what-if-assumption-title">未入力</strong>
    <span id="what-if-assumption-detail"></span>
    <span>価格freshnessはCanonical runtime側で判定します。STALE / UNAVAILABLEを正常値として扱いません。</span>
    <strong>これは注文ではありません。</strong>
  </div>

  <div class="what-if-state" aria-live="polite">
    <span class="what-if-label">計算状態</span>
    <strong id="what-if-state-code">NOT_STARTED</strong>
    <span id="what-if-state-message">売買条件を入力してください。</span>
    <a id="what-if-run-link" href="#" target="_blank" rel="noopener" hidden>対応するGitHub runを開く</a>
  </div>

  <div class="content-card" id="what-if-result-guide" hidden>
    <strong>Portfolio Before → After</strong>
    <span>計算結果は対応runのStep Summaryに表示されます。対象銘柄PF比率 / cash / theme・sector concentration / rule・data statusを、取得できる項目だけ確認してください。</span>
    <span>UNKNOWN / RULE_UNSET / NOT_JUDGABLEはPASSへ丸めません。</span>
  </div>

  <details>
    <summary>実行・診断情報</summary>
    <div class="what-if-request-box">
      <div>
        <span class="what-if-label">Request ID</span>
        <code id="what-if-request-id">未発行</code>
      </div>
      <div class="codex-action-row">
        <button type="button" class="codex-action codex-action--secondary" id="what-if-copy" disabled>Request IDをコピー</button>
        <button type="button" class="codex-action codex-action--secondary" id="what-if-copy-inputs" disabled>入力内容をコピー</button>
      </div>
    </div>
    <div class="codex-action-row">
      <a class="codex-action codex-action--primary" href="{WHAT_IF_WORKFLOW_URL}" target="_blank" rel="noopener">GitHub Actionsで計算を実行</a>
      <button type="button" class="codex-action codex-action--secondary" id="what-if-track" disabled>このRequestを追跡</button>
    </div>
    <p>Pagesにはtoken / secretを保存しません。認証済みGitHub Actionsをon-demand runtimeとして使い、#233 / #307 Python calculatorを唯一の計算Authorityとして実行します。</p>
  </details>
</div>

### 現在の安全な実行フロー

1. このページで**対象 / BUY・SELL / 数量 / 価格 / 口座文脈**を入力して `PF影響の確認を準備`。
2. 仮定内容とRequest IDを確認し、診断情報から**GitHub Actionsで計算を実行**。同じRequest IDと入力値を指定する。
3. このページへ戻って**このRequestを追跡**。60秒間隔でexact Request IDのrunだけを確認する。
4. `CALCULATED`になったら対応runのStep Summaryで**Before → After / Rule / Data status**を確認し、必要ならこのページで条件を修正する。

inline invoke / result retrievalが認証境界を壊さず成立するまでは、Actions往復をfallbackとして維持します。request/run/telemetryは診断層に置き、通常の視線順は `売買仮定 → 計算状態 → Before/After → 警告・不足 → 条件修正` とします。

`QUEUED / RUNNING / CALCULATED / FAILED / EXPIRED / RATE_LIMITED / CLIENT_ERROR` はruntime観測状態です。`CALCULATED`は投資判断の`PASS`や買い推奨を意味しません。

> **重要:** これは注文ではありません。Portfolio、Decision Journal、Execution Intentを変更せず、発注も行いません。Request IDと入力値はこのページのメモリ上だけに保持し、reload後にCanonical Decisionとして復元しません。
>
> **認証境界:** Pagesにはtoken / secretを保存しません。result JSONを未認証clientへ公開する仕組みも追加しません。
>
> **実装境界:** 計算は既存 #307 / #233 Python calculatorだけを実行します。Pages内に別のrisk計算式を持ちません。

<script>
(() => {{
  const root = document.getElementById('what-if-runner');
  if (!root) return;

  const securityCode = document.getElementById('what-if-security-code');
  const action = document.getElementById('what-if-action');
  const quantity = document.getElementById('what-if-quantity');
  const price = document.getElementById('what-if-price');
  const accountType = document.getElementById('what-if-account-type');
  const errorBox = document.getElementById('what-if-input-error');
  const prepareButton = document.getElementById('what-if-prepare');
  const resetButton = document.getElementById('what-if-reset');
  const copyButton = document.getElementById('what-if-copy');
  const copyInputsButton = document.getElementById('what-if-copy-inputs');
  const trackButton = document.getElementById('what-if-track');
  const requestCode = document.getElementById('what-if-request-id');
  const assumption = document.getElementById('what-if-assumption');
  const assumptionTitle = document.getElementById('what-if-assumption-title');
  const assumptionDetail = document.getElementById('what-if-assumption-detail');
  const resultGuide = document.getElementById('what-if-result-guide');
  const stateCode = document.getElementById('what-if-state-code');
  const stateMessage = document.getElementById('what-if-state-message');
  const runLink = document.getElementById('what-if-run-link');
  const runsApi = root.dataset.runsApi;

  const POLL_MS = 60000;
  const EXPIRE_MS = 10 * 60 * 1000;
  let requestId = null;
  let createdAt = null;
  let timer = null;
  let preparedInput = null;

  const stateText = {{
    NOT_STARTED: '売買条件を入力してください。',
    INPUT_VALID: '入力した仮定を確認し、GitHub ActionsでCanonical計算を実行してください。',
    QUEUED: '対応runの開始を待っています。同じRequest IDと入力値を指定したか確認してください。',
    RUNNING: '対応するWhat-if runを実行中です。',
    CALCULATED: '対応runは正常終了しました。これは投資判断PASSの意味ではありません。Before/AfterとRule/Data statusを確認してください。',
    FAILED: '対応run自体が失敗または取消になりました。正常結果として扱いません。',
    EXPIRED: '10分以内に対応runを確認できませんでした。Request IDを作り直して再試行してください。',
    RATE_LIMITED: 'GitHub APIの取得制限に達したため追跡を停止しました。What-if計算失敗ではありません。',
    CLIENT_ERROR: 'GitHub APIの状態取得に失敗しました。What-if計算失敗や投資上のPASSとして扱いません。'
  }};

  function setState(code, run) {{
    stateCode.textContent = code;
    stateMessage.textContent = stateText[code] || '状態を判定できません。';
    resultGuide.hidden = code !== 'CALCULATED';
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

  function validateInput() {{
    const code = securityCode.value.trim();
    const qty = Number(quantity.value);
    const px = Number(price.value);
    if (!code) return '対象銘柄コードを入力してください。';
    if (!Number.isInteger(qty) || qty <= 0) return '数量は1以上の整数株で入力してください。';
    if (!Number.isFinite(px) || px <= 0) return '価格は0より大きい有限値を入力してください。';
    return null;
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

  prepareButton.addEventListener('click', () => {{
    const error = validateInput();
    if (error) {{
      errorBox.textContent = error;
      setState('NOT_STARTED');
      return;
    }}
    stopPolling();
    requestId = makeRequestId();
    createdAt = Date.now();
    preparedInput = {{
      security_code: securityCode.value.trim(),
      action: action.value,
      quantity: Number(quantity.value),
      price: Number(price.value),
      account_type: accountType.value
    }};
    requestCode.textContent = requestId;
    assumptionTitle.textContent = `${{preparedInput.security_code}} / ${{preparedInput.action}} / ${{preparedInput.quantity}}株`;
    assumptionDetail.textContent = `価格 ${{preparedInput.price}}円 / account ${{preparedInput.account_type}} / Request ${{requestId}}`;
    assumption.hidden = false;
    copyButton.disabled = false;
    copyInputsButton.disabled = false;
    trackButton.disabled = false;
    errorBox.textContent = '入力はVALIDです。Canonical計算はまだ実行していません。';
    setState('INPUT_VALID');
  }});

  resetButton.addEventListener('click', () => {{
    stopPolling();
    requestId = null;
    createdAt = null;
    preparedInput = null;
    requestCode.textContent = '未発行';
    assumption.hidden = true;
    resultGuide.hidden = true;
    copyButton.disabled = true;
    copyInputsButton.disabled = true;
    trackButton.disabled = true;
    errorBox.textContent = '条件を修正できます。未保存What-ifはCanonical判断として保持されません。';
    setState('NOT_STARTED');
  }});

  copyButton.addEventListener('click', async () => {{
    if (!requestId) return;
    try {{
      await navigator.clipboard.writeText(requestId);
      copyButton.textContent = 'コピー済み';
      window.setTimeout(() => {{ copyButton.textContent = 'Request IDをコピー'; }}, 1500);
    }} catch (_) {{
      copyButton.textContent = '長押しでコピー';
    }}
  }});

  copyInputsButton.addEventListener('click', async () => {{
    if (!requestId || !preparedInput) return;
    const text = [
      `request_id=${{requestId}}`,
      `security_code=${{preparedInput.security_code}}`,
      `action=${{preparedInput.action}}`,
      `quantity=${{preparedInput.quantity}}`,
      `price=${{preparedInput.price}}`,
      `account_type=${{preparedInput.account_type}}`
    ].join('\n');
    try {{
      await navigator.clipboard.writeText(text);
      copyInputsButton.textContent = '入力内容をコピー済み';
      window.setTimeout(() => {{ copyInputsButton.textContent = '入力内容をコピー'; }}, 1500);
    }} catch (_) {{
      copyInputsButton.textContent = '長押しでコピー';
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
