# AI Key Person Watch — Operational Heartbeat

担当: 🌊ナギ  
種別: Monitoring / Reliability / Observability

Issue #124 の運用監査用SSoTです。Researchニュース本文とは分離します。

## Files

- `status.json`: 最新runの監査状態。Pagesや全体最適チェックはここを参照する。

## Update contract

❤️レイの定期run終了時に、ニュース差分の有無に関係なく `status.json` を更新します。

必須項目:

- `last_run_at`: run終了時刻（ISO 8601, JST推奨）
- `last_success_at`: 最終 `OK` run時刻
- `last_status`: `OK | ERROR | UNKNOWN`
- `news_delta`: そのrunの重要差分件数
- `last_news_delta_at`: 最後に重要差分を検出したrun時刻。差分0では更新しない
- `news_persisted`: 重要差分のResearch保存が完了したか
- `persistence_status`: `COMPLETED | PENDING_PERSIST | NOT_REQUIRED`

ニュース差分0の本文は `06_Research/News/**` へ保存しません。

## Healthy / Stale

`expected_interval_minutes` は想定実行間隔、`stale_after_minutes` は停止・遅延判定の閾値です。

- `last_success_at` が存在し、現在時刻との差が `stale_after_minutes` 以下 → `HEALTHY`
- `last_success_at` がない、または閾値超過 → `STALE`
- `last_status == ERROR` は別途エラー表示対象

初期値は1時間周期に対して150分をStale閾値とします。単発の実行遅延で過剰警報にならず、2回超の欠落を検知する狙いです。

## Authority / Safety

- ChatGPT上の表示有無とは独立した監査経路とする
- ResearchニュースとOperational Heartbeatを混在させない
- 保存失敗は `PENDING_PERSIST` とし、次runで新規収集より先に再試行する
- 保存方式・生成ロジック・Pages連携を変更する場合はTEAM_RULESに従いbranch→PRを使用する
