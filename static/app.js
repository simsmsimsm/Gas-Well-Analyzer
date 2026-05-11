/* ============================================================
   Gas Well Correlation Analyzer — frontend logic
   Uses Plotly.js (loaded via CDN in index.html)
   ============================================================ */

// ── State ─────────────────────────────────────────────────────────────────
const S = {
  tab: "scatter",
  info: null,           // /api/info response
  // per-tab selections
  scatter: { x: null, y: null, color: null, outlierMethod: "none" },
  overview: { tempCol: null },
  timeseries: { dateCol: null, cols: [], rollingWindow: 0 },
};

// ── Boot ──────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });
  document.getElementById("file-input").addEventListener("change", onFileChange);
  showEmpty("Load sample data or upload a CSV to begin.");
});

// ── Data loading ──────────────────────────────────────────────────────────
async function loadSample() {
  setDataStatus("Loading…", false);
  const res = await fetch("/api/sample");
  const d = await res.json();
  if (d.error) { setDataStatus("Error: " + d.error, false); return; }
  await refreshInfo();
}

async function onFileChange(evt) {
  const file = evt.target.files[0];
  if (!file) return;
  setDataStatus("Uploading…", false);
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/upload", { method: "POST", body: form });
  const d = await res.json();
  if (d.error) { setDataStatus("Error: " + d.error, false); return; }
  await refreshInfo();
}

async function refreshInfo() {
  const res = await fetch("/api/info");
  S.info = await res.json();
  if (S.info.error) { setDataStatus("Error: " + S.info.error, false); return; }

  setDataStatus(`${S.info.filename}\n${S.info.rows.toLocaleString()} rows · ${S.info.numeric_cols.length} numeric cols`, true);
  document.getElementById("analyze-btn").disabled = false;

  // Show / populate date range filter when a date column is present
  const wrap = document.getElementById("date-filter-wrap");
  if (S.info.date_col && S.info.date_min) {
    wrap.style.display = "";
    document.getElementById("date-from").value = S.info.date_min;
    document.getElementById("date-to").value   = S.info.date_max;
    document.getElementById("date-from").min   = S.info.date_min;
    document.getElementById("date-from").max   = S.info.date_max;
    document.getElementById("date-to").min     = S.info.date_min;
    document.getElementById("date-to").max     = S.info.date_max;
  } else {
    wrap.style.display = "none";
  }

  buildControls();
  showEmpty("Configure columns and click Analyze.");
}

function resetDateRange() {
  if (!S.info) return;
  document.getElementById("date-from").value = S.info.date_min || "";
  document.getElementById("date-to").value   = S.info.date_max || "";
}

function dateRange() {
  return {
    date_from: document.getElementById("date-from")?.value || null,
    date_to:   document.getElementById("date-to")?.value   || null,
  };
}

function setDataStatus(msg, loaded) {
  const el = document.getElementById("data-status");
  el.textContent = msg;
  el.className = loaded ? "loaded" : "";
}

// ── Tab switching ─────────────────────────────────────────────────────────
function switchTab(tab) {
  S.tab = tab;
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.toggle("active", b.dataset.tab === tab));
  if (S.info) buildControls();
  clearChart();
}

// ── Sidebar controls ──────────────────────────────────────────────────────
function buildControls() {
  const info = S.info;
  const nc = info.numeric_cols;
  const dt = info.date_col;
  const tc = info.temp_cols;
  const el = document.getElementById("tab-controls");

  if (S.tab === "scatter") {
    el.innerHTML = `
      <div class="form-group">
        <label>X Axis</label>
        ${selectEl("sc-x", nc, S.scatter.x || nc[0])}
      </div>
      <div class="form-group">
        <label>Y Axis</label>
        ${selectEl("sc-y", nc, S.scatter.y || nc[1] || nc[0])}
      </div>
      <div class="form-group">
        <label>Colour By (optional)</label>
        ${selectEl("sc-color", ["(none)", ...nc], S.scatter.color || "(none)")}
      </div>
      <div class="form-group">
        <label>Outlier Detection</label>
        ${selectEl("sc-outlier", ["none", "iqr", "zscore"], S.scatter.outlierMethod || "none")}
        <p class="ts-hint" style="margin-top:4px">IQR = 1.5×IQR fence &nbsp;|&nbsp; Z-score = |z| &gt; 3</p>
      </div>`;
  } else if (S.tab === "overview") {
    const choices = tc.length ? tc : nc;
    el.innerHTML = `
      <div class="form-group">
        <label>Temperature Column</label>
        ${selectEl("ov-temp", choices, S.overview.tempCol || choices[0])}
      </div>
      <p class="ts-hint">Shows Pearson r of selected temperature column vs every other numeric variable, sorted by strength.</p>`;
  } else if (S.tab === "matrix") {
    el.innerHTML = `<p class="ts-hint" style="color:#7a92a8;font-size:11px">Displays the full Pearson correlation matrix for all numeric columns. No selection needed.</p>`;
  } else if (S.tab === "timeseries") {
    const dateCols = info.columns.filter(c => c.is_datetime || c.is_numeric).map(c => c.name);
    const checkItems = nc.map(col => `
      <label class="col-check-item">
        <input type="checkbox" value="${esc(col)}" ${S.timeseries.cols.includes(col) ? "checked" : ""}>
        ${esc(col)}
      </label>`).join("");
    const rollingVal = S.timeseries.rollingWindow ?? 0;
    el.innerHTML = `
      <div class="form-group">
        <label>X Axis / Date</label>
        ${selectEl("ts-date", ["(row index)", ...dateCols], S.timeseries.dateCol || dt || "(row index)")}
      </div>
      <div class="form-group">
        <label>Y Columns</label>
        <div class="col-checklist">${checkItems}</div>
      </div>
      <div class="form-group">
        <label>Rolling Average</label>
        <div class="rolling-row">
          <select id="ts-rolling-preset">
            <option value="0"  ${rollingVal === 0  ? "selected" : ""}>Off</option>
            <option value="7"  ${rollingVal === 7  ? "selected" : ""}>7-point</option>
            <option value="14" ${rollingVal === 14 ? "selected" : ""}>14-point</option>
            <option value="30" ${rollingVal === 30 ? "selected" : ""}>30-point</option>
            <option value="90" ${rollingVal === 90 ? "selected" : ""}>90-point</option>
            <option value="custom" ${rollingVal > 0 && ![7,14,30,90].includes(rollingVal) ? "selected" : ""}>Custom…</option>
          </select>
          <input type="number" id="ts-rolling-custom" min="2" max="365"
            value="${rollingVal > 0 && ![7,14,30,90].includes(rollingVal) ? rollingVal : ""}"
            placeholder="n"
            style="display:${rollingVal > 0 && ![7,14,30,90].includes(rollingVal) ? 'block' : 'none'}" />
        </div>
      </div>
      <p class="ts-hint">Each series gets its own Y axis. Rolling avg overlays in bold.</p>`;

    document.getElementById("ts-rolling-preset").addEventListener("change", e => {
      const custom = document.getElementById("ts-rolling-custom");
      custom.style.display = e.target.value === "custom" ? "block" : "none";
    });
  } else if (S.tab === "summary") {
    el.innerHTML = `<p class="ts-hint" style="color:#7a92a8;font-size:11px">Descriptive statistics for all numeric columns.</p>`;
  }
}

function selectEl(id, options, selected) {
  const opts = options.map(o => `<option value="${esc(o)}" ${o === selected ? "selected" : ""}>${esc(o)}</option>`).join("");
  return `<select id="${id}">${opts}</select>`;
}

// ── Analyze dispatch ──────────────────────────────────────────────────────
async function analyze() {
  if (!S.info) return;
  if (S.tab === "scatter")    await runScatter();
  else if (S.tab === "overview")   await runOverview();
  else if (S.tab === "matrix")     await runMatrix();
  else if (S.tab === "timeseries") await runTimeSeries();
  else if (S.tab === "summary")    await runSummary();
}

// ── Scatter ───────────────────────────────────────────────────────────────
async function runScatter() {
  const x = val("sc-x");
  const y = val("sc-y");
  const color = val("sc-color");
  if (!x || !y) return;
  S.scatter = { x, y, color };

  setChartTitle(`${x} vs ${y}`);
  showLoading();

  const res = await fetch("/api/scatter", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ x, y, color: color === "(none)" ? null : color, ...dateRange() }),
  });
  const d = await res.json();
  if (d.error) { showEmpty("Error: " + d.error); return; }

  // Build traces
  const markerColor = d.color
    ? d.color
    : Array(d.x.length).fill("#1a6bba");

  const traces = [
    // CI lower boundary (invisible)
    { x: d.trend_x, y: d.ci_lower, mode: "lines", line: { width: 0 }, showlegend: false, hoverinfo: "skip" },
    // CI upper fill
    {
      x: d.trend_x, y: d.ci_upper,
      mode: "lines", fill: "tonexty",
      fillcolor: "rgba(26,107,186,0.12)",
      line: { width: 0 },
      name: "95% CI", hoverinfo: "skip", showlegend: true,
    },
    // Regression line
    {
      x: d.trend_x, y: d.trend_y,
      mode: "lines",
      line: { color: "#e05252", width: 2, dash: "dash" },
      name: "Regression",
    },
    // Scatter points
    {
      x: d.x, y: d.y,
      mode: "markers",
      type: "scatter",
      name: "Data",
      marker: {
        color: d.color ? d.color : "#1a6bba",
        colorscale: d.color ? "Viridis" : null,
        showscale: !!d.color,
        colorbar: d.color ? { title: { text: d.color_col, side: "right" }, thickness: 14 } : null,
        size: 6,
        opacity: 0.75,
        line: { color: "#fff", width: 0.5 },
      },
      hovertemplate: `${x}: %{x:.3f}<br>${y}: %{y:.3f}<extra></extra>`,
    },
  ];

  const layout = plotLayout(x, y);
  Plotly.react("chart", traces, layout, plotConfig());

  showStats(d.stats, x, y);
}

// ── Temperature Overview ──────────────────────────────────────────────────
async function runOverview() {
  const tempCol = val("ov-temp");
  if (!tempCol) return;
  S.overview.tempCol = tempCol;

  setChartTitle(`Correlation with ${tempCol}`);
  showLoading();

  const res = await fetch("/api/temp-overview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ temp_col: tempCol, ...dateRange() }),
  });
  const d = await res.json();
  if (d.error) { showEmpty("Error: " + d.error); return; }

  const corrs = d.correlations;
  const cols   = corrs.map(c => c.column);
  const rs     = corrs.map(c => c.pearson_r);
  const sigs   = corrs.map(c => c.significant);
  const colors = rs.map((r, i) => {
    const opacity = sigs[i] ? 1 : 0.45;
    if (r >= 0) return `rgba(26,107,186,${opacity})`;
    return `rgba(224,82,82,${opacity})`;
  });
  const texts  = rs.map((r, i) => `r = ${r.toFixed(3)}${sigs[i] ? " *" : ""}`);

  const trace = {
    type: "bar",
    orientation: "h",
    x: rs,
    y: cols,
    text: texts,
    textposition: "outside",
    textfont: { size: 11 },
    marker: { color: colors },
    hovertemplate: "%{y}<br>r = %{x:.4f}<extra></extra>",
  };

  const layout = {
    ...plotLayout(`Pearson r with ${tempCol}`, "Variable"),
    xaxis: { title: { text: "Pearson r" }, range: [-1.1, 1.1], zeroline: true, zerolinecolor: "#888", zerolinewidth: 1.5 },
    yaxis: { autorange: "reversed", tickfont: { size: 11 } },
    margin: { l: 180, r: 80, t: 20, b: 50 },
    shapes: [
      { type: "line", x0: 0.3,  x1: 0.3,  y0: -0.5, y1: cols.length - 0.5, line: { color: "#ccc", dash: "dot", width: 1 } },
      { type: "line", x0: -0.3, x1: -0.3, y0: -0.5, y1: cols.length - 0.5, line: { color: "#ccc", dash: "dot", width: 1 } },
    ],
    annotations: [
      { x: 0.3,  y: -0.8, xref: "x", yref: "y", text: "0.3", showarrow: false, font: { size: 10, color: "#999" } },
      { x: -0.3, y: -0.8, xref: "x", yref: "y", text: "-0.3", showarrow: false, font: { size: 10, color: "#999" } },
    ],
  };

  Plotly.react("chart", [trace], layout, plotConfig());
  hideStats();

  // Wire click → scatter
  document.getElementById("chart").on("plotly_click", data => {
    const col = data.points[0]?.y;
    if (!col) return;
    // Pre-fill scatter and switch tab
    S.scatter = { x: tempCol, y: col, color: null };
    switchTab("scatter");
    buildControls();
    runScatter();
  });
}

// ── Correlation Matrix ────────────────────────────────────────────────────
async function runMatrix() {
  setChartTitle("Pearson Correlation Matrix");
  showLoading();

  const res = await fetch("/api/matrix", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...dateRange() }),
  });
  const d = await res.json();
  if (d.error) { showEmpty("Error: " + d.error); return; }

  const n = d.columns.length;
  // Annotations showing r value (skip if large matrix)
  const annotations = [];
  if (n <= 20) {
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const r = d.matrix[i][j];
        const p = d.p_matrix[i][j];
        const sig = p < 0.05 && i !== j;
        annotations.push({
          x: d.columns[j],
          y: d.columns[i],
          text: i === j ? "" : (r > 0 ? "+" : "") + r.toFixed(2) + (sig ? "" : ""),
          font: { size: n > 12 ? 8 : 10, color: Math.abs(r) > 0.5 ? "#fff" : "#24292f" },
          showarrow: false,
        });
      }
    }
  }

  const trace = {
    type: "heatmap",
    z: d.matrix,
    x: d.columns,
    y: d.columns,
    colorscale: [
      [0,    "#b40426"],
      [0.25, "#e05252"],
      [0.5,  "#f7f7f7"],
      [0.75, "#4393c3"],
      [1,    "#053061"],
    ],
    zmin: -1, zmax: 1,
    colorbar: { title: { text: "Pearson r", side: "right" }, thickness: 14, len: 0.8 },
    hovertemplate: "%{y} × %{x}<br>r = %{z:.4f}<extra></extra>",
  };

  const layout = {
    ...plotLayout("", ""),
    xaxis: { tickangle: -40, tickfont: { size: 10 } },
    yaxis: { tickfont: { size: 10 } },
    annotations,
    margin: { l: 150, r: 80, t: 20, b: 160 },
  };

  Plotly.react("chart", [trace], layout, plotConfig());
  hideStats();
}

// ── Time Series ───────────────────────────────────────────────────────────
async function runTimeSeries() {
  const dateColRaw = val("ts-date");
  const dateCol = dateColRaw === "(row index)" ? null : dateColRaw;
  const cols = [...document.querySelectorAll(".col-checklist input:checked")].map(i => i.value);

  if (!cols.length) { showEmpty("Select at least one Y column."); return; }

  const presetEl = document.getElementById("ts-rolling-preset");
  const presetVal = presetEl ? presetEl.value : "0";
  let rollingWindow = 0;
  if (presetVal === "custom") {
    rollingWindow = parseInt(document.getElementById("ts-rolling-custom")?.value || "0", 10) || 0;
  } else {
    rollingWindow = parseInt(presetVal, 10) || 0;
  }

  S.timeseries = { dateCol, cols, rollingWindow };
  setChartTitle("Time Series");
  showLoading();

  const res = await fetch("/api/timeseries", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ date_col: dateCol, columns: cols, rolling_window: rollingWindow, ...dateRange() }),
  });
  const d = await res.json();
  if (d.error) { showEmpty("Error: " + d.error); return; }

  const palette = ["#1a6bba","#e05252","#3abf7a","#f0a500","#9b59b6","#1abc9c","#e67e22","#2c3e50"];
  const hasRolling = !!d.rolling_window;
  const traces = [];

  d.series.forEach((s, i) => {
    const color = palette[i % palette.length];
    const yaxis = i === 0 ? "y" : `y${i + 1}`;

    // Raw data trace — faint when rolling avg is active
    traces.push({
      x: d.x,
      y: s.y,
      name: s.name,
      type: "scatter",
      mode: "lines",
      line: { color, width: hasRolling ? 1 : 1.8, dash: hasRolling ? "dot" : "solid" },
      opacity: hasRolling ? 0.35 : 1,
      yaxis,
      legendgroup: s.name,
      hovertemplate: `${esc(s.name)}: %{y:.3f}<extra></extra>`,
    });

    // Rolling average overlay
    if (hasRolling && s.y_rolling) {
      traces.push({
        x: d.x,
        y: s.y_rolling,
        name: `${s.name} (${d.rolling_window}-pt avg)`,
        type: "scatter",
        mode: "lines",
        line: { color, width: 2.5 },
        yaxis,
        legendgroup: s.name,
        hovertemplate: `${esc(s.name)} avg: %{y:.3f}<extra></extra>`,
      });
    }
  });

  // Build axis specs for each series
  const axisLayout = {};
  d.series.forEach((s, i) => {
    const key = i === 0 ? "yaxis" : `yaxis${i + 1}`;
    const side = i % 2 === 0 ? "left" : "right";
    axisLayout[key] = {
      title: { text: s.name, font: { size: 10 } },
      overlaying: i > 0 ? "y" : undefined,
      side,
      showgrid: i === 0,
      zeroline: false,
      tickfont: { size: 9 },
    };
  });

  const layout = {
    ...plotLayout(d.x_label, ""),
    ...axisLayout,
    xaxis: { title: { text: d.x_label }, tickfont: { size: 10 } },
    margin: { l: 60, r: d.series.length > 1 ? 80 : 30, t: 20, b: 60 },
    legend: { orientation: "h", y: -0.18 },
    hovermode: "x unified",
  };

  Plotly.react("chart", traces, layout, plotConfig());
  hideStats();
}

// ── Summary ───────────────────────────────────────────────────────────────
async function runSummary() {
  setChartTitle("Descriptive Statistics");
  showLoading();

  const res = await fetch("/api/summary", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...dateRange() }),
  });
  const rows = await res.json();
  if (rows.error) { showEmpty("Error: " + rows.error); return; }

  const fmt = (v) => {
    if (v === null || v === undefined) return "—";
    const abs = Math.abs(v);
    if (abs === 0) return "0";
    if (abs >= 1000) return v.toLocaleString("en-US", { maximumFractionDigits: 1 });
    if (abs >= 1) return v.toFixed(3);
    return v.toFixed(4);
  };

  const thead = `<tr><th>Column</th><th>n</th><th>Mean</th><th>Std</th><th>Min</th><th>P25</th><th>Median</th><th>P75</th><th>Max</th></tr>`;
  const tbody = rows.map(r => `
    <tr>
      <td>${esc(r.column)}</td>
      <td>${r.count}</td>
      <td>${fmt(r.mean)}</td>
      <td>${fmt(r.std)}</td>
      <td>${fmt(r.min)}</td>
      <td>${fmt(r.p25)}</td>
      <td>${fmt(r.median)}</td>
      <td>${fmt(r.p75)}</td>
      <td>${fmt(r.max)}</td>
    </tr>`).join("");

  document.getElementById("chart").innerHTML = `
    <div id="summary-scroll" style="padding:12px;">
      <table id="summary-table">
        <thead>${thead}</thead>
        <tbody>${tbody}</tbody>
      </table>
    </div>`;

  hideStats();
}

// ── Stats panel ───────────────────────────────────────────────────────────
function showStats(s, xCol, yCol) {
  const panel = document.getElementById("stats-panel");
  panel.style.display = "";

  const rStr = (r, p) => {
    const stars = p < 0.001 ? "***" : p < 0.01 ? "**" : p < 0.05 ? "*" : "ns";
    const sigCls = p < 0.05 ? "sig-yes" : "sig-no";
    const label = p < 0.05 ? "significant" : "not significant";
    return `${r.toFixed(4)} <span class="sig-badge ${sigCls}">${stars} ${label}</span>`;
  };

  const rInterp = (r) => {
    const a = Math.abs(r);
    if (a >= 0.9) return "very strong";
    if (a >= 0.7) return "strong";
    if (a >= 0.5) return "moderate";
    if (a >= 0.3) return "weak";
    return "negligible";
  };

  const dir = s.pearson_r >= 0 ? "positive" : "negative";
  const interp = `${rInterp(s.pearson_r)} ${dir} correlation`;
  const eqSign = s.intercept >= 0 ? "+" : "−";
  const eqLine = `ŷ = ${s.slope.toFixed(4)}·x ${eqSign} ${Math.abs(s.intercept).toFixed(4)}`;

  document.getElementById("stats-grid").innerHTML = `
    <div class="stat-block">
      <div class="stat-label">Pearson r</div>
      <div class="stat-value">${s.pearson_r >= 0 ? "+" : ""}${s.pearson_r.toFixed(3)}</div>
      <div class="stat-sub">${rStr(s.pearson_r, s.pearson_p)}</div>
    </div>
    <div class="stat-block">
      <div class="stat-label">Spearman ρ</div>
      <div class="stat-value">${s.spearman_r >= 0 ? "+" : ""}${s.spearman_r.toFixed(3)}</div>
      <div class="stat-sub">${rStr(s.spearman_r, s.spearman_p)}</div>
    </div>
    <div class="stat-block">
      <div class="stat-label">R²</div>
      <div class="stat-value">${s.r_squared.toFixed(3)}</div>
      <div class="stat-sub">${(s.r_squared * 100).toFixed(1)}% variance explained</div>
    </div>
    <div class="stat-block">
      <div class="stat-label">n</div>
      <div class="stat-value">${s.n.toLocaleString()}</div>
      <div class="stat-sub">data points</div>
    </div>
  `;

  const interpEl = document.getElementById("interpretation");
  interpEl.style.display = "";
  interpEl.textContent = `${xCol} shows a ${interp} with ${yCol} (${eqLine}).`;

  document.getElementById("eq-display").textContent = eqLine;
  document.getElementById("eq-display").style.display = "";
}

function hideStats() {
  document.getElementById("stats-panel").style.display = "none";
  document.getElementById("interpretation").style.display = "none";
  document.getElementById("eq-display").style.display = "none";
}

// ── Chart helpers ─────────────────────────────────────────────────────────
function plotLayout(xTitle, yTitle) {
  return {
    xaxis: { title: { text: xTitle }, gridcolor: "#e8edf2", linecolor: "#d1dbe6", tickfont: { size: 11 } },
    yaxis: { title: { text: yTitle }, gridcolor: "#e8edf2", linecolor: "#d1dbe6", tickfont: { size: 11 } },
    paper_bgcolor: "#ffffff",
    plot_bgcolor: "#ffffff",
    font: { family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", size: 12 },
    margin: { l: 60, r: 30, t: 20, b: 60 },
    legend: { bgcolor: "rgba(255,255,255,0.9)", bordercolor: "#d1dbe6", borderwidth: 1 },
    hoverlabel: { bgcolor: "#0f1923", font: { color: "#fff", size: 12 } },
  };
}

function plotConfig() {
  return {
    responsive: true,
    displayModeBar: true,
    modeBarButtonsToRemove: ["select2d", "lasso2d"],
    displaylogo: false,
  };
}

function setChartTitle(title) {
  const dr = dateRange();
  let suffix = "";
  if (S.info?.date_col && (dr.date_from || dr.date_to)) {
    suffix = ` · ${dr.date_from || "…"} → ${dr.date_to || "…"}`;
  }
  document.getElementById("chart-title-text").textContent = title + suffix;
}

function showEmpty(msg) {
  document.getElementById("chart").innerHTML =
    `<div id="empty-state"><div style="font-size:32px">⛽</div><span>${esc(msg)}</span></div>`;
}

function showLoading() {
  document.getElementById("chart").innerHTML =
    `<div id="empty-state"><div class="spinner"></div><span>Computing…</span></div>`;
}

function clearChart() {
  showEmpty("Click Analyze to render.");
  hideStats();
}

// ── Utilities ─────────────────────────────────────────────────────────────
function val(id) {
  return document.getElementById(id)?.value ?? null;
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
