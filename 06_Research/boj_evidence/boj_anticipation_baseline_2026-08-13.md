# BOJ Anticipation Window — Baseline Snapshot

担当: 🌅アサヒ  
種別: Research / Policy Intelligence / Market Reaction  
Issue: #512  
PR: #534  
Collection as of: 2026-08-14 00:51 JST  
Freshest fully aligned window: VERIFIED_2026-08-07_TO_2026-08-10

## Purpose
2026年9月BOJ会合へ向けたAnticipation Windowの最初の比較基準を保存する。

重要: Web上で同一basisまで検証できた5銘柄・TOPIX・Growth250の共通最新windowは2026-08-07→2026-08-10。8/12〜8/13の5銘柄完全セットはfresh source未到達のため推測補完しない。

## Policy context
- BOJ Early Warning state: ORANGE
- 9月利上げ観測は高水準だが、市場全体の本格的な退避は未確認
- 本Snapshotは「利上げ観測が強いが株式市場がまだ崩れていない」局面のbaseline

## Verified benchmark closes

| Benchmark | 2026-08-07 | 2026-08-10 | Return |
|---|---:|---:|---:|
| TOPIX | 4,074.93 | 4,100.61 | +0.63% |
| Growth250 | 724.09 | 737.17 | +1.81% |

Growth250の8/7値は、8/10終値737.17・前日比+13.08から直前営業日8/7終値724.09を復元。週末を挟むため同一close-to-close basis。

## Initial aligned excess-return observation — 2026-08-07 → 2026-08-10

`excess_return = stock_return - benchmark_return`

| Security | Benchmark | 8/7 close | 8/10 close | Stock return | Benchmark return | Excess return | Initial reading |
|---|---|---:|---:|---:|---:|---:|---|
| 3778 さくらインターネット | TOPIX | 3,440 | 3,315 | -3.63% | +0.63% | **-4.26pt** | 相対弱さあり。ただし1 windowのみでBOJ帰属しない |
| 247A Aiロボティクス | Growth250 | 827 | 848 | +2.54% | +1.81% | **+0.73pt** | 相対強い。8/14決算confoundを優先 |
| 9166 GENDA | Growth250 | 661 | 661 | 0.00% | +1.81% | **-1.81pt** | 軽度相対劣後。過去BOJ eventの符号不一致からCONTEXT_SENSITIVE維持 |
| 3110 日東紡 | TOPIX | 2,825 | 2,815 | -0.35% | +0.63% | **-0.98pt** | 軽度劣後だが決算後高volatility confound |
| 4063 信越化学 | TOPIX | 6,116 | 6,286 | +2.78% | +0.63% | **+2.15pt** | 相対強い。BOJ退避シグナルなし |

## Volume context

| Security | 8/7 volume | 8/10 volume | Direction |
|---|---:|---:|---|
| 3778 さくら | 921,300 | 663,800 | DOWN |
| 247A Aiロボティクス | 340,600 | 638,100 | UP |
| 9166 GENDA | 1,261,300 | 1,513,800 | UP |
| 3110 日東紡 | 8,656,600 | 5,823,200 | DOWN |
| 4063 信越化学 | 6,430,700 | 6,667,400 | FLAT_UP |

さくらの相対下落は出来高増を伴っていないため、この1windowだけでは「BOJ織り込みによる逃避」と判定しない。GENDAは出来高増＋相対劣後だが、劣後幅は軽度で個別材料照合が必要。

## Source provenance
価格・出来高はYahoo!ファイナンス日次時系列。TOPIXはYahoo!ファイナンス時系列、Growth250はTraders Web指数データを使用。
- https://finance.yahoo.co.jp/quote/3778.T/history
- https://finance.yahoo.co.jp/quote/247A.T/history
- https://finance.yahoo.co.jp/quote/9166.T/history
- https://finance.yahoo.co.jp/quote/3110.T/history
- https://finance.yahoo.co.jp/quote/4063.T/history
- https://finance.yahoo.co.jp/quote/998405.T/history
- https://www.traders.co.jp/index/0115

## Current interpretation
この1windowだけでは銘柄別BOJ Market Reactionを恒久昇格しない。

- さくら: `WATCH_RELATIVE_WEAKNESS / LOW_CONFIDENCE`
- Aiロボティクス: `NO_BOJ_WEAKNESS / EARNINGS_CONFOUND_PENDING`
- GENDA: `CONTEXT_SENSITIVE / MILD_RELATIVE_WEAKNESS`
- 日東紡: `UNRESOLVED / EARNINGS_CONFOUND`
- 信越化学: `NO_BOJ_WEAKNESS`

重要: 現時点の初期実測では、理論上HIGHと見やすいさくらが相対劣後、信越化学は相対強い。一方AiロボティクスはGrowth250を上回っており、高duration分類だけで退避順位を作れないことを再確認した。

## Escalation rule for next transactions
銘柄別Market Reaction警戒度を上げるのは、原則として以下が2営業日以上で重なる場合のみ。
1. BOJ利上げ織込み上昇
2. 2年/5年JGB上昇または円高
3. benchmark比継続劣後
4. 出来高増加またはwindow高値からのdrawdown拡大
5. 決算/IR/M&A/sector shock等で説明できない

## Next observation transaction
fresh 8/12〜8/13または次営業日データ取得時に以下をappendする。
1. stock close / volume
2. TOPIX / Growth250同一日return
3. excess return
4. window highからのdrawdown
5. BOJ probability / 2y-5y JGB / USDJPY context
6. company/sector confound
7. 2営業日以上の相対劣後継続時のみMarket Reaction警戒度を再評価

## Safety
- stale 8/10データを8/13終値として扱わない
- benchmark未確認windowでexcess returnを推測しない
- 決算等の個別材料をBOJへ単独帰属しない
- 単一windowだけで恒久的HIGH判定しない
- BUY/SELL自動生成なし
- Issue #79 untouched
