from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site-src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


WHAT_IF_WORKFLOW_URL = "https://github.com/sadouninc/Sado-Investment-Lab/actions/workflows/risk-preflight-what-if.yml"


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

## ▶ 実際にWhat-ifを確認する

<div class="content-card">
  <strong>売買内容を入力すると、注文前のPF影響をCanonical計算で確認できます。</strong>
  <span>GitHubへログインした状態で専用Actionsを開き、<code>Run workflow</code> から銘柄コード・BUY/SELL・株数・価格を入力します。ダイヘンは <code>6622</code>、BUY 100株なら action=<code>BUY</code> / quantity=<code>100</code> です。</span>
  <span>計算は既存 #307 / #233 Python calculatorだけを実行します。Pages内に別の計算式を持ちません。</span>
  <div class="codex-action-row">
    <a class="codex-action codex-action--primary" href="{WHAT_IF_WORKFLOW_URL}">What-if入力を開始する</a>
    <a class="codex-action codex-action--secondary" href="{WHAT_IF_WORKFLOW_URL}">直近の実行結果を見る</a>
  </div>
</div>

### iPhoneでの確認手順

1. **What-if入力を開始する**を開く。
2. GitHub Actionsの `Run workflow` を押し、銘柄コード / BUY・SELL / 株数 / 価格を入力する。
3. 実行後、同じ画面の最新runを開き、**Step Summary**で結果を確認する。必要なら7日間保持されるresult artifactも確認する。

`SELL` はCASH / MARGINの口座文脈を明示できない場合、信用新規売り等を推測せず `NOT_JUDGABLE` になります。PF評価額・現金余力を入力しなければ、その項目は`UNKNOWN`のままです。

> **重要:** これは注文ではありません。Portfolio、Decision Journal、Execution Intentを変更せず、発注も行いません。GitHub認証済みActionsをruntime境界として使うため、Pagesへtokenやsecretを埋め込みません。

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
