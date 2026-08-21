# Architecture Note: Market Observation Contract v1

**担当**: 🤖 Jules
**種別**: Product Architecture / Contract Documentation
**Refs**: #460 (#444, #59, #49, #349)

---

## 1. 概要 (Overview)

Sado Investment OSの心臓部となる **Market Observation Contract v1** は、「何を観測するか（Canonical Contract）」と「どこから取得するか（Provider Adapter）」を完全に分離し、特に寄付き前の寄り前時間帯（8:00–9:00 JST）における市場予想（Expectation）を安全かつ決定論的に観測するための共通データ契約仕様です。

本アーキテクチャノートは、オーナー（👑サド）およびチームが観測モデルの概念と振る舞いを日本語で直感的に理解できるように記述した文書です。

---

## 2. 観測フィールドの標準定義 (Canonical Field Vocabulary)

| フィールド名 | 型 | 意味・市場的意義 |
| --- | --- | --- |
| `best_bid` | Object `{price, size}` | **最良買い気配 (Best Bid)**: 現時点で板上に存在する最も高い買い注文の価格と数量。 |
| `best_ask` | Object `{price, size}` | **最良売り気配 (Best Ask)**: 現時点で板上に存在する最も安い売り注文の価格と数量。 |
| `indicative_open` | Object `{price, special_quote_flag}` | **寄り前予想気配 (Indicative Open)**: 合致計算（板寄せ）に基づき、寄付き時点で約定すると予想される気配価格および特別気配フラグ（特別買い気配/特別売り気配など）。 |
| `last_price` | Float | **直近約定価格**: 市場で最後に約定した価格（ザラ場中または前日終値）。 |
| `previous_close` | Float | **前日終値**: 基準となる前営業日の確定終値。 |
| `observed_at` | String (ISO 8601) | **OS観測時刻**: Sado Investment OSがデータを記録・生成したシステム時刻。 |
| `source_timestamp` | String (ISO 8601) | **Providerデータ生成時刻**: データ提供元（Provider）が気配・株価を発行した刻印。 |

---

## 3. 重要原則とセマンティクスの厳格な区別 (Invariants)

1. **気配値と予想気配の混同・補完禁止**
   - `best_bid`（買気配）、`best_ask`（売気配）、`indicative_open`（寄り前気配）は独立した市場概念です。
   - 一方のデータが欠落している場合でも、他方の値から推測・補完（コピー）してはなりません。
2. **タイムスタンプの独立分離**
   - OSの記録時刻 `observed_at` と Providerの刻印 `source_timestamp` は独立して管理・検証されます。
   - これにより、Providerのデータが過去の遅延データ（Stale Data）であるか、freshなリアルタイムデータであるかを正確に判定します。
3. **欠損・非対応時における Fail-closed 挙動 (`PARTIAL` / `UNKNOWN`)**
   - 寄り前時間帯にデータプロバイダから板や予想気配が得られない場合、OSは存在しないデータやダミーLIVE値を捏造（合成）しません。
   - 観測ステータスを `PARTIAL` または `UNKNOWN` として不完全状態を明示し、安全に処理を落とします（Fail Closed）。
4. **決定論的検証 (Deterministic Validation)**
   - 同一の入力データに対しては、常に同一の検証結果 (`ValidationResult`) が出力されます。

---

## 4. 観測ケイパビリティ・ステータス (Observation Status)

- **`FULL`**: 必要な全観測項目（気配・予想気配・約定値等）が正常に取得できている状態。
- **`PARTIAL`**: 一部フィールド（例: 寄り前で `indicative_open` のみ取得可能、板情報なし）が欠落している状態。
- **`UNKNOWN`**: プロバイダの応答が不完全で、状態が未確定な状態。
- **`UNAVAILABLE`**: ヘッダ不正、タイムスタンプ違反、データの不当な合成・推測が検出され、利用不可な状態。

---

## 5. 既存コードおよび将来プロバイダとの関係

- **`MarketProvider` 権限の維持**: 既存の `scripts/morning_dataset/providers/market.py` やデータ構造を壊さず、上流の共通契約（Contract）として位置づけます。
- **プロバイダ独立性**: 将来 `kabuステーション API` やその他のプロバイダアダプタを追加・変更した場合でも、Downstreamの投資判断ロジックやデータ蓄積形式（Snapshot / Delta）に影響を与えません。
