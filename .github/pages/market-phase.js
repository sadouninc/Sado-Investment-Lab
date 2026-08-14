(() => {
  const source = document.getElementById("phase-data");
  if (!source) return;
  const data = JSON.parse(source.textContent);
  const symbols = Object.fromEntries(data.symbols.map(item => [item.code, item]));
  const colors = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2",
    "#be123c", "#4f46e5", "#65a30d", "#c026d3"];
  const esc = value => String(value).replace(/[&<>"']/g, char =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
  const table = (rows, columns) =>
    `<div class="table-scroll"><table><thead><tr>${columns.map(c => `<th>${c[0]}</th>`).join("")}</tr></thead>` +
    `<tbody>${rows.map(row => `<tr>${columns.map(c => `<td>${esc(c[1](row))}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  const symbolLabel = code => {
    const name = symbols[code]?.name;
    return name ? `${name} (${code})` : code;
  };
  const shortSymbolLabel = code => {
    const name = symbols[code]?.name || "";
    return `${code} ${name}`.trim();
  };
  const correlationDirection = value => value >= 0 ? "同方向" : "逆方向";
  const formatDay = day => String(day).replace(/^(\d{4})-(\d{2})-(\d{2}).*$/, "$1/$2/$3");
  let selectedCodes = new Set();

  function currentGroupCodes() {
    const group = document.getElementById("phase-group").value;
    return data.symbols.filter(item => group === "all" || item.group === group).map(item => item.code);
  }

  function ensureSelectionForGroup() {
    const available = new Set(currentGroupCodes());
    const retained = [...selectedCodes].filter(code => available.has(code));
    selectedCodes = new Set(retained.length ? retained : available);
  }

  function selectedSeries(period) {
    ensureSelectionForGroup();
    return data.symbols.filter(item => selectedCodes.has(item.code)).map(item => {
      const points = Object.entries(data.normalized[item.code] || {}).slice(-period);
      if (!points.length) return null;
      const base = points[0][1];
      if (base == null || base === 0) return null;
      return {item, points: points.map(([day, value]) => [day, value / base * 100])};
    }).filter(Boolean);
  }

  function renderSelectionLegend(series) {
    const legend = document.getElementById("phase-legend");
    legend.innerHTML = series.map((row, index) =>
      `<label class="phase-series-choice"><input type="checkbox" data-phase-code="${esc(row.item.code)}" checked>` +
      `<i style="background:${colors[index % colors.length]}"></i>${esc(row.item.code)} ${esc(row.item.name)}</label>`).join("");
    legend.querySelectorAll("input[data-phase-code]").forEach(input => {
      input.addEventListener("change", event => {
        const code = event.currentTarget.dataset.phaseCode;
        if (event.currentTarget.checked) selectedCodes.add(code);
        else selectedCodes.delete(code);
        if (!selectedCodes.size) selectedCodes.add(code);
        renderAllSelectionViews();
      });
    });
  }

  function renderChart() {
    const svg = document.getElementById("phase-chart");
    const period = Number(document.getElementById("phase-period").value);
    const series = selectedSeries(period);
    const values = series.flatMap(row => row.points.map(point => point[1]));
    const min = Math.min(...values, 90), max = Math.max(...values, 110);
    const x = (index, length) => 60 + index / Math.max(1, length - 1) * 820;
    const y = value => 425 - (value - min) / Math.max(1, max - min) * 380;
    let content = `<line x1="60" y1="${y(100)}" x2="880" y2="${y(100)}" class="chart-baseline"/>`;

    series.forEach((row, index) => {
      const color = colors[index % colors.length];
      const points = row.points.map((point, i) => `${x(i, row.points.length)},${y(point[1])}`).join(" ");
      const last = row.points[row.points.length - 1];
      const labelOffset = ((index % 5) - 2) * 10;
      content += `<polyline points="${points}" fill="none" stroke="${color}" stroke-width="2" opacity="${series.length > 20 ? .45 : .8}"><title>${esc(row.item.name)}</title></polyline>`;
      content += `<text x="888" y="${y(last[1]) + labelOffset}" class="phase-line-label" data-phase-code="${esc(row.item.code)}">${esc(row.item.code)} ${esc(row.item.name)}</text>`;
    });

    if (series.length) {
      const days = series[0].points.map(point => point[0]);
      const tickIndexes = [...new Set([0, Math.floor((days.length - 1) / 2), days.length - 1])];
      tickIndexes.forEach(index => {
        const px = x(index, days.length);
        content += `<line x1="${px}" y1="430" x2="${px}" y2="436" class="chart-tick"/>`;
        content += `<text x="${px}" y="452" text-anchor="middle" class="phase-date-tick">${esc(formatDay(days[index]))}</text>`;
      });
      const range = document.getElementById("phase-range") || document.createElement("p");
      range.id = "phase-range";
      range.className = "phase-date-range";
      range.textContent = `表示期間: ${formatDay(days[0])} — ${formatDay(days[days.length - 1])}`;
      if (!range.isConnected) svg.before(range);
    }
    content += `<text x="8" y="${y(max) + 5}">${max.toFixed(0)}</text><text x="8" y="${y(min) + 5}">${min.toFixed(0)}</text>`;
    svg.innerHTML = content;
    renderSelectionLegend(series);
  }

  function correlationValue(left, right) {
    const row = data.correlation.pearson[left] || {};
    const value = row[right];
    return value == null ? null : Number(value);
  }

  function selectedPairs(codes) {
    const pairs = [];
    codes.forEach((left, index) => {
      codes.slice(index + 1).forEach(right => {
        const correlation = correlationValue(left, right);
        if (correlation != null) pairs.push({left, right, correlation});
      });
    });
    return pairs.sort((a, b) => Math.abs(b.correlation) - Math.abs(a.correlation));
  }

  function renderHeatmap() {
    const codes = [...selectedCodes];
    const target = document.getElementById("phase-heatmap");
    if (!codes.length) {
      target.innerHTML = "<p>相関を比較する銘柄が選択されていません。</p>";
      return;
    }
    if (codes.length === 1) {
      target.innerHTML = `<p>相関を比較するには2銘柄以上選択してください。現在: ${esc(symbolLabel(codes[0]))}</p>`;
      renderSelectedPairSummary([]);
      return;
    }
    let html = `<table><thead><tr><th></th>${codes.map(code => `<th title="${esc(symbols[code].name)}">${code}</th>`).join("")}</tr></thead><tbody>`;
    codes.forEach(left => {
      html += `<tr><th>${left}</th>`;
      codes.forEach(right => {
        const value = correlationValue(left, right);
        const hue = value == null ? 0 : value >= 0 ? 210 : 4;
        const alpha = value == null ? .05 : .12 + Math.abs(value) * .72;
        html += `<td style="background:hsla(${hue},75%,50%,${alpha})" title="${left} × ${right}: ${value == null ? "データ不足" : value.toFixed(2)}">${value == null ? "—" : value.toFixed(1)}</td>`;
      });
      html += "</tr>";
    });
    target.innerHTML = html + "</tbody></table>";
    renderSelectedPairSummary(selectedPairs(codes));
  }

  function renderSelectedPairSummary(pairs) {
    let target = document.getElementById("phase-selected-pairs");
    const heatmap = document.getElementById("phase-heatmap");
    if (!target) {
      target = document.createElement("section");
      target.id = "phase-selected-pairs";
      heatmap.before(target);
    }
    target.innerHTML = `<h3>選択銘柄内の相関</h3>` + (pairs.length
      ? table(pairs.slice(0, 5), [
          ["銘柄ペア", row => `${symbolLabel(row.left)} × ${symbolLabel(row.right)}`],
          ["方向", row => correlationDirection(row.correlation)],
          ["相関", row => row.correlation.toFixed(3)]
        ])
      : "<p>比較できる相関データがありません。データ不足を0相関として扱いません。</p>");
  }

  function relatedRows(code) {
    return Object.entries(data.correlation.pearson[code] || {})
      .filter(([other, value]) => other !== code && !selectedCodes.has(other) && value != null)
      .map(([other, value]) => ({code: other, correlation: Number(value)}))
      .sort((a, b) => Math.abs(b.correlation) - Math.abs(a.correlation))
      .slice(0, 5);
  }

  function renderRelatedDiscovery() {
    let target = document.getElementById("phase-related-discovery");
    const heatmap = document.getElementById("phase-heatmap");
    if (!target) {
      target = document.createElement("details");
      target.id = "phase-related-discovery";
      heatmap.after(target);
    }
    const rows = [...selectedCodes].flatMap(code => relatedRows(code).map(row => ({...row, source: code})));
    target.innerHTML = `<summary>関連銘柄を探す</summary><p>比較中の銘柄とは分離し、既存の相関データから未選択銘柄を探します。</p>` +
      (rows.length ? table(rows, [
        ["基準", row => symbolLabel(row.source)],
        ["関連候補", row => symbolLabel(row.code)],
        ["方向", row => correlationDirection(row.correlation)],
        ["相関", row => row.correlation.toFixed(3)]
      ]) : "<p>利用可能な関連銘柄データがありません。</p>");
  }

  function selectedCorrelationRows(code) {
    return Object.entries(data.correlation.pearson[code] || {})
      .filter(([other, value]) => other !== code && value != null)
      .map(([other, value]) => ({
        code: other,
        name: symbols[other]?.name || "",
        correlation: Number(value)
      }))
      .sort((a, b) => Math.abs(b.correlation) - Math.abs(a.correlation))
      .slice(0, 8);
  }

  function renderSelectedCorrelation(code) {
    const target = document.getElementById("phase-mobile-selected-row");
    if (!target) return;
    const rows = selectedCorrelationRows(code);
    target.innerHTML = table(rows, [
      ["相手", row => symbolLabel(row.code)],
      ["方向", row => correlationDirection(row.correlation)],
      ["相関", row => row.correlation.toFixed(3)]
    ]);
  }

  function renderMobileCorrelationSummary() {
    if (!window.matchMedia("(max-width: 700px)").matches) return;
    const heatmap = document.getElementById("phase-heatmap");
    if (!heatmap || document.getElementById("phase-mobile-correlation-summary")) return;

    const summary = document.createElement("section");
    summary.id = "phase-mobile-correlation-summary";
    summary.innerHTML = `
      <h3>相関の見方</h3>
      <p>まず「選択銘柄内の相関」で比較し、必要なときだけ「関連銘柄を探す」で探索範囲を広げます。</p>
      <div class="phase-controls">
        <label>個別銘柄の相関を確認
          <select id="phase-mobile-row-select">
            ${data.symbols.map(item => `<option value="${esc(item.code)}">${esc(item.code)} ${esc(item.name)}</option>`).join("")}
          </select>
        </label>
      </div>
      <div id="phase-mobile-selected-row"></div>`;
    heatmap.before(summary);
    const select = document.getElementById("phase-mobile-row-select");
    select.addEventListener("change", () => renderSelectedCorrelation(select.value));
    renderSelectedCorrelation(select.value);
  }

  function renderAllSelectionViews() {
    renderChart();
    renderHeatmap();
    renderRelatedDiscovery();
  }

  const grouped = {};
  data.symbols.forEach(item => (grouped[item.cluster] ||= []).push(item));
  document.getElementById("phase-clusters").innerHTML = Object.entries(grouped).map(([id, items]) =>
    `<section><h3>Cluster ${id}</h3><ul>${items.map(item => `<li>${item.code} ${esc(item.name)}<small>${esc(item.group)}</small></li>`).join("")}</ul></section>`).join("");
  document.getElementById("phase-cluster-periods").innerHTML = table(data.symbols, [
    ["コード", row => row.code], ["銘柄", row => row.name],
    ["3か月", row => `Cluster ${data.clusters_by_period["3m"][row.code]}`],
    ["6か月", row => `Cluster ${data.clusters_by_period["6m"][row.code]}`],
    ["1年", row => `Cluster ${data.clusters_by_period["1y"][row.code]}`],
  ]);
  const pairColumns = [["銘柄ペア", row => `${row.left} × ${row.right}`], ["相関", row => row.correlation.toFixed(3)]];
  document.getElementById("phase-positive").innerHTML = table(data.top_positive_pairs, pairColumns);
  document.getElementById("phase-negative").innerHTML = table(data.top_negative_pairs, pairColumns);
  document.getElementById("phase-lead-lag").innerHTML = table(data.lead_lag.slice(0, 20), [
    ["先行候補", row => row.leader || "同日"], ["追随候補", row => row.follower || "同日"],
    ["ラグ", row => `${row.lag}日`], ["相関", row => row.correlation.toFixed(3)],
    ["共通標本", row => row.samples],
  ]);
  document.getElementById("phase-period").addEventListener("change", renderAllSelectionViews);
  document.getElementById("phase-group").addEventListener("change", () => {
    selectedCodes = new Set(currentGroupCodes());
    renderAllSelectionViews();
  });
  selectedCodes = new Set(currentGroupCodes());
  renderAllSelectionViews();
  renderMobileCorrelationSummary();
})();
