# Fair PER Evidence Contract v1 (Issue #626)

担当: 🤖カイ
種別: Framework Design / Research Handoff (Implementation)
関連Issue: #626, #403, #308, #312, #402, #633

## 目的

`PERが低い = 割安` という単純判定を避け、**良い会社**と**良い買値**を分離するため、Sony (#403) で構築中の適正PER推定を、全銘柄で再利用できる machine-readable な Evidence Contract として昇格させる。

実装は `scripts/fair_per_evidence.py`、テストは `tests/test_fair_per_evidence.py`。

**この Contract は Fair PER の数値を自動決定しない。** Entry Zone、BUY/SELL/HOLD、投資哲学、銘柄固有ロジックのいずれも生成しない。あくまで **10 factorの Evidence を保持し、Range + Confidence + freshness を fail-closed に検証するための研究境界** である。

## Fair PER の共通定義

```
Fair PER = f(
  Historical valuation, EPS growth, Earnings quality, Business mix,
  Cyclicality/Risk, Capital allocation, Peer valuation,
  Optionality evidence, Macro discount rate, Market expectation,
)
```

- Fair PERは単一の点推定として保持しない。原則として **Fair PER Range + Confidence + Evidence freshness** で保持する（`FairPERRange`）。
- 過去平均PERはそのままFair PERにしない。過去PERは `HistoricalValuationAnchor`（アンカー）として別概念で保持し、Fair PER Rangeへ機械的に代入しない。

## 10-Factor Evidence Schema

`FactorEvidence` (`scripts/fair_per_evidence.py`) が1 factorぶんのEvidence記録単位。

| Field | 内容 |
| --- | --- |
| `factor` | 10 factorのいずれか（`REQUIRED_FACTORS`） |
| `summary` | Evidence要約 |
| `as_of` | Evidenceの日付 |
| `confidence` | `LOW` / `MEDIUM` / `HIGH` |
| `source_ref` | 一次情報参照 |
| `stage` | Optionality factorのみ必須。Evidence Stage（下記） |
| `realized_revenue` / `realized_profit` | Optionality factorが `FINANCIAL_REALIZATION` の場合のみ設定可 |
| `excluded_periods` | 除外期間の記録 |

`FairPEREvidenceRecord.factors` は10 factorすべてが揃っていないと構築時に fail-closed する（`FairPEREvidenceError`）。

### 10 Factors

1. `historical_valuation` — 自社過去PERと利益局面
2. `eps_growth` — 成長率・revision・持続性
3. `earnings_quality` — margin / recurring性 / FCF conversion
4. `business_mix` — 高収益・継続収益segment比率
5. `cyclicality_risk` — 景気・為替・商品cycle・災害・規制
6. `capital_allocation` — buyback / dilution / ROE / ROIC / balance sheet
7. `peer_valuation` — Peer / market relative valuation
8. `optionality` — 将来テーマ。Evidence Stageで管理し、未実現利益をEPSへ混ぜない
9. `macro_discount_rate` — 金利 / ERP
10. `market_expectation` — implied PER / implied earnings

## Evidence Stage: Intent / Operating Evidence / Financial Realization

Optionality evidence（factor 8）は次の3段のladderで管理する。

```
INTENT → OPERATING_EVIDENCE → FINANCIAL_REALIZATION
(announcement)   (design win / order)   (revenue / profit)
```

- `FactorEvidence` は `stage == FINANCIAL_REALIZATION` の場合のみ `realized_revenue` / `realized_profit` を保持できる。それ以外のstageでこれらを設定するとfail-closedする。
- `FINANCIAL_REALIZATION` を宣言するには `realized_revenue` または `realized_profit` のいずれかが必須。**Intentの宣言だけでFinancial Realizationへ昇格することはできない。**
- `promote_evidence_stage()` はladderを1段ずつしか進められない。`INTENT → FINANCIAL_REALIZATION` のような一足飛びの昇格は、たとえ realized metric を渡しても拒否する。
- `EPSScenario.optionality_included=True` を宣言する場合、Optionality factorのstageが `FINANCIAL_REALIZATION` でなければ `FairPEREvidenceRecord` の構築時にfail-closedする。これにより「Physical AI等のoptionalityを未実現のままEPSへ加算しない」ガードレールを機械的に強制する。

## Range + Confidence Contract

- `FairPERRange(fair_per_low, fair_per_high, confidence)` — `confidence` は `LOW` / `MEDIUM` / `HIGH` のいずれかのみ許可。`fair_per_low <= fair_per_high` を強制。
- `HistoricalValuationAnchor` は過去PERの機械的な単純平均を明示的に拒否する:
  - 異常年 (`is_abnormal_year`) と赤字年 (`is_loss_year`) は集計対象から除外し、除外理由 (`exclusion_reason`) を必須にする。
  - 会計basisが混在する期間を一括平均しない。含める期間の会計basisが1つに揃っていない場合はfail-closedする。
  - 使用可能な期間が1つも残らない場合はfail-closedする。

## Bear / Base / Bull EPS × Valuation Matrix Contract

- `EPSScenario(bear_eps, base_eps, bull_eps, scenario_as_of, optionality_included)` — 各シナリオEPSは `UNKNOWN` の場合 `None`（架空の代入値を作らない）。
- `scenario_as_of` は `price_as_of` と独立したauthorityとして保持する。新鮮な価格が古い/欠落したシナリオを自動的に格上げしない。

## Implied Expectation（逆算）Contract

`compute_implied_expectation(canonical_price, eps_scenario, fair_per_range)` が次を計算する。

- `current_per` = 現在価格 / Base EPS（Base EPSが正の場合のみ）
- `implied_scenario` = 現在価格が最も近いBear/Base/Bullシナリオ
- `expectation_gap_to_low` / `expectation_gap_to_high` = `current_per` とFair PER Rangeとの乖離

**Canonical priceが利用不可の場合、この関数は全フィールドを `None`（UNKNOWN相当）で返す。** stale価格や前期価格からcurrent PERを生成することはない。

## Stale / UNKNOWN / Abnormal-year Fail-closed Rule

- `CanonicalPriceGate.usable_for_current_valuation` は次すべてを満たす場合のみ `True`:
  - `identity_status == VERIFIED`
  - `freshness_status == FRESH`
  - `provider_status == OK`
  - `not_market_truth is False`
  - `price` と `price_as_of` が両方存在
- 上記いずれか一つでも欠ける場合（`FAILED` / `UNKNOWN` / `STALE` を含む）、`FairPEREvidenceRecord.current_valuation_status` は `UNKNOWN` に固定され、`current_price` / `price_as_of` / implied expectationのすべてのフィールドが `None` となる。
- 異常年・赤字年・会計basis不整合のfail-closed ruleは上記「Range + Confidence Contract」節の通り。
- この Contract は #633 の Canonical Market Data / Price Identity Gate をそのまま消費する設計であり、独自に価格を取得・代替しない。

## Authority境界（Pages / Decision Board）

- `FairPEREvidenceRecord.entry_zone` と `decision_action` は常に `None` に固定され（`dataclasses.field(init=False, default=None)`）、呼び出し側から上書きできない。
- **Pages / Decision Boardはこの Contract から独自のFair PERを生成しない。** Fair PER Range + Confidence + freshnessをそのまま参照し、Entry ZoneとBUY/SELL/HOLDは既存のOwner Authority / Decision Board authority側でのみ生成する。
- Fair PER evidence contractからEntry ZoneまたはBUY/SELL/HOLDを直接生成するコードを追加してはならない。

## Pilot 検証: Sony (#403)

`tests/test_fair_per_evidence.py` の `test_sony_403_fixture_*` / `test_sony_403_current_valuation_*` は、`docs/handoffs/sony-6758-investment-review.md` のBear/Base/Bull EPS、Fair PER Range、Canonical Price Gateの構造を10-factor schemaへlosslessに写像できることを確認する。

- FY2022/FY2023の通常年PERのみをHistorical Valuation Anchorに含め、FY2020（赤字年）とFY2024（一過性利益による異常年）は除外理由付きで除外する。
- Optionality（AI Vision / Physical AI）は `OPERATING_EVIDENCE` stageで保持し、`FINANCIAL_REALIZATION` を明示的なrealized revenue/profitなしに宣言できないことを確認する。
- Canonical priceがSTALE / UNKNOWN / FAILEDのいずれの場合も、current valuation系のフィールドがすべて `UNKNOWN` になることを確認する。

## 再現性検証: 別銘柄（Daihen, 6622）

`test_daihen_second_company_reproduces_ten_factor_schema` は、Sonyとは異なる業種・cyclicality・capital allocationプロファイルを持つDaihen (6622) でも、同じ10-factor schema・Evidence Stage・Historical Valuation Anchor・fail-closed ruleが変更なしに再現できることを確認する。

## Non-goals（この実装が行わないこと）

- Fair PER数値の自動決定engine
- Entry Zone閾値の決定
- BUY / SELL / HOLD生成
- 投資哲学またはOwner Authorityの変更
- 銘柄固有ロジックの追加
- Issue #79への変更

## Acceptance Criteria対応表

| Acceptance Criteria | 実装箇所 |
| --- | --- |
| Fair PERの共通定義をFrameworkへ記録 | 本ドキュメント「Fair PERの共通定義」節 |
| 10 factorのEvidence schemaを定義 | `FactorEvidence`, `REQUIRED_FACTORS` |
| Range + Confidence contractを定義 | `FairPERRange` |
| Bear/Base/Bull EPSとのvaluation matrix contractを定義 | `EPSScenario` |
| implied expectation逆算を定義 | `compute_implied_expectation`, `ImpliedExpectation` |
| stale / UNKNOWN / abnormal-yearのfail-closed ruleを定義 | `CanonicalPriceGate.usable_for_current_valuation`, `build_historical_valuation_anchor` |
| Sony #403でpilot検証 | `test_sony_403_*` |
| 少なくとも別銘柄1社で再現性を確認 | `test_daihen_second_company_reproduces_ten_factor_schema` |
| Pages / Decision Boardが独自Fair PERを生成しないauthority境界を明記 | 本ドキュメント「Authority境界」節、`entry_zone`/`decision_action` frozen fields |
