# BOJ Market Reaction Pilot — Issue #512

担当: 🌅アサヒ  
種別: Research / Policy Intelligence / Market Reaction  
Status: PILOT / PARTIALLY_VERIFIED  
As of: 2026-08-13

## Goal

BOJ Early Warningを、企業財務・valuation上の理論的な金利感応度だけでなく、**実際にBOJイベントを市場参加者がどう売買したか**まで含めて判定できるようにする。

本PilotはIssue #512へ以下の追加レイヤーを実装するための最初のResearch artifact。

1. `fundamental_rate_sensitivity`
2. `boj_market_reaction_sensitivity`
3. `boj_anticipation_beta`
4. `positioning_follower_risk`

売買判断は自動化しない。最終判断はOwner Authority。

---

## Event calendar v0

### Event A — 2026-06-16
- BOJ policy event: 利上げ
- Policy rate: 0.75% → 1.00%
- Authority: Bank of Japan monetary-policy decision
- Event type: `RATE_HIKE`

### Event B — 2025-12-19
- BOJ policy event: 利上げ
- Policy rate: 0.50% → 0.75%
- Authority: Bank of Japan monetary-policy decision
- Event type: `RATE_HIKE`

今後、利上げ実施日だけでなく、Summary of Opinions、総裁発言、利上げ織込み急上昇windowも追加する。

---

## Pilot universe

Owner reviewで指定した初期5銘柄:

- 3778 さくらインターネット
- 247A Aiロボティクス
- 9166 GENDA
- 3110 日東紡
- 4063 信越化学

---

## Event A raw observation — 2026-06-16

価格SourceはTraders Web時系列。Event-day close-to-close returnをまず保存する。
Benchmark excess returnは次sliceでTOPIX / Growth250の同一windowを揃えて計算する。

| Security | 6/15 close | 6/16 close | Event-day return | Initial interpretation | Verification |
|---|---:|---:|---:|---|---|
| 3778 さくらインターネット | 2,850 | 2,846 | -0.1% | BOJ当日はほぼ無反応 | VERIFIED_RAW |
| 247A Aiロボティクス | 691 | 660 | -4.5% | 当日は弱いが翌日以降反発。単日でHIGH判定しない | VERIFIED_RAW |
| 9166 GENDA | 590 | 548 | -7.1% | Pilot内で最も明確な弱さ。ただし個別材料confound確認が必要 | VERIFIED_RAW |
| 3110 日東紡 | UNKNOWN | UNKNOWN | UNKNOWN | 株式分割等で時系列basis差異が見られるため現時点ではfail-closed | NEEDS_NORMALIZATION |
| 4063 信越化学 | 7,564 | 7,454 | -1.5% | 限定的な下落。市場全体対比が必要 | VERIFIED_RAW |

### Post-event observations

- さくら: 6/16 2,846 → 6/19 3,150。利上げ後に上昇。
- Aiロボティクス: 6/16 660 → 6/17 707 → 6/19 753。Event-day下落をそのままBOJ sensitivityと解釈できない。
- GENDA: 6/16 548 → 6/19 528。一旦6/17に反発後、再び弱含み。
- 信越化学: 6/16 7,454 → 6/19 7,310。緩やかな弱さ。
- 日東紡: split-adjustment / historical price basisを正規化するまでUNKNOWN。

---

## Interpretation rule

### Important distinction

```text
Fundamental Rate Sensitivity != Market Reaction Sensitivity
```

例:
- 借入やvaluation duration上は金利に弱くても、実際の株主がAI・政策・個別成長材料を優先すればBOJ Eventで売られない可能性がある。
- 財務への直接影響が小さくても、市場参加者が「金利上昇に弱い株」と認識して繰り返し売るならMarket Reaction Sensitivityは高くなり得る。

### Event contamination

以下が同windowにある場合は `confounded=true` とする。
- 決算 / guidance
- 増資 / M&A
- 大型受注
- index rebalance
- stock split / corporate action
- sector-specific shock
- AI / semiconductor等の大型theme catalyst

因果をBOJへ単独帰属しない。

---

## Proposed canonical record

```yaml
security_code: "9166"
company_name: "GENDA"
fundamental_rate_sensitivity: UNKNOWN
market_reaction_sensitivity: UNKNOWN
boj_event_beta: UNKNOWN
boj_anticipation_beta: UNKNOWN
positioning_follower_risk: UNKNOWN
event_sample_count: 1
benchmark: TOPIX
confounded_events: []
evidence_refs: []
confidence: LOW
```

`boj_event_beta` / `boj_anticipation_beta`はraw returnをそのまま入れず、benchmark excess returnと複数event sampleを使って算定する。

---

## Provisional ranking — NOT CANONICAL

現時点でのraw observationだけから恒久分類はしない。

- GENDA: `MARKET_REACTION_WATCH` — Event Aで明確な弱さ。複数event確認が必要。
- Aiロボティクス: `VOLATILE / UNRESOLVED` — Event-day弱いが即反発。
- さくらインターネット: `LOW_OR_UNKNOWN` — Event Aではほぼ無反応。
- 信越化学: `LOW_TO_MEDIUM / UNRESOLVED` — 軽微下落。benchmark対比待ち。
- 日東紡: `UNKNOWN` — corporate-action basis正規化待ち。

この順位はPortfolio actionへ直接使用しない。

---

## Next slice

1. TOPIX / Growth250のEvent A, B raw seriesを取得
2. `stock_return - benchmark_return` をT-1/T0/T+1, T-5/T+5で保存
3. Event B (2025-12-19) を5銘柄へ追加
4. 日東紡のcorporate-action / split-adjusted basisを正規化
5. Eventごとの決算・IR・M&A等を照合し `confounded_events` を付与
6. 2026年9月会合に向け、利上げ確率上昇期間を`anticipation_window`として保存
7. サンプル不足時は `UNKNOWN` のまま維持

## Acceptance guards

- 高PERだけでMarket Reaction HIGHにしない
- 単一eventだけで恒久分類しない
- 株価下落をBOJへ自動帰属しない
- benchmark未確認時はbetaを生成しない
- corporate action未正規化価格からreturnを作らない
- BUY/SELLを自動生成しない
- Issue #79 untouched

Refs: #512
