from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site-src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def page_content() -> str:
    return """---
layout: site
title: 売買前のポートフォリオ確認
description: 新規売買前に集中度・現金余力・エクスポージャーとデータ不足を確認する
permalink: /risk-preflight/
---

<p class="breadcrumb"><a href="{{ '/' | relative_url }}">Home</a> / 売買前のポートフォリオ確認</p>

# 🛡️ 売買前のポートフォリオ確認

新規BUY / ADDなどを検討するとき、銘柄単体の魅力度とは別に、**ポートフォリオ全体の資本リスク**を確認するための画面です。

> この画面は売買指示を生成しません。最終判断はオーナーが行います。

## What-ifを開始

売買方向・株数・価格を入力して、Canonical Portfolioを変更せずに仮想約定後の影響を確認できます。計算はGitHub Actions上のcanonical #233/#307 calculatorを使い、Pages側に別の計算式を持ちません。

<a class="nav-card" href="https://github.com/sadouninc/Sado-Investment-Lab/actions/workflows/risk-preflight-what-if.yml" target="_blank" rel="noopener">
  <strong>What-if入力を開く →</strong>
  <span>GitHubで認証した状態で「Run workflow」から BUY / SELL・株数・価格を入力します。これは注文ではありません。</span>
</a>

<details class="source-journal">
  <summary>実行後の結果を見る手順</summary>
  <ol>
    <li>実行した <code>Risk Preflight What-if</code> runを開きます。</li>
    <li>Step Summaryで判定を確認します。</li>
    <li>必要なら <code>risk-preflight-what-if-&lt;run_id&gt;</code> artifactの <code>result.json</code> を確認します。</li>
  </ol>
  <p><code>QUEUED / RUNNING</code> 中やartifact未生成は計算完了として扱いません。結果は7日で期限切れになり、Decision / Execution Intentへ自動保存されません。</p>
</details>

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
