# 💹 Sector Rotation — TOPIX-17

**今日どのSectorへ資金が入り始めているか**を、最新確定営業日のstate変化から確認します。

## 今日のSector Rotation

<div id="sector-rotation-summary" class="notice-card" aria-live="polite">
  <strong>最新のSector状態を確認中...</strong>
</div>

<div id="sector-rotation-focus" class="content-grid" aria-live="polite"></div>

<details>
<summary><strong>この画面の見方・データ契約</strong></summary>

TOPIX-17 Sector Money Flowの**最新確定営業日**を、前回stateとの差と一緒に確認する読み取り専用ダッシュボードです。

単なる当日騰落率ランキングではありません。#112 Detectorが生成した既存state / scoreをそのまま読み、**COLD → WARMING**、**WARMING → INFLOW**のような資金流入初動と、HOT / OVERHEATEDのような既に温度が高い状態を分けて確認します。

> このページはBUY / SELLを生成しません。Detector thresholdやscoreをブラウザ側で再計算せず、Canonical `sector-history.jsonl` の値だけを表示します。

### 見方

- **前回 → 現在**: 同じSector identityの直前canonical snapshotからのstate変化です。
- **WARMING / INFLOW**: 初動候補として確認するstateです。BUY推奨ではありません。
- **HOT / OVERHEATED**: すでに温度が高い状態で、初動とは分けて扱います。
- **Breadth —**: TOPIX-17 ETF proxy contractで取得不能な場合があります。`0`とは解釈しません。
- stale / unavailable runはcanonical historyへ保存されないため、空データをCOLDとして表示しません。

### Data Contract

- Sector history: `data/generated/public/money-flow/sector-history.jsonl`
- `kind=SECTOR` のみ表示し、Theme snapshotと同一ランキングへ混ぜません。
- 最新表示は全Sectorで共通する最新 `as_of` のrowsだけを対象にします。
- `previous_state` / `state` / `flow_score` / score axesはCanonical値をそのまま表示します。
- 欠損値は `—` と表示し、0へ変換しません。

</details>

## 全Sector詳細

<div id="sector-rotation-table" class="table-scroll"></div>

<script>
(() => {
  const RAW_BASE = 'https://raw.githubusercontent.com/sadouninc/Sado-Investment-Lab/main/';
  const HISTORY_URL = RAW_BASE + 'data/generated/public/money-flow/sector-history.jsonl';
  const summary = document.getElementById('sector-rotation-summary');
  const focus = document.getElementById('sector-rotation-focus');
  const table = document.getElementById('sector-rotation-table');
  const stateOrder = ['WARMING', 'INFLOW', 'COLD', 'HOT', 'OVERHEATED'];

  const esc = (value) => String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  const num = (value, digits = 1) => value == null || value === '' || !Number.isFinite(Number(value))
    ? '—' : Number(value).toFixed(digits);

  function transition(row) {
    const previous = row.previous_state || '—';
    const current = row.state || 'UNKNOWN';
    return `${previous} → ${current}`;
  }

  function transitionClass(row) {
    const key = `${row.previous_state || ''}->${row.state || ''}`;
    if (key === 'COLD->WARMING' || key === 'WARMING->INFLOW') return '資金流入初動';
    if (row.state === 'WARMING' || row.state === 'INFLOW') return '初動候補';
    if (row.state === 'HOT' || row.state === 'OVERHEATED') return '高温';
    return '通常';
  }

  function renderFocus(rows, newest) {
    const transitions = rows.filter((row) =>
      (row.previous_state === 'COLD' && row.state === 'WARMING') ||
      (row.previous_state === 'WARMING' && row.state === 'INFLOW')
    );
    const early = rows.filter((row) => row.state === 'WARMING' || row.state === 'INFLOW');
    const selected = [...transitions, ...early.filter((row) => !transitions.includes(row))]
      .sort((a, b) => Number(b.scores?.acceleration ?? -Infinity) - Number(a.scores?.acceleration ?? -Infinity))
      .slice(0, 3);

    if (!selected.length) {
      focus.innerHTML = '<div class="content-card"><strong>新しい資金流入初動は未検出</strong><span>WARMING / INFLOWの新規候補はありません。COLDを弱気や売り推奨とは解釈しません。</span></div>';
      return;
    }

    focus.innerHTML = selected.map((row) => {
      const scores = row.scores || {};
      return `<div class="content-card">`
        + `<strong>${esc(row.name || row.id)}</strong>`
        + `<span>${esc(transition(row))} · ${esc(transitionClass(row))}</span>`
        + `<span>Acceleration ${num(scores.acceleration)} / Flow ${num(row.flow_score)}</span>`
        + `<span class="muted">As of ${esc(newest)}</span>`
        + `</div>`;
    }).join('');
  }

  function render(rows) {
    const sectors = rows.filter((row) => row && row.kind === 'SECTOR' && row.id && row.as_of);
    if (!sectors.length) {
      summary.innerHTML = '<strong>NO DATA</strong><p>Sector canonical snapshotはまだ公開されていません。空データをCOLDとして補完しません。</p>';
      focus.innerHTML = '';
      table.innerHTML = '';
      return;
    }

    const newest = sectors.map((row) => String(row.as_of)).sort().at(-1);
    const latest = sectors.filter((row) => String(row.as_of) === newest);
    const early = latest.filter((row) => row.state === 'WARMING' || row.state === 'INFLOW');
    const transitions = latest.filter((row) =>
      (row.previous_state === 'COLD' && row.state === 'WARMING') ||
      (row.previous_state === 'WARMING' && row.state === 'INFLOW')
    );

    latest.sort((a, b) => {
      const aState = stateOrder.indexOf(a.state);
      const bState = stateOrder.indexOf(b.state);
      const stateDiff = (aState < 0 ? 99 : aState) - (bState < 0 ? 99 : bState);
      if (stateDiff) return stateDiff;
      const aAccel = Number.isFinite(Number(a.scores?.acceleration)) ? Number(a.scores.acceleration) : -Infinity;
      const bAccel = Number.isFinite(Number(b.scores?.acceleration)) ? Number(b.scores.acceleration) : -Infinity;
      return bAccel - aAccel || String(a.name || a.id).localeCompare(String(b.name || b.id), 'ja');
    });

    summary.innerHTML = `<strong>${esc(newest)} の資金ローテーション</strong>`
      + `<p>TOPIX-17 ${latest.length} Sector / WARMING・INFLOW ${early.length}件 / 新しいstate遷移 ${transitions.length}件。</p>`;
    renderFocus(latest, newest);

    table.innerHTML = '<table><thead><tr>'
      + '<th>Sector</th><th>前回 → 現在</th><th>意味</th><th>Flow</th><th>RS</th><th>Activity</th><th>Breadth</th><th>Heat</th><th>Acceleration</th><th>As of</th>'
      + '</tr></thead><tbody>'
      + latest.map((row) => {
        const scores = row.scores || {};
        return `<tr><td>${esc(row.name || row.id)}</td>`
          + `<td><strong>${esc(transition(row))}</strong></td>`
          + `<td>${esc(transitionClass(row))}</td>`
          + `<td>${num(row.flow_score)}</td>`
          + `<td>${num(scores.relative_strength)}</td>`
          + `<td>${num(scores.activity)}</td>`
          + `<td>${num(scores.breadth)}</td>`
          + `<td>${num(scores.heat)}</td>`
          + `<td>${num(scores.acceleration)}</td>`
          + `<td>${esc(row.as_of)}</td></tr>`;
      }).join('') + '</tbody></table>';
  }

  fetch(`${HISTORY_URL}?t=${Date.now()}`, { cache: 'no-store' })
    .then((response) => {
      if (response.status === 404) return '';
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.text();
    })
    .then((text) => {
      const rows = text.split(/\r?\n/).filter((line) => line.trim()).map((line) => JSON.parse(line));
      render(rows);
    })
    .catch((error) => {
      summary.innerHTML = `<strong>DATA UNAVAILABLE</strong><p>Sector history取得失敗: ${esc(error.message)}</p>`;
      focus.innerHTML = '';
      table.innerHTML = '';
    });
})();
</script>
