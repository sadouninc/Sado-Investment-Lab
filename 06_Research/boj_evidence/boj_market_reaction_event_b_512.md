# BOJ Market Reaction Event B — 2025-12-19

担当: 🌅アサヒ
種別: Research / Policy Intelligence / Market Reaction
Refs: #512

## Event
- BOJ rate hike: 0.50% → 0.75%
- Broad market: TOPIX +0.80%, Growth250 +1.72%
- Context: widely anticipated hike; broad market rose

## Event-day benchmark-relative reaction

| Security | Benchmark | Stock return | Benchmark return | Excess |
|---|---|---:|---:|---:|
| 3778 さくらインターネット | TOPIX | +0.7% | +0.80% | 約-0.1pt |
| 247A Aiロボティクス | Growth250 | +8.9% | +1.72% | 約+7.2pt |
| 9166 GENDA | Growth250 | +4.7% | +1.72% | 約+3.0pt |
| 3110 日東紡 | TOPIX | UNKNOWN | +0.80% | UNKNOWN |
| 4063 信越化学 | TOPIX | 0.0% | +0.80% | 約-0.8pt |

## Key finding
GENDAは2026-06-16利上げでGrowth250対比約-7.3ptだった一方、2025-12-19は約+3.0pt。反応符号が逆であり、単純な「利上げに弱い株」分類は棄却する。

AiロボティクスもEvent Bでは大幅超過上昇。BOJより個別材料・テーマ・需給の寄与を切り分ける必要がある。

さくらはEvent A/Bともbenchmark近辺で、現時点ではBOJ固有感応度はLOW_OR_UNKNOWN。

信越化学は2イベントともbenchmarkをやや下回るが、大幅反応ではないためLOW_TO_MEDIUM / UNRESOLVED。

日東紡は価格basis / history gapの正規化までUNKNOWN。

## Guard
- 単一eventで恒久betaを作らない
- event contextを保存する
- confounded eventをBOJへ単独帰属しない
- BUY/SELL自動生成なし
- Issue #79 untouched
