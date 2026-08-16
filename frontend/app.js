// ============================================================
// M5 RETAIL DEMAND FORECASTING - FRONTEND
// ============================================================
// API_URL is empty so the browser calls whatever origin served
// the page. Hardcoding localhost breaks every deployment.
// ============================================================

const API_URL = "";

let overviewData = null;
let dashboardData = null;
let loadedTabs = new Set();

function currentMode() {
    const el = document.getElementById("mode-filter");
    return el ? el.value : "future";
}

function filterQuery() {
    const p = new URLSearchParams();
    p.set("mode", currentMode());
    const map = { state: "state-filter", store: "store-filter",
                  category: "category-filter", department: "department-filter",
                  item: "item-filter" };
    for (const [k, id] of Object.entries(map)) {
        const v = getValue(id);
        if (v) p.set(k, v);
    }
    return p.toString();
}

async function api(path) {
    const r = await fetch(`${API_URL}${path}`);
    if (!r.ok) throw new Error(`${path} → ${r.status}`);
    return r.json();
}

// ============================================================
// OVERVIEW
// ============================================================

async function loadOverview() {
    try {
        const d = await api("/overview");
        overviewData = d;
        const s = d.dataset;

        setText("sidebar-wrmsse",
            d.wrmsse ? Number(d.wrmsse).toFixed(4) : "—");

        document.getElementById("overview-stats").innerHTML = [
            ["🔢", "Time Series", formatNumber(s.series)],
            ["📦", "Unique Items", formatNumber(s.items)],
            ["🏪", "Stores", s.stores],
            ["🇺🇸", "States", s.states],
            ["🛒", "Categories", s.categories],
            ["🏷️", "Departments", s.departments],
            ["📅", "Days of History", formatNumber(s.history_days)],
            ["🎯", "Forecast Horizon", s.horizon_days + " days"]
        ].map(([icon, label, value]) => `
            <div class="stat-card">
              <div class="stat-icon">${icon}</div>
              <span>${label}</span>
              <strong>${value}</strong>
            </div>`).join("");

        const sbs = d.stores_by_state || {};
        document.getElementById("states-breakdown").innerHTML =
            Object.keys(sbs).map(state => `
              <div class="breakdown-row">
                <div class="breakdown-label">
                  <strong>${escapeHTML(state)}</strong>
                  <span>${sbs[state].length} stores</span>
                </div>
                <div class="chip-row">
                  ${sbs[state].map(s2 =>
                    `<span class="chip">${escapeHTML(s2)}</span>`).join("")}
                </div>
              </div>`).join("");

        const dbc = d.departments_by_category || {};
        document.getElementById("category-breakdown").innerHTML =
            Object.keys(dbc).map(cat => `
              <div class="breakdown-row">
                <div class="breakdown-label">
                  <strong>${escapeHTML(cat)}</strong>
                  <span>${dbc[cat].length} departments</span>
                </div>
                <div class="chip-row">
                  ${dbc[cat].map(x =>
                    `<span class="chip">${escapeHTML(x)}</span>`).join("")}
                </div>
              </div>`).join("");

        renderBars(document.getElementById("overview-category-chart"),
                   d.category_volume || []);

        document.getElementById("windows-table").innerHTML = `
          <table><thead><tr>
            <th>Window</th><th>Dates</th><th>Scoreable</th>
          </tr></thead><tbody>
          ${(d.windows || []).map(w => `
            <tr>
              <td><strong>${escapeHTML(w.mode)}</strong></td>
              <td>${w.first_date || "—"} → ${w.last_date || "—"}</td>
              <td>${w.scoreable
                    ? '<span class="badge-ok">Yes — WRMSSE</span>'
                    : '<span class="badge-no">No ground truth</span>'}</td>
            </tr>`).join("")}
          </tbody></table>`;

        const m = d.model || {};
        document.getElementById("model-info").innerHTML = `
          <div class="info-list">
            <div><span>Algorithm</span><strong>${escapeHTML(m.algorithm || "")}</strong></div>
            <div><span>Objective</span><strong>${escapeHTML(m.objective || "")}</strong></div>
            <div><span>Features</span><strong>${m.features || "—"}</strong></div>
            <div><span>Approach</span><strong>${escapeHTML(m.approach || "")}</strong></div>
            <div><span>Accuracy</span><strong>WRMSSE ${
              d.wrmsse ? Number(d.wrmsse).toFixed(4) : "—"}</strong></div>
          </div>`;
    } catch (e) {
        console.error("Overview error:", e);
    }
}

// ============================================================
// FORECAST
// ============================================================

async function loadMain() {
    try {
        const d = await api(`/dashboard?${filterQuery()}`);
        dashboardData = d;

        setText("total-units", formatNumber(d.total_units));
        setText("average-units", formatNumber(d.avg_units_per_day));
        setText("series-count", formatNumber(d.series));
        setText("peak-day", formatNumber(d.peak_day_units));
        setText("window-label",
            d.first_date ? `${d.first_date} → ${d.last_date}` : d.mode);

        if (d.filters) {
            populateSelect("state-filter", d.filters.states);
            populateSelect("store-filter", d.filters.stores);
            populateSelect("category-filter", d.filters.categories);
            populateSelect("department-filter", d.filters.departments);
            populateSelect("item-filter", d.filters.items);
            const hint = document.getElementById("item-count-hint");
            if (hint) {
                const n = d.filters.item_count || 0;
                hint.textContent = n ? `(${formatNumber(n)})` : "";
            }
        }

        createLineChart("forecast-chart", d.daily || [],
                        "date", "forecast", "Forecasted Units");
        renderBars(document.getElementById("category-chart"), d.by_category || []);
        renderBars(document.getElementById("store-chart"), d.by_store || []);

        const items = d.top_items || [];
        document.getElementById("top-items").innerHTML = items.length
          ? `<table><thead><tr><th>#</th><th>Item</th><th>Store</th>
             <th>28-day Forecast</th></tr></thead><tbody>
             ${items.map((it, i) => `<tr>
               <td>${i + 1}</td>
               <td>${escapeHTML(String(it.item_id))}</td>
               <td>${escapeHTML(String(it.store_id))}</td>
               <td>${formatNumber(it.forecast)}</td></tr>`).join("")}
             </tbody></table>`
          : "<p>No data.</p>";
    } catch (e) {
        console.error("Dashboard error:", e);
    }
}

// ============================================================
// HIERARCHY
// ============================================================

async function loadHierarchy() {
    try {
        const d = await api(`/hierarchy?mode=${currentMode()}`);
        const o = overviewData || {};

        document.getElementById("hierarchy-cards").innerHTML = [
            { icon: "🇺🇸", title: "States", values: o.states || [] },
            { icon: "🏪", title: "Stores", values: o.stores || [] },
            { icon: "🛒", title: "Categories", values: o.categories || [] },
            { icon: "🏷️", title: "Departments", values: o.departments || [] }
        ].map(c => `
            <div class="hierarchy-card">
              <div class="icon">${c.icon}</div>
              <h3>${escapeHTML(c.title)}</h3>
              <p>${c.values.length
                   ? c.values.slice(0, 12).map(v => escapeHTML(String(v))).join(" · ")
                   : "—"}</p>
              <strong>${c.values.length} values</strong>
            </div>`).join("");

        document.getElementById("hierarchy-table").innerHTML = `
          <table><thead><tr>
            <th>Level</th><th>Grouped by</th><th>Series</th>
            <th>Largest node</th><th>Forecast</th>
          </tr></thead><tbody>
          ${(d.levels || []).map(l => {
            const top = l.data && l.data.length ? l.data[0] : null;
            return `<tr>
              <td><strong>${escapeHTML(l.level)}</strong></td>
              <td>${l.columns && l.columns.length
                    ? l.columns.map(c => escapeHTML(c)).join(" × ") : "All"}</td>
              <td>${formatNumber(l.count)}</td>
              <td>${top ? escapeHTML(String(top.name)) : "—"}</td>
              <td>${top ? formatNumber(top.forecast) : "—"}</td>
            </tr>`;
          }).join("")}
          </tbody></table>`;
    } catch (e) {
        console.error("Hierarchy error:", e);
    }
}

// ============================================================
// ACCURACY
// ============================================================

async function loadAccuracy() {
    try {
        const d = await api(`/accuracy?mode=${currentMode()}`);
        const body = document.getElementById("accuracy-body");
        let html = "";

        if (d.wrmsse !== null && d.wrmsse !== undefined) {
            html += `<div class="kpi-grid">
              <div class="kpi-card"><div class="kpi-icon">🎯</div>
                <div><span>WRMSSE (measured)</span>
                <strong>${Number(d.wrmsse).toFixed(4)}</strong></div></div>
              <div class="kpi-card"><div class="kpi-icon">🏆</div>
                <div><span>M5 winner</span><strong>0.520</strong></div></div>
              <div class="kpi-card"><div class="kpi-icon">📊</div>
                <div><span>Levels scored</span>
                <strong>${(d.levels || []).length}</strong></div></div>
            </div>`;
        } else {
            html += `<div class="notice">${escapeHTML(d.message || "")}</div>`;
            if (d.backtest) {
                html += `<div class="kpi-grid">
                  <div class="kpi-card"><div class="kpi-icon">🔬</div>
                    <div><span>Expected WRMSSE</span>
                    <strong>${Number(d.backtest.mean_wrmsse).toFixed(4)}</strong></div></div>
                  <div class="kpi-card"><div class="kpi-icon">📐</div>
                    <div><span>Std deviation</span>
                    <strong>±${Number(d.backtest.std_wrmsse).toFixed(4)}</strong></div></div>
                  <div class="kpi-card"><div class="kpi-icon">🔁</div>
                    <div><span>Backtest origins</span>
                    <strong>${d.backtest.n_origins}</strong></div></div>
                </div>
                <div class="notice ok">
                  Estimated by re-running the identical task
                  (${escapeHTML(d.backtest.task)}) at
                  ${d.backtest.n_origins} earlier points in history where
                  actual sales do exist.
                </div>`;
            }
        }

        if ((d.levels || []).length) {
            html += `<section class="dashboard-card">
              <div class="card-header"><div>
                <h2>RMSSE by Hierarchy Level</h2>
                <p>Lower is better. Higher levels are easier to forecast.</p>
              </div></div>
              <table><thead><tr>
                <th>Level</th><th>Series</th><th>RMSSE</th>
                <th>MAE</th><th>Bias %</th>
              </tr></thead><tbody>
              ${d.levels.map(l => `<tr>
                <td><strong>${escapeHTML(l.level)}</strong></td>
                <td>${formatNumber(l.n_series)}</td>
                <td>${l.rmsse !== undefined ? Number(l.rmsse).toFixed(4) : "—"}</td>
                <td>${l.mae !== undefined ? formatNumber(l.mae) : "—"}</td>
                <td>${l.bias_pct !== undefined
                      ? Number(l.bias_pct).toFixed(2) + "%" : "—"}</td>
              </tr>`).join("")}
              </tbody></table></section>`;
        }
        body.innerHTML = html;

        const feats = d.features || [];
        const fc = document.getElementById("feature-chart");
        if (feats.length) {
            const key = feats[0].gain !== undefined ? "gain" : "importance";
            renderBars(fc, feats.map(f => ({
                name: f.feature, forecast: f[key]
            })), 20);
        } else {
            fc.innerHTML = "<p>No feature importance available.</p>";
        }
    } catch (e) {
        console.error("Accuracy error:", e);
    }
}

// ============================================================
// EVENTS
// ============================================================

async function loadEvents() {
    try {
        const d = await api(`/events?mode=${currentMode()}`);

        const ev = d.events || [];
        document.getElementById("events-table").innerHTML = ev.length
          ? `<table><thead><tr><th>Date</th><th>Event</th><th>Type</th>
             <th>Forecast</th><th>vs normal day</th></tr></thead><tbody>
             ${ev.map(e => `<tr>
               <td>${String(e.date).substring(0, 10)}</td>
               <td><strong>${escapeHTML(e.event)}</strong></td>
               <td>${escapeHTML(e.type || "—")}</td>
               <td>${formatNumber(e.forecast)}</td>
               <td class="${e.vs_normal_pct >= 0 ? 'pos' : 'neg'}">
                 ${e.vs_normal_pct !== null
                   ? (e.vs_normal_pct >= 0 ? "+" : "") +
                      e.vs_normal_pct.toFixed(1) + "%" : "—"}</td>
             </tr>`).join("")}</tbody></table>`
          : "<p>No calendar events fall inside this window.</p>";

        const snap = d.snap || [];
        document.getElementById("snap-table").innerHTML = snap.length
          ? `<table><thead><tr><th>State</th><th>SNAP day</th>
             <th>Normal day</th><th>Uplift</th></tr></thead><tbody>
             ${snap.map(s => `<tr>
               <td><strong>${escapeHTML(s.state)}</strong></td>
               <td>${formatNumber(s.snap_day)}</td>
               <td>${formatNumber(s.non_snap_day)}</td>
               <td class="${s.uplift_pct >= 0 ? 'pos' : 'neg'}">
                 ${(s.uplift_pct >= 0 ? "+" : "") +
                    s.uplift_pct.toFixed(1)}%</td>
             </tr>`).join("")}</tbody></table>`
          : "<p>No SNAP data.</p>";

        renderBars(document.getElementById("weekly-chart"),
            (d.weekly_profile || []).map(w => ({
                name: w.day, forecast: w.forecast
            })), 7, false);

        createScatter("price-chart", d.price_points || []);
    } catch (e) {
        console.error("Events error:", e);
    }
}

// ============================================================
// SERIES EXPLORER
// ============================================================

async function searchSeries() {
    const input = document.getElementById("series-search");
    const box = document.getElementById("series-results");
    if (!input) return;
    const q = input.value.trim();
    if (!q) { box.innerHTML = "<p>Enter a search term.</p>"; return; }

    box.innerHTML = "<p>Searching…</p>";
    try {
        const d = await api(
            `/series/search?q=${encodeURIComponent(q)}&mode=${currentMode()}`);
        const rows = d.data || [];
        if (!rows.length) { box.innerHTML = "<p>No matching series.</p>"; return; }

        box.innerHTML = `<p>${formatNumber(d.matches)} series matched —
            showing top ${rows.length}. Click a row for detail.</p>
            <table><thead><tr><th>Series</th><th>28-day total</th>
            <th>Avg/day</th><th>Peak</th></tr></thead><tbody>
            ${rows.map(r => `<tr class="clickable"
              onclick="showSeriesDetail('${escapeHTML(String(r.id))}')">
              <td>${escapeHTML(String(r.id))}</td>
              <td>${formatNumber(r.total)}</td>
              <td>${formatNumber(r.avg)}</td>
              <td>${formatNumber(r.peak)}</td></tr>`).join("")}
            </tbody></table>`;
    } catch (e) {
        console.error("Search error:", e);
        box.innerHTML = "<p>Search failed.</p>";
    }
}

async function showSeriesDetail(id) {
    try {
        const d = await api(
            `/series/detail?series_id=${encodeURIComponent(id)}&mode=${currentMode()}`);
        document.getElementById("series-detail-card").style.display = "block";
        setText("series-detail-title", id);

        const hist = (d.history || []).map(h => ({
            date: h.date, forecast: h.sales, kind: "history"
        }));
        const fc = (d.forecast || []).map(f => ({
            date: f.date, forecast: f.forecast, kind: "forecast"
        }));
        createLineChart("series-detail-chart", hist.concat(fc),
                        "date", "forecast", "Units", true);
        document.getElementById("series-detail-card")
                .scrollIntoView({ behavior: "smooth" });
    } catch (e) {
        console.error("Detail error:", e);
    }
}

// ============================================================
// EXPORT
// ============================================================

function exportForecast(fmt) {
    window.location = `${API_URL}/export?${filterQuery()}&fmt=${fmt}`;
}

// ============================================================
// CHARTS
// ============================================================

function createLineChart(containerId, rows, xKey, yKey, yLabel, split) {
    const el = document.getElementById(containerId);
    if (!el) return;
    if (!rows.length) {
        el.innerHTML = `<div class="chart-placeholder"><span>📈</span>
                        No data available.</div>`;
        return;
    }

    const labels = rows.map(r => String(r[xKey]).substring(0, 10));
    const values = rows.map(r => Number(r[yKey]) || 0);

    const W = 1100, H = 420, L = 85, R = 35, T = 30, B = 70;
    const uw = W - L - R, uh = H - T - B;
    const max = Math.max(...values), min = Math.min(...values);
    const range = Math.max(max - min, 1);

    const pts = values.map((v, i) => ({
        x: L + (i / Math.max(values.length - 1, 1)) * uw,
        y: T + uh - ((v - min) / range) * uh,
        kind: rows[i].kind
    }));

    let grid = "";
    for (let i = 0; i <= 5; i++) {
        const y = T + uh - (i / 5) * uh;
        grid += `<line x1="${L}" y1="${y}" x2="${W - R}" y2="${y}"
                 stroke="#e5e7eb"/>
                 <text x="${L - 10}" y="${y + 4}" text-anchor="end"
                 font-size="12" fill="#667085">
                 ${formatNumber(min + (i / 5) * range)}</text>`;
    }

    let xlab = "";
    pts.forEach((p, i) => {
        const step = Math.ceil(pts.length / 8);
        if (i % step !== 0 && i !== pts.length - 1) return;
        xlab += `<text x="${p.x}" y="${H - 30}" text-anchor="middle"
                 font-size="11" fill="#667085">${labels[i]}</text>`;
    });

    let paths = "";
    if (split) {
        const hp = pts.filter(p => p.kind === "history");
        const fp = pts.filter(p => p.kind === "forecast");
        if (hp.length) paths += `<polyline points="${
            hp.map(p => `${p.x},${p.y}`).join(" ")}" fill="none"
            stroke="#94a3b8" stroke-width="2.5"/>`;
        if (fp.length) {
            const join = hp.length ? [hp[hp.length - 1], ...fp] : fp;
            paths += `<polyline points="${
              join.map(p => `${p.x},${p.y}`).join(" ")}" fill="none"
              stroke="#3264d6" stroke-width="4" stroke-linecap="round"/>`;
        }
    } else {
        paths = `<polyline points="${pts.map(p => `${p.x},${p.y}`).join(" ")}"
                 fill="none" stroke="#3264d6" stroke-width="4"
                 stroke-linecap="round" stroke-linejoin="round"/>`;
    }

    const dots = pts.map((p, i) =>
        `<circle cx="${p.x}" cy="${p.y}" r="${split ? 3 : 5}"
         fill="${p.kind === "history" ? "#94a3b8" : "#3264d6"}"
         stroke="white" stroke-width="1.5">
         <title>${labels[i]} — ${formatNumber(values[i])}</title></circle>`
    ).join("");

    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="420">
        ${grid}
        <line x1="${L}" y1="${T}" x2="${L}" y2="${H - B}" stroke="#98a2b3"/>
        <line x1="${L}" y1="${H - B}" x2="${W - R}" y2="${H - B}" stroke="#98a2b3"/>
        ${paths}${dots}${xlab}
        <text x="${W / 2}" y="${H - 6}" text-anchor="middle" font-size="13"
              font-weight="600" fill="#344054">Date</text>
        <text x="20" y="${H / 2}" text-anchor="middle" font-size="13"
              font-weight="600" fill="#344054"
              transform="rotate(-90 20 ${H / 2})">${yLabel}</text>
    </svg>`;
}

function renderBars(container, rows, limit, sort) {
    if (!container) return;
    if (!rows || !rows.length) {
        container.innerHTML = `<div class="chart-placeholder">No data.</div>`;
        return;
    }
    let entries = rows.slice(0, limit || 10);
    if (sort !== false) {
        entries = [...entries].sort((a, b) =>
            (Number(b.forecast) || 0) - (Number(a.forecast) || 0));
    }
    const max = Math.max(...entries.map(e => Number(e.forecast) || 0));
    container.innerHTML = entries.map(e => {
        const v = Number(e.forecast) || 0;
        return `<div class="bar-row">
            <div class="bar-head">
              <span>${escapeHTML(String(e.name))}</span>
              <strong>${formatNumber(v)}</strong>
            </div>
            <div class="bar-track">
              <div class="bar-fill" style="width:${
                max > 0 ? (v / max) * 100 : 0}%"></div>
            </div>
          </div>`;
    }).join("");
}

function createScatter(containerId, points) {
    const el = document.getElementById(containerId);
    if (!el) return;
    if (!points.length) {
        el.innerHTML = `<div class="chart-placeholder">
                        No price data available.</div>`;
        return;
    }
    const W = 1000, H = 340, L = 80, R = 30, T = 25, B = 55;
    const uw = W - L - R, uh = H - T - B;
    const xs = points.map(p => Number(p.sell_price) || 0);
    const ys = points.map(p => Number(p.forecast) || 0);
    const xmax = Math.max(...xs), ymax = Math.max(...ys);

    const dots = points.map(p => {
        const x = L + ((Number(p.sell_price) || 0) / (xmax || 1)) * uw;
        const y = T + uh - ((Number(p.forecast) || 0) / (ymax || 1)) * uh;
        return `<circle cx="${x}" cy="${y}" r="4" fill="#0ea5e9"
                opacity="0.55"><title>${escapeHTML(String(p.item_id))} @ ${
                escapeHTML(String(p.store_id))}
                $${Number(p.sell_price).toFixed(2)} —
                ${formatNumber(p.forecast)} units</title></circle>`;
    }).join("");

    let grid = "";
    for (let i = 0; i <= 4; i++) {
        const y = T + uh - (i / 4) * uh;
        grid += `<line x1="${L}" y1="${y}" x2="${W - R}" y2="${y}"
                 stroke="#eef1f5"/>
                 <text x="${L - 8}" y="${y + 4}" text-anchor="end"
                 font-size="11" fill="#667085">
                 ${formatNumber((i / 4) * ymax)}</text>`;
    }
    let xl = "";
    for (let i = 0; i <= 5; i++) {
        const x = L + (i / 5) * uw;
        xl += `<text x="${x}" y="${H - 28}" text-anchor="middle"
               font-size="11" fill="#667085">
               $${((i / 5) * xmax).toFixed(1)}</text>`;
    }

    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="340">
        ${grid}
        <line x1="${L}" y1="${T}" x2="${L}" y2="${H - B}" stroke="#98a2b3"/>
        <line x1="${L}" y1="${H - B}" x2="${W - R}" y2="${H - B}" stroke="#98a2b3"/>
        ${dots}${xl}
        <text x="${W / 2}" y="${H - 6}" text-anchor="middle" font-size="12"
              font-weight="600" fill="#344054">Sell price (USD)</text>
        <text x="18" y="${H / 2}" text-anchor="middle" font-size="12"
              font-weight="600" fill="#344054"
              transform="rotate(-90 18 ${H / 2})">28-day forecast</text>
    </svg>`;
}

// ============================================================
// TABS & FILTERS
// ============================================================

const TAB_LOADERS = {
    "forecast-tab": loadMain,
    "hierarchy-tab": loadHierarchy,
    "accuracy-tab": loadAccuracy,
    "events-tab": loadEvents,
};

function showTab(tabId, button) {
    document.querySelectorAll(".tab-content")
        .forEach(t => t.classList.remove("active-tab"));
    const tab = document.getElementById(tabId);
    if (tab) tab.classList.add("active-tab");

    document.querySelectorAll(".nav-item")
        .forEach(i => i.classList.remove("active"));
    if (button) button.classList.add("active");

    // filters apply to every tab except the overview
    const fp = document.getElementById("filter-panel");
    if (fp) fp.style.display = tabId === "overview-tab" ? "none" : "block";

    if (TAB_LOADERS[tabId] && !loadedTabs.has(tabId)) {
        loadedTabs.add(tabId);
        TAB_LOADERS[tabId]();
    }
}

function populateSelect(id, values) {
    const sel = document.getElementById(id);
    if (!sel || !values) return;
    const current = sel.value;
    const first = sel.options[0] ? sel.options[0].outerHTML : "";
    sel.innerHTML = first;
    values.forEach(v => {
        const o = document.createElement("option");
        o.value = v; o.textContent = v;
        sel.appendChild(o);
    });
    if (values.some(v => String(v) === String(current))) sel.value = current;
}

function resetFilters() {
    ["state-filter", "store-filter", "category-filter", "department-filter",
     "item-filter"]
        .forEach(id => { const el = document.getElementById(id);
                         if (el) el.value = ""; });
    refreshAll();
}

function refreshAll() {
    loadedTabs.clear();
    const active = document.querySelector(".tab-content.active-tab");
    const id = active ? active.id : "forecast-tab";
    if (TAB_LOADERS[id]) { loadedTabs.add(id); TAB_LOADERS[id](); }
}

// ============================================================
// HELPERS
// ============================================================

function formatNumber(v) {
    if (v === undefined || v === null || Number.isNaN(Number(v))) return "—";
    return Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
}
function getValue(id) { const e = document.getElementById(id); return e ? e.value : ""; }
function setText(id, v) { const e = document.getElementById(id); if (e) e.textContent = v; }
function escapeHTML(v) {
    return String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;")
        .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

// ============================================================
// START
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
    ["state-filter", "store-filter", "category-filter", "department-filter",
     "item-filter"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener("change", refreshAll);
    });

    const mode = document.getElementById("mode-filter");
    if (mode) mode.addEventListener("change", refreshAll);

    const search = document.getElementById("series-search");
    if (search) search.addEventListener("keydown", e => {
        if (e.key === "Enter") searchSeries();
    });

    loadOverview();
    loadMain();          // preload so the Forecast tab is instant
    loadedTabs.add("forecast-tab");
});
