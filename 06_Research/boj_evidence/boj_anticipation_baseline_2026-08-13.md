# BOJ Anticipation Window — Baseline Snapshot

担当: 🌅アサヒ  
種別: Research / Policy Intelligence / Market Reaction  
Issue: #512  
PR: #534  
Collection as of: 2026-08-13 23:46 JST  
Market-data freshness: LAST_VERIFIED_2026-08-10

## Purpose
2026年9月BOJ会合へ向けたAnticipation Windowの最初の比較基準を保存する。

重要: 2026-08-13時点でWeb取得できた5銘柄の最新確定日次時系列は2026-08-10まで。8/13終値を推測補完しない。8/11〜8/13の価格はfresh source取得後に追記する。

## Policy context
- BOJ Early Warning state: ORANGE
- 9月利上げ観測は高水準だが、市場全体の本格的な退避は未確認
- 本Snapshotは「利上げ観測が強いが株式市場がまだ崩れていない」局面のbaseline

## Last verified stock closes

| Security | Benchmark class | 2026-08-10 close | Volume | Freshness | Confound / note |
|---|---|---:|---:|---|---|
| 3778 さくらインターネット | TOPIX + growth/theme cross-check | 3,315 | 663,800 | VERIFIED_2026-08-10 | AI/DC theme catalystを別途確認 |
| 247A Aiロボティクス | Growth250 | 848 | 638,100 | VERIFIED_2026-08-10 | 8/14決算予定のため直近windowは `EARNINGS_CONFOUND` を優先 |
| 9166 GENDA | Growth250 | 661 | 1,513,800 | VERIFIED_2026-08-10 | M&A / company-specific newsを同時確認 |
| 3110 日東紡 | TOPIX | 2,815 | 5,823,200 | VERIFIED_2026-08-10 | 8月決算後の高volatilityを `EARNINGS_CONFOUND` として扱う |
| 4063 信越化学 | TOPIX | 6,286 | 6,667,400 | VERIFIED_2026-08-10 | semiconductor / FX / commodityを同時確認 |

## Source provenance
Yahoo!ファイナンス日次時系列（東証データ提供を含む）を価格・出来高のraw referenceとして使用。
- https://finance.yahoo.co.jp/quote/3778.T/history
- https://finance.yahoo.co.jp/quote/247A.T/history
- https://finance.yahoo.co.jp/quote/9166.T/history
- https://finance.yahoo.co.jp/quote/3110.T/history
- https://finance.yahoo.co.jp/quote/4063.T/history

## Benchmark state
`TOPIX` / `Growth250` の2026-08-10同一basis終値は、このrunではfreshness/series整合を満たす一次または十分信頼できるsourceまで揃っていないため `UNKNOWN`。

したがって現時点では:
- `benchmark_return = UNKNOWN`
- `excess_return = UNKNOWN`
- `boj_anticipation_beta = UNKNOWN`

を維持する。benchmark未確認でbetaを生成しない。

## Initial interpretation
このbaselineだけでは銘柄別BOJ Market Reactionを昇格しない。

- さくら: `UNRESOLVED`
- Aiロボティクス: `UNRESOLVED / EARNINGS_CONFOUND_PENDING`
- GENDA: `CONTEXT_SENSITIVE`
- 日東紡: `UNRESOLVED / EARNINGS_CONFOUND`
- 信越化学: `UNRESOLVED`

## Next observation transaction
fresh 8/13または次営業日データ取得時に以下をappendする。
1. stock close / volume
2. TOPIX / Growth250同一日return
3. excess return
4. window highからのdrawdown
5. BOJ probability / 2y-5y JGB / USDJPY context
6. company/sector confound
7. 2営業日以上の相対劣後が継続した場合のみMarket Reaction警戒度を再評価

## Safety
- stale 8/10データを8/13終値として扱わない
- benchmark UNKNOWN時にexcess returnを推測しない
- 決算等の個別材料をBOJへ単独帰属しない
- BUY/SELL自動生成なし
- Issue #79 untouched
