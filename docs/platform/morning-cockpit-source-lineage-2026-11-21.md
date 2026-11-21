# #826 Morning Cockpit — source lineage and recovery gates (2026-11-21)

担当: 🪐ソラ
種別: Read-only source audit / non-conflicting documentation
対象: #826, #928
実データ移設: **対象外**。この文書は公開可能な構造・状態のみを記載し、取引原本や保有明細を含まない。

## 現行データ供給経路（mainの実コード確認）

| Morning source | Reader / producer | Canonical input | 2026-11-20 dataset status | 必要な回復条件 |
| --- | --- | --- | --- | --- |
| Portfolio | `scripts/generate_morning_dataset.py --repo-portfolio` → `scripts/morning_dataset/providers/portfolio.py` | `data/portfolio/current.json` | STALE, as_of 2026-08-08 | 既存VERIFIED基準Snapshot、基準日以降の全確定約定、別途SBIポジション明示照合による新Snapshot |
| Watchlist | `--repo-watchlist` → `scripts/morning_dataset/providers/watchlist.py` | `Current_Status.md` の `## Current Focus` | STALE, as_of 2026-08-11 | 人による最新の対象・根拠・as_ofの明示的確認。日付だけ更新しない |
| Capital | `--repo-capital` → `scripts/morning_dataset/providers/capital.py` | `data/database/history.db` の `capital_snapshots` | MISSING, table absent | 認証済み資金・買付余力等の入力と正規schema/producer経路を別途整備。テーブルだけ空作成してOKにしない |
| Events | `--repo-events` → EventsProvider | `data/events/calendar.json` | MISSING, empty coverage unverified | 対象範囲の明示的な完全性確認 |

## Portfolioの既存正規ルート

`data/portfolio/README.md` の契約:
`latest VERIFIED snapshot + confirmed SBI executions since snapshot → data/portfolio/current.json`。

- `scripts/manage_portfolio_state.py` は `scripts/portfolio_repository.py` の `build_from_repository` と `verify_state` を使用し、明示的なポジションSnapshotを照合する。
- `scripts/reconcile_weekly_sbi.py` は検証レポートとCSVのSHA256が一致することを要求し、strict import後に明示的なポジション情報と照合する。
- `data/database/investment_lab.sqlite` は `data/database/README.md` により **local-only**。現存する正規DBの所在地は未確認。空DBを本番代替にしてはいけない。
- `Current_Status.md` の「Verified transaction delta after portfolio snapshot」は特定約定の証跡であり、全ポジションの新規認証ではない。
- 週次 #928 にCSVの受領・事前検証の証跡はあるが、既存本番DB照合やPortfolioの `VERIFIED` 昇格は未完了。Sado-Investment-Data PR #1 は現在🌙ルナが単独実装担当。🪐ソラはPR #1の編集・Pushを行わない。

## なぜ古いのか（証拠と未確定事項を分離）

**確認済み:** 
- `data/portfolio/current.json` は `as_of=2026-08-08`。
- `Current_Status.md` の Current Focus は `as_of=2026-08-11`。
- 2026-11-20版 `data/generated/diagnostics/openai/optimized-morning-dataset.json` は Portfolio STALE / Watchlist STALE / Capital MISSING / Events MISSINGを明示。
- CapitalProviderはテーブル欠如時に MISSINGを返し、資金額を補完しない。

**未確認:** 
- 最後にPortfolio生成コマンドが実行された日時と失敗理由。
- 正規のprivate SQLite DBの保管場所・完全性・入力期間。
- 新しいSBIの保有・信用建玉Snapshotと信用口座余力データの整合性。
- Watchlistの最新の人間レビュー結果。
- public Pagesの実HTTP出力とmain blobの一致。

したがって「コードが壊れた」とは断定しない。現時点で実証できるのは **上流データの鮮度不足・欠損** である。

## 実装・運用の依存順

1. 🌙ルナのprivate writer/backup/recoveryは独立継続。🪐ソラは同じファイル・ロジックを変更しない。
2. 正規DB保管先と検証済みポジションSnapshotが揃った後、既存 `validate_weekly_sbi_csv.py` / `reconcile_weekly_sbi.py` の契約に従って取込・照合する。CSVの受領・検証を `VERIFIED` と誤認しない。
3. `data/portfolio/current.json` 更新は一致確認時のみ。失敗・不明なら旧情報をSTALEのまま残す。
4. Watchlistは独立した人間レビューを経て内容と日付を更新し、Portfolioのデータから推定しない。
5. Capitalは口座残高と買付余力を混同せず、認証済み入力・schema・producer・readbackの追加を別sliceで検討する。
6. Morning dataset再生成 → source_status確認 → public / diagnostics差分確認 → live Pages HTTPを確認。実データと非公開情報を公開artifactに含めない。

## 完了条件

- Source単位で `as_of`, authority, schema, verification, freshness, downstream output を追跡できる。
- STALE/MISSINGが解消するまで、Morning UIは最新と表示しない。
- 資金残高・信用建玉・約定履歴の値を推測で補完しない。
- #79 HARD DENY・Owner/安全ゲート維持。

This is a read-only lineage audit, **not** production write authorization, Owner acceptance, or proof of end-to-end deployment.
