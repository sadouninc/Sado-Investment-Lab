# #460 Market Observation Architecture — Owner-facing Visual Prototype Contract

担当: ⭐️ミナ  
種別: Product UI Design / Market Observation UX  
Status: IMPLEMENTATION_HANDOFF_READY  
Related: #460 / #444 / #49 / #320

## Goal
Market ObservationのProvider/Runtime内部設計を、そのままOwner UIへ露出せず、「何を見ているか / いつの情報か / 何が取れないか / 何に使えるか」を30秒で理解できる形へ固定する。

## Owner first-view hierarchy
1. Observation target / session slot
2. Freshness + source timestamp
3. Observation capability（LIVE / DELAYED / DAILY_ONLY / UNKNOWN）
4. Current market observation
5. Missing / unavailable fields
6. Provider / runtime details

## Pre-open semantics
- indicative_open と best_bid / best_ask を混同しない
- source timestamp と OS observed_at を分離
- 前日終値しか取れていないのにPREOPEN LIVEと表示しない
- provider unavailableをmarket negative signalへ変換しない

## 390px contract
- first viewportに `session / freshness / capability / first observation` が見える
- quote fieldsは縦stack。横長board tableを縮小しない
- unavailable fieldは `取得できません` と明示
- provider name / auth / runtime topologyはdetailsへ
- Home/Cockpitへraw order bookを持ち込まない

## Capability state
- LIVE: 現在時点に近い更新を検証済み
- DELAYED: 遅延あり
- DAILY_ONLY: 日次/前日データ中心
- UNKNOWN: freshness未検証

UIはこの状態を推測せずCanonical validation結果を表示する。

## Design Gate
### BLOCKER
- DAILY_ONLYをLIVEに見せる
- timestamp未検証なのにfresh表示
- indicative_openとbest bid/askを同じ意味に扱う
- provider failureを市場悪化へ変換
- raw provider schemaをOwner UIの主役にする
- mobileで横長板/tableのみ

### SHOULD_FIX
- session slotよりprovider名が先に出る
- missing fieldの理由が読めない
- source timestampとobserved_atが混同
- Home/Cockpitへfull market observationを複製

### NICE_TO_HAVE
- capability summary chip
- field-by-field freshness detail
- PREOPEN→POST_OPEN timeline

Result: **PASS_WITH_NOTES — provider validation成立後のOwner-facing read model実装に進行可。**

Issue #79 untouched.
Broadcast checked through: comment_id=5276694845 — VERIFIED
TEAM_STATE User Mode: ACTIVE
