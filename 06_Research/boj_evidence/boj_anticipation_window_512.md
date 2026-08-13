# BOJ Anticipation Window — Issue #512

担当: 🌅アサヒ  
種別: Research / Policy Intelligence / Market Reaction  
Status: ACTIVE_WINDOW  
As of: 2026-08-13

## Goal
利上げ発表日ではなく、次回会合へ向けて市場が利上げを織り込む途中で、どの銘柄がTOPIX / Growth250に対して先に弱くなるかを観測する。

## Window contract
- `window_start`: 利上げ確率が明確に上昇し始めた日
- `window_end`: 会合前営業日または確率低下でwindow解除
- `policy_probability_start/end`: 取得可能な市場織込み
- `benchmark`: TOPIX / Growth250
- `stock_return`
- `benchmark_return`
- `excess_return = stock_return - benchmark_return`
- `drawdown_from_window_high`
- `volume_change`
- `confounded`: 決算/IR/M&A/増資/sector shock等
- `confidence`: LOW/MEDIUM/HIGH/UNKNOWN

## Pilot universe
- 3778 さくらインターネット
- 247A Aiロボティクス
- 9166 GENDA
- 3110 日東紡
- 4063 信越化学

## Interpretation
- Fundamental Rate SensitivityとAnticipation Market Reactionは別物。
- 単日下落では判定しない。
- 指数が強いのに個別株だけ継続して弱い場合をEarly Warningとして重視。
- 反応符号が過去BOJ eventと一貫しない場合は `CONTEXT_SENSITIVE`。
- corporate action未正規化はUNKNOWN。
- BUY/SELL自動生成なし。

## Current baseline
2026-08-13時点はBOJ Early Warning = ORANGE。日本株全体の本格的な退避は未確認のため、ここをAnticipation Window baselineとして保存する。

## Escalation candidate
以下が複数営業日で同時に成立した場合、銘柄別のMarket Reaction警戒度を引き上げる。
1. 利上げ織込み上昇
2. 2年/5年JGB上昇または円高
3. 株価がbenchmark比で継続劣後
4. 出来高増加またはwindow高値からのdrawdown拡大
5. 個別材料で説明できない

## Guardrails
- 高PERのみでHIGHにしない
- 1回のイベントで恒久分類しない
- confounded eventをBOJへ単独帰属しない
- sample不足はUNKNOWN
- Issue #79 untouched

Refs: #512
