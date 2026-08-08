(() => {
  const normalizedPath = window.location.pathname.replace(/\/+$/, '');
  if (!normalizedPath.endsWith('/research/ai-key-person-watch')) return;

  const main = document.querySelector('main.book-shell');
  const title = main?.querySelector('h1');
  if (!main || !title) return;

  const panel = document.createElement('section');
  panel.className = 'notice-card';
  panel.setAttribute('aria-live', 'polite');
  panel.innerHTML = '<strong>Monitoring status</strong><p>Heartbeatを確認中...</p>';
  title.insertAdjacentElement('afterend', panel);

  const statusUrl = 'https://raw.githubusercontent.com/sadouninc/Sado-Investment-Lab/main/Ops/Monitoring/AI_Key_Person_Watch/status.json';

  const escapeHtml = (value) => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const classify = (payload) => {
    const lastSuccess = payload.last_success_at ? new Date(payload.last_success_at) : null;
    if (!lastSuccess || Number.isNaN(lastSuccess.getTime())) {
      return { state: 'STALE', reason: '成功runがまだ記録されていません。' };
    }
    const ageMinutes = (Date.now() - lastSuccess.getTime()) / 60000;
    const staleAfter = Number(payload.stale_after_minutes || 150);
    if (ageMinutes > staleAfter) {
      return { state: 'STALE', reason: `最終成功runから約${Math.floor(ageMinutes)}分経過しています。` };
    }
    if (payload.last_status === 'ERROR') {
      return { state: 'DEGRADED', reason: '直近runがERRORです。' };
    }
    if (payload.persistence_status === 'PENDING_PERSIST') {
      return { state: 'DEGRADED', reason: 'ニュース保存がPENDING_PERSISTです。' };
    }
    return { state: 'HEALTHY', reason: '直近の成功runは監視閾値内です。' };
  };

  const renderTime = (value) => value ? new Date(value).toLocaleString('ja-JP', { timeZone: 'Asia/Tokyo' }) + ' JST' : '未記録';

  fetch(`${statusUrl}?t=${Date.now()}`, { cache: 'no-store' })
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then((payload) => {
      const health = classify(payload);
      panel.innerHTML = `
        <strong>Monitoring status: ${escapeHtml(health.state)}</strong>
        <dl>
          <dt>最終監視成功</dt><dd>${escapeHtml(renderTime(payload.last_success_at))}</dd>
          <dt>最終ニュース差分</dt><dd>${escapeHtml(renderTime(payload.last_news_delta_at))}</dd>
          <dt>直近run</dt><dd>${escapeHtml(renderTime(payload.last_run_at))}</dd>
          <dt>状態理由</dt><dd>${escapeHtml(health.reason)}</dd>
        </dl>`;
    })
    .catch((error) => {
      panel.innerHTML = `<strong>Monitoring status: UNKNOWN</strong><p>Heartbeatの取得に失敗しました: ${escapeHtml(error.message)}</p>`;
    });
})();
