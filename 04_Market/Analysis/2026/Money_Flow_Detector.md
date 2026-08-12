# 💸 Money Flow Detector

Sector / Themeへの資金流入を、**COLD → WARMING → INFLOW → HOT → OVERHEATED** の状態遷移として追跡する研究ダッシュボードです。

このページは買い／売りシグナルではありません。狙いは、まだ市場の主役ではない領域で温度が上がり始めた変化を見つけ、Company Research / Candidate Selectorへ研究材料として渡すことです。

## State Guide

| State | 意味 | Candidate source |
| --- | --- | --- |
| COLD | 相対的に弱い／資金流入の兆候が乏しい | No |
| WARMING | levelはまだ極端でないが改善が複数軸で始まった | **Yes** |
| INFLOW | 改善が継続し、資金流入の確度が上がった | **Yes** |
| HOT | すでに市場の注目・上昇が高水準 | No |
| OVERHEATED | 初動発見としては遅い可能性が高い | No |

## Latest Snapshot

<div id="money-flow-summary" class="notice-card" aria-live="polite">
  <strong>Money Flow historyを確認中...</strong>
</div>

<div id="money-flow-state-table" class="table-scroll"></div>

## Policy Lead-Time — 政策と市場、どちらが先に動いたか

Policy Intelligenceのcheckpointと、独立して計算されたMarket Money Flowを時系列で比較します。**Policy EvidenceはMoney Flow scoreへ混ぜず**、すでに生成済みのcanonical判定をread-only表示します。

- **POLICY_LEADS** — 政策の後に意味あるMarket Flowが成立
- **MARKET_LEADS** — 市場が政策より先に動き、政策後の新しい持続・再加速は未確認
- **POLICY_CONFIRMATION** — 市場が先行した後、政策後もFlowが維持／再成立
- **REACCELERATION_AFTER_POLICY** — 市場が先行・冷却した後、政策後に再加速
- **DATA_LIMITED / INCONCLUSIVE** — データ品質・期間・membership等の制約で強い判定をしない

<div id="policy-lead-time-summary" class="notice-card" aria-live="polite">
  <strong>Policy Lead-Timeを確認中...</strong>
</div>

<div id="policy-lead-time-table" class="table-scroll"></div>

## Stability / Evaluation

<div id="money-flow-stability" class="notice-card">
  <strong>履歴が蓄積されると、state change率・WARMING継続期間・short reversal・selection turnoverを確認できます。</strong>
</div>

<div id="money-flow-forward" class="table-scroll"></div>

## Data Contract

- History: `data/generated/public/money-flow/history.jsonl`
- Evaluation: `data/generated/public/money-flow/evaluation.json`
- Policy Lead-Time AI/DC: `data/generated/public/money-flow/policy-lead-time-ai-dc-v2.json`
- Policy Lead-Time Defense Drone: `data/generated/public/money-flow/policy-lead-time-defense-drone-v2.json`
- Policy Lead-Time Physical AI: `data/generated/public/money-flow/policy-lead-time-physical-ai-v2.json`
- 同一 `(kind, id, as_of)` の再保存はidempotentに扱います。
- 同一identityでpayloadが異なる場合はsilent overwriteせずfail closedです。
- 将来価格が不足する場合、forward returnは `0%` にせず `null` / 未評価として扱います。
- 欠損scoreも0点へ変換しません。
- Policy Lead-Timeの `classification / data_quality / limitations` はcanonical artifactをそのまま表示し、ブラウザ側で再判定しません。

> 履歴・評価・Policy Lead-Timeデータがまだ生成されていない場合、このページは `NO DATA` を表示します。存在しない市場データや政策判定を推測・補完して表示しません。

<script>
(() => {
  const RAW_BASE = 'https://raw.githubusercontent.com/sadouninc/Sado-Investment-Lab/main/';
  const HISTORY_URL = RAW_BASE + 'data/generated/public/money-flow/history.jsonl';
  const EVALUATION_URL = RAW_BASE + 'data/generated/public/money-flow/evaluation.json';
  const POLICY_URLS = [
    RAW_BASE + 'data/generated/public/money-flow/policy-lead-time-ai-dc-v2.json',
    RAW_BASE + 'data/generated/public/money-flow/policy-lead-time-defense-drone-v2.json',
    RAW_BASE + 'data/generated/public/money-flow/policy-lead-time-physical-ai-v2.json',
  ];
  const summary = document.getElementById('money-flow-summary');
  const stateTable = document.getElementById('money-flow-state-table');
  const stability = document.getElementById('money-flow-stability');
  const forward = document.getElementById('money-flow-forward');
  const policySummary = document.getElementById('policy-lead-time-summary');
  const policyTable = document.getElementById('policy-lead-time-table');
  const states = ['COLD', 'WARMING', 'INFLOW', 'HOT', 'OVERHEATED'];

  const esc = (value) => String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  const num = (value, digits = 1) => Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : '—';
  const classificationJa = {
    POLICY_LEADS: '政策が先行',
    MARKET_LEADS: '市場が先行',
    POLICY_CONFIRMATION: '政策が市場先行を確認',
    REACCELERATION_AFTER_POLICY: '政策後に再加速',
    DATA_LIMITED: 'データ制約あり',
    INCONCLUSIVE: '判定保留',
  };

  function latestPerEntity(rows) {
    const latest = new Map();
    rows.forEach((row) => {
      if (!row || !row.id || !row.as_of) return;
      const key = `${row.kind || ''}:${row.id}`;
      const current = latest.get(key);
      if (!current || String(row.as_of) > String(current.as_of)) latest.set(key, row);
    });
    return [...latest.values()].sort((a, b) =>
      (states.indexOf(a.state) - states.indexOf(b.state)) || String(a.name || a.id).localeCompare(String(b.name || b.id), 'ja')
    );
  }

  function computeStability(rows) {
    const grouped = new Map();
    rows.forEach((row) => {
      const key = `${row.kind || ''}:${row.id || ''}`;
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(row);
    });
    let transitions = 0;
    let comparisons = 0;
    const warmingRuns = [];
    let shortReversals = 0;
    grouped.forEach((items) => {
      items.sort((a, b) => String(a.as_of).localeCompare(String(b.as_of)));
      for (let i = 1; i < items.length; i++) {
        comparisons++;
        if (items[i - 1].state !== items[i].state) transitions++;
      }
      let i = 0;
      while (i < items.length) {
        const state = items[i].state;
        let j = i + 1;
        while (j < items.length && items[j].state === state) j++;
        const len = j - i;
        if (state === 'WARMING') {
          warmingRuns.push(len);
          if (len <= 2 && j < items.length && items[j].state === 'COLD') shortReversals++;
        }
        i = j;
      }
    });
    return {
      stateChangeRate: comparisons ? transitions / comparisons : null,
      warmingAverage: warmingRuns.length ? warmingRuns.reduce((a, b) => a + b, 0) / warmingRuns.length : null,
      shortReversalRate: warmingRuns.length ? shortReversals / warmingRuns.length : null,
    };
  }

  function renderHistory(rows) {
    if (!rows.length) {
      summary.innerHTML = '<strong>NO DATA</strong><p>Money Flowの日次snapshotはまだ公開されていません。</p>';
      stateTable.innerHTML = '';
      return;
    }
    const latest = latestPerEntity(rows);
    const signals = latest.filter((row) => row.selection_signal === true);
    const newest = rows.map((row) => row.as_of).filter(Boolean).sort().at(-1) || '—';
    summary.innerHTML = `<strong>Latest: ${esc(newest)}</strong><p>${latest.length} Sector / Theme、WARMING・INFLOW candidate ${signals.length}件。</p>`;
    stateTable.innerHTML = '<table><thead><tr><th>Kind</th><th>Sector / Theme</th><th>State</th><th>Flow</th><th>RS</th><th>Activity</th><th>Breadth</th><th>Heat</th><th>Acceleration</th><th>As of</th></tr></thead><tbody>'
      + latest.map((row) => {
        const s = row.scores || {};
        return `<tr><td>${esc(row.kind)}</td><td>${esc(row.name || row.id)}</td><td><strong>${esc(row.state)}</strong></td><td>${num(row.flow_score)}</td><td>${num(s.relative_strength)}</td><td>${num(s.activity)}</td><td>${num(s.breadth)}</td><td>${num(s.heat)}</td><td>${num(s.acceleration)}</td><td>${esc(row.as_of)}</td></tr>`;
      }).join('') + '</tbody></table>';

    const metrics = computeStability(rows);
    stability.innerHTML = '<strong>History stability</strong><dl>'
      + `<dt>Snapshot</dt><dd>${rows.length}</dd>`
      + `<dt>State change rate</dt><dd>${metrics.stateChangeRate == null ? '—' : (metrics.stateChangeRate * 100).toFixed(1) + '%'}</dd>`
      + `<dt>WARMING average duration</dt><dd>${metrics.warmingAverage == null ? '—' : metrics.warmingAverage.toFixed(1) + ' sessions'}</dd>`
      + `<dt>WARMING short reversal</dt><dd>${metrics.shortReversalRate == null ? '—' : (metrics.shortReversalRate * 100).toFixed(1) + '%'}</dd>`
      + '</dl>';
  }

  function renderEvaluation(payload) {
    const rows = Array.isArray(payload) ? payload : (payload?.evaluations || payload?.results || []);
    if (!rows.length) {
      forward.innerHTML = '<p>Forward performanceはまだ評価可能な履歴がありません。</p>';
      return;
    }
    forward.innerHTML = '<table><thead><tr><th>As of</th><th>Sector / Theme</th><th>State</th><th>5 sessions</th><th>20 sessions</th><th>60 sessions</th></tr></thead><tbody>'
      + rows.map((row) => {
        const r = row.forward_returns_pct || {};
        return `<tr><td>${esc(row.as_of)}</td><td>${esc(row.name || row.id)}</td><td>${esc(row.state)}</td><td>${num(r.return_5d, 2)}%</td><td>${num(r.return_20d, 2)}%</td><td>${num(r.return_60d, 2)}%</td></tr>`;
      }).join('') + '</tbody></table>';
  }

  function renderPolicyLeadTime(payloads) {
    const available = payloads.filter(Boolean);
    if (!available.length) {
      policySummary.innerHTML = '<strong>NO DATA</strong><p>Policy Lead-Time v2はまだ公開されていません。</p>';
      policyTable.innerHTML = '';
      return;
    }
    const rows = [];
    available.forEach((payload) => {
      const checkpoints = payload.policy_checkpoints || payload.checkpoints || [];
      if (checkpoints.length) {
        checkpoints.forEach((checkpoint) => rows.push({ payload, checkpoint, evaluation: checkpoint.evaluation || checkpoint }));
      } else if (payload.evaluation || payload.classification) {
        rows.push({ payload, checkpoint: { date: payload.policy_t0, label: payload.policy_label || 'Policy checkpoint' }, evaluation: payload.evaluation || payload });
      }
    });
    if (!rows.length) {
      policySummary.innerHTML = '<strong>NO DATA</strong><p>Policy checkpointの判定結果がありません。</p>';
      policyTable.innerHTML = '';
      return;
    }
    const counts = {};
    rows.forEach(({ evaluation }) => {
      const key = evaluation.classification || 'INCONCLUSIVE';
      counts[key] = (counts[key] || 0) + 1;
    });
    policySummary.innerHTML = `<strong>${available.length}テーマ / ${rows.length} checkpoint</strong><p>${Object.entries(counts).map(([key, value]) => `${esc(classificationJa[key] || key)} ${value}`).join('・')}</p>`;
    policyTable.innerHTML = '<table><thead><tr><th>Theme</th><th>Policy date</th><th>Stage / checkpoint</th><th>判定</th><th>Data quality</th><th>Market state around policy</th><th>Limitations</th></tr></thead><tbody>'
      + rows.sort((a, b) => String(a.checkpoint.date || '').localeCompare(String(b.checkpoint.date || ''))).map(({ payload, checkpoint, evaluation }) => {
        const sequence = checkpoint.sequence_summary || {};
        const before = sequence.pre_policy_state?.state || '—';
        const at = sequence.state_at_or_before_policy?.state || '—';
        const after = sequence.reliable_strongest_post_policy_state || '—';
        const limitations = evaluation.limitations || payload.limitations || [];
        const classification = evaluation.classification || 'INCONCLUSIVE';
        return `<tr><td>${esc(payload.theme_name || payload.theme_id || '—')}</td><td>${esc(checkpoint.date || evaluation.policy_t0 || '—')}</td><td>${esc(checkpoint.policy_stage || checkpoint.label || '—')}<br><small>${esc(checkpoint.label || '')}</small></td><td><strong>${esc(classificationJa[classification] || classification)}</strong><br><small>${esc(classification)}</small></td><td>${esc(evaluation.data_quality || '—')}</td><td>${esc(before)} → ${esc(at)} → ${esc(after)}</td><td>${limitations.length ? limitations.map(esc).join('<br>') : '—'}</td></tr>`;
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
      renderHistory(rows);
    })
    .catch((error) => {
      summary.innerHTML = `<strong>DATA UNAVAILABLE</strong><p>History取得失敗: ${esc(error.message)}</p>`;
    });

  fetch(`${EVALUATION_URL}?t=${Date.now()}`, { cache: 'no-store' })
    .then((response) => {
      if (response.status === 404) return null;
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then((payload) => renderEvaluation(payload))
    .catch((error) => {
      forward.innerHTML = `<p>Evaluation取得失敗: ${esc(error.message)}</p>`;
    });

  Promise.all(POLICY_URLS.map((url) => fetch(`${url}?t=${Date.now()}`, { cache: 'no-store' })
    .then((response) => {
      if (response.status === 404) return null;
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .catch(() => null)))
    .then((payloads) => renderPolicyLeadTime(payloads))
    .catch((error) => {
      policySummary.innerHTML = `<strong>DATA UNAVAILABLE</strong><p>Policy Lead-Time取得失敗: ${esc(error.message)}</p>`;
    });
})();
</script>