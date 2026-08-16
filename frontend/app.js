// ============================================================
// M5 RETAIL DEMAND FORECASTING - FRONTEND
// ============================================================
//
// API_URL is empty on purpose. The browser then calls the same
// origin it was served from, so this works identically on
// localhost and on Render. Hardcoding http://127.0.0.1:8000
// breaks every deployment, because "localhost" means the
// VISITOR'S machine, not your server.
// ============================================================

const API_URL = "";

let token = localStorage.getItem("m5_token");
let dashboardData = null;

function authHeaders() {
    return { "Authorization": `Bearer ${token}` };
}

function currentMode() {
    const el = document.getElementById("mode-filter");
    return el ? el.value : "future";
}

function filterQuery() {
    const params = new URLSearchParams();
    params.set("mode", currentMode());
    const map = {
        state: "state-filter",
        store: "store-filter",
        category: "category-filter",
        department: "department-filter",
        item: "item-filter"
    };
    for (const [key, id] of Object.entries(map)) {
        const v = getValue(id);
        if (v) params.set(key, v);
    }
    return params.toString();
}

// ============================================================
// LOGIN
// ============================================================

async function login() {
    const message = document.getElementById("login-message");
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    message.textContent = "";

    if (!username || !password) {
        message.textContent = "Please enter username and password.";
        return;
    }

    try {
        const response = await fetch(`${API_URL}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });
        const data = await response.json();

        if (!response.ok) {
            message.textContent = data.detail || "Invalid username or password.";
            return;
        }

        token = data.token;
        localStorage.setItem("m5_token", token);
        showDashboard(data.username);
    } catch (error) {
        console.error("Login error:", error);
        message.textContent = "Cannot connect to the server.";
    }
}

// ============================================================
// REGISTER
// ============================================================

async function register() {
    const message = document.getElementById("signup-message");
    const uEl = document.getElementById("signup-username");
    const pEl = document.getElementById("signup-password");
    const cEl = document.getElementById("signup-confirm-password");
    if (!uEl || !pEl || !cEl || !message) return;

    const username = uEl.value.trim();
    const password = pEl.value;
    const confirm = cEl.value;
    message.style.color = "";
    message.textContent = "";

    if (!username || !password || !confirm) {
        message.textContent = "Please fill in all fields.";
        return;
    }
    if (username.length < 3) {
        message.textContent = "Username must contain at least 3 characters.";
        return;
    }
    if (password.length < 6) {
        message.textContent = "Password must contain at least 6 characters.";
        return;
    }
    if (password !== confirm) {
        message.textContent = "Passwords do not match.";
        return;
    }

    try {
        const response = await fetch(`${API_URL}/auth/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });
        const data = await response.json();

        if (!response.ok) {
            message.textContent = data.detail || "Could not create account.";
            return;
        }

        message.style.color = "#16a34a";
        message.textContent = "Account created. Logging you in...";
        uEl.value = ""; pEl.value = ""; cEl.value = "";

        // log straight in so the user never sees "invalid credentials"
        document.getElementById("username").value = username;
        document.getElementById("password").value = password;
        setTimeout(login, 600);
    } catch (error) {
        console.error("Registration error:", error);
        message.textContent = "Cannot connect to the server.";
    }
}

// ============================================================
// SESSION
// ============================================================

function showDashboard(username) {
    const loginSection = document.getElementById("login-section");
    const dash = document.getElementById("dashboard-section");
    if (loginSection) loginSection.style.display = "none";
    if (dash) dash.style.display = "flex";
    setText("logged-user", username);
    setText("sidebar-username", username);
    loadDashboard();
}

function logout() {
    localStorage.removeItem("m5_token");
    token = null;
    dashboardData = null;
    const dash = document.getElementById("dashboard-section");
    const loginSection = document.getElementById("login-section");
    if (dash) dash.style.display = "none";
    if (loginSection) loginSection.style.display = "flex";
}

async function checkExistingLogin() {
    if (!token) return;
    try {
        const response = await fetch(`${API_URL}/auth/me`, { headers: authHeaders() });
        if (!response.ok) {
            localStorage.removeItem("m5_token");
            token = null;
            return;
        }
        const data = await response.json();
        showDashboard(data.username);
    } catch (error) {
        console.error("Session check error:", error);
    }
}

// ============================================================
// LOAD DASHBOARD
// ============================================================

async function loadDashboard() {
    await loadMain();
    await loadMetrics();
    await loadHierarchy();
    await loadProfile();
}

// One call returns every aggregate the UI needs (~3 KB), instead of
// downloading 853,720 raw rows (~190 MB) and grouping in the browser.
async function loadMain() {
    if (!token) return;
    try {
        const response = await fetch(`${API_URL}/dashboard?${filterQuery()}`, {
            headers: authHeaders()
        });
        const data = await response.json();
        if (!response.ok) {
            console.error("Dashboard API error:", data);
            return;
        }

        dashboardData = data;

        setText("total-units", formatNumber(data.total_units));
        setText("average-units", formatNumber(data.avg_units_per_day));
        setText("series-count", formatNumber(data.series));
        setText("peak-day", formatNumber(data.peak_day_units));

        if (data.filters) {
            populateSelect("state-filter", data.filters.states);
            populateSelect("store-filter", data.filters.stores);
            populateSelect("category-filter", data.filters.categories);
            populateSelect("department-filter", data.filters.departments);
        }

        createForecastChart(data.daily || []);
        renderBars(document.getElementById("category-chart"), data.by_category || []);
        renderBars(document.getElementById("store-chart"), data.by_store || []);
        createTopItemsTable(data.top_items || []);
    } catch (error) {
        console.error("Dashboard error:", error);
    }
}

async function loadMetrics() {
    if (!token) return;
    try {
        const response = await fetch(`${API_URL}/metrics?mode=validation`, {
            headers: authHeaders()
        });
        const data = await response.json();
        if (!response.ok) return;
        const m = data.metrics || {};
        setText("wrmsse", formatNumber(m.wrmsse));
        setText("rmse", formatNumber(m.rmse));
        setText("mae", formatNumber(m.mae));
        setText("mape", formatNumber(m.mape));
    } catch (error) {
        console.error("Metrics error:", error);
    }
}

async function loadHierarchy() {
    if (!token) return;
    try {
        const response = await fetch(`${API_URL}/hierarchy?mode=${currentMode()}`, {
            headers: authHeaders()
        });
        const data = await response.json();
        if (!response.ok) return;
        createHierarchyCards(data);
        await loadHierarchySummary();
    } catch (error) {
        console.error("Hierarchy error:", error);
    }
}

async function loadHierarchySummary() {
    try {
        const response = await fetch(
            `${API_URL}/hierarchy/summary?mode=${currentMode()}`,
            { headers: authHeaders() }
        );
        const data = await response.json();
        if (!response.ok) return;

        const container = document.getElementById("hierarchy-table");
        if (!container) return;

        let html = `<table><thead><tr>
            <th>Level</th><th>Dimensions</th>
            <th>Series / Groups</th><th>Top Forecast</th>
        </tr></thead><tbody>`;

        (data.levels || []).forEach(level => {
            const top = level.data && level.data.length
                ? level.data[0].forecast : undefined;
            html += `<tr>
                <td><strong>${escapeHTML(level.level)}</strong></td>
                <td>${level.columns && level.columns.length
                    ? level.columns.map(c => escapeHTML(String(c))).join(" × ")
                    : "All"}</td>
                <td>${formatNumber(level.count)}</td>
                <td>${top !== undefined ? formatNumber(top) : "—"}</td>
            </tr>`;
        });

        container.innerHTML = html + "</tbody></table>";
    } catch (error) {
        console.error("Hierarchy summary error:", error);
    }
}

async function loadProfile() {
    if (!token) return;
    try {
        const response = await fetch(`${API_URL}/data-profile?mode=${currentMode()}`, {
            headers: authHeaders()
        });
        const data = await response.json();
        if (!response.ok) return;
        const f = (data.profile && data.profile.external_features) || {};
        setText("price-status", f.price
            ? "Price information is available in the forecast data."
            : "Price is used as a model feature but is not present in the exported forecast table.");
        setText("promotion-status", f.promotion
            ? "Promotion information is available."
            : "Promotion is captured via price-relative features during training.");
        setText("holiday-status", f.holiday
            ? "Holiday/event information is available."
            : "Holiday and SNAP events are used during training as model features.");
    } catch (error) {
        console.error("Profile error:", error);
    }
}

// ============================================================
// FILTERS
// ============================================================

function populateSelect(id, values) {
    const select = document.getElementById(id);
    if (!select || !values) return;
    const current = select.value;
    const first = select.options[0] ? select.options[0].outerHTML : "";
    select.innerHTML = first;
    values.forEach(value => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
    });
    if (values.some(v => String(v) === String(current))) select.value = current;
}

// Filtering now happens server-side: just refetch.
async function applyFilters() {
    await loadMain();
}

// ============================================================
// CHARTS
// ============================================================

function createForecastChart(daily) {
    const container = document.getElementById("forecast-chart");
    if (!container) return;

    const dates = daily.map(d => String(d.date).substring(0, 10));
    const values = daily.map(d => Number(d.forecast) || 0);

    if (!dates.length) {
        container.innerHTML =
            `<div class="chart-placeholder"><span>📈</span>No forecast data available.</div>`;
        return;
    }

    const width = 1100, height = 420;
    const leftPad = 80, rightPad = 35, topPad = 35, bottomPad = 70;
    const uw = width - leftPad - rightPad;
    const uh = height - topPad - bottomPad;
    const max = Math.max(...values), min = Math.min(...values);
    const range = Math.max(max - min, 1);

    const points = values.map((value, i) => ({
        x: leftPad + (i / Math.max(dates.length - 1, 1)) * uw,
        y: topPad + uh - ((value - min) / range) * uh
    }));

    let grid = "";
    for (let i = 0; i <= 5; i++) {
        const ratio = i / 5;
        const y = topPad + uh - ratio * uh;
        grid += `<line x1="${leftPad}" y1="${y}" x2="${width - rightPad}" y2="${y}"
                 stroke="#e5e7eb" stroke-width="1"/>
                 <text x="${leftPad - 10}" y="${y + 4}" text-anchor="end"
                 font-size="12" fill="#667085">${formatNumber(min + ratio * range)}</text>`;
    }

    let labels = "";
    points.forEach((p, i) => {
        if (i !== 0 && i !== points.length - 1 && i % 4 !== 0) return;
        labels += `<text x="${p.x}" y="${height - 30}" text-anchor="middle"
                   font-size="12" fill="#667085">${dates[i]}</text>`;
    });

    const circles = points.map((p, i) =>
        `<circle cx="${p.x}" cy="${p.y}" r="5" fill="#3264d6" stroke="white"
         stroke-width="2"><title>${dates[i]} — ${formatNumber(values[i])} units</title></circle>`
    ).join("");

    container.innerHTML = `<svg viewBox="0 0 ${width} ${height}" width="100%" height="420">
        ${grid}
        <line x1="${leftPad}" y1="${topPad}" x2="${leftPad}" y2="${height - bottomPad}"
              stroke="#98a2b3" stroke-width="1.5"/>
        <line x1="${leftPad}" y1="${height - bottomPad}" x2="${width - rightPad}"
              y2="${height - bottomPad}" stroke="#98a2b3" stroke-width="1.5"/>
        <polyline points="${points.map(p => `${p.x},${p.y}`).join(" ")}" fill="none"
              stroke="#3264d6" stroke-width="4" stroke-linecap="round"
              stroke-linejoin="round"/>
        ${circles}${labels}
        <text x="${width / 2}" y="${height - 5}" text-anchor="middle" font-size="14"
              font-weight="600" fill="#344054">Date</text>
        <text x="18" y="${height / 2}" text-anchor="middle" font-size="14"
              font-weight="600" fill="#344054"
              transform="rotate(-90 18 ${height / 2})">Forecasted Units</text>
    </svg>`;
}

function renderBars(container, rows) {
    if (!container) return;
    if (!rows.length) {
        container.innerHTML = `<div class="chart-placeholder">No data available.</div>`;
        return;
    }
    const entries = rows.slice(0, 10);
    const max = Math.max(...entries.map(e => Number(e.forecast) || 0));
    container.innerHTML = entries.map(e => {
        const value = Number(e.forecast) || 0;
        const width = max > 0 ? (value / max) * 100 : 0;
        return `<div style="margin-bottom:16px;">
            <div style="display:flex;justify-content:space-between;
                        margin-bottom:6px;font-size:13px;">
                <span>${escapeHTML(String(e.name))}</span>
                <strong>${formatNumber(value)}</strong>
            </div>
            <div style="height:10px;background:#edf1f7;border-radius:10px;overflow:hidden;">
                <div style="width:${width}%;height:100%;background:#3264d6;
                            border-radius:10px;"></div>
            </div>
        </div>`;
    }).join("");
}

function createHierarchyCards(data) {
    const container = document.getElementById("hierarchy-cards");
    if (!container) return;
    const cards = [
        { icon: "🇺🇸", title: "States", values: data.states || [] },
        { icon: "🏪", title: "Stores", values: data.stores || [] },
        { icon: "🛒", title: "Categories", values: data.categories || [] },
        { icon: "🏷️", title: "Departments", values: data.departments || [] }
    ];
    container.innerHTML = cards.map(card => `
        <div class="hierarchy-card">
            <div class="icon">${card.icon}</div>
            <h3>${escapeHTML(card.title)}</h3>
            <p>${card.values.length
                ? card.values.slice(0, 12).map(v => escapeHTML(String(v))).join(" · ")
                : "No data available"}</p>
            <strong>${card.values.length} ${card.values.length === 1 ? "value" : "values"}</strong>
        </div>`).join("");
}

function createTopItemsTable(items) {
    const container = document.getElementById("top-items");
    if (!container) return;
    if (!items.length) {
        container.innerHTML = "<p>No forecast items available.</p>";
        return;
    }
    let html = `<table><thead><tr><th>#</th><th>Item</th><th>Forecast</th></tr></thead><tbody>`;
    items.forEach((item, i) => {
        html += `<tr><td>${i + 1}</td>
                 <td>${escapeHTML(String(item.id))}</td>
                 <td>${formatNumber(item.forecast)}</td></tr>`;
    });
    container.innerHTML = html + "</tbody></table>";
}

// ============================================================
// SERIES SEARCH  (server-side)
// ============================================================

async function searchSeries() {
    const input = document.getElementById("series-search");
    const container = document.getElementById("series-results");
    if (!input || !container) return;

    container.innerHTML = "<p>Searching...</p>";
    try {
        const response = await fetch(
            `${API_URL}/series/search?q=${encodeURIComponent(input.value.trim())}` +
            `&mode=${currentMode()}`,
            { headers: authHeaders() }
        );
        const data = await response.json();
        if (!response.ok) {
            container.innerHTML = "<p>Search failed.</p>";
            return;
        }
        const rows = data.data || [];
        if (!rows.length) {
            container.innerHTML = "<p>No matching series found.</p>";
            return;
        }
        let html = `<p>${formatNumber(data.matches)} matching rows —
                    showing first ${rows.length}.</p>
                    <table><thead><tr><th>Series</th><th>Store</th>
                    <th>Date</th><th>Forecast</th></tr></thead><tbody>`;
        rows.forEach(row => {
            html += `<tr>
                <td>${escapeHTML(String(row.id ?? "—"))}</td>
                <td>${escapeHTML(String(row.store_id ?? "—"))}</td>
                <td>${escapeHTML(String(row.date ?? "—")).substring(0, 10)}</td>
                <td>${formatNumber(row.forecast)}</td></tr>`;
        });
        container.innerHTML = html + "</tbody></table>";
    } catch (error) {
        console.error("Search error:", error);
        container.innerHTML = "<p>Cannot connect to the server.</p>";
    }
}

// ============================================================
// EXPORT  (streamed from the server, not built in the browser)
// ============================================================

function exportForecast() {
    if (!token) return;
    const url = `${API_URL}/export?${filterQuery()}`;
    fetch(url, { headers: authHeaders() })
        .then(r => {
            if (!r.ok) throw new Error("Export failed");
            return r.blob();
        })
        .then(blob => {
            const link = document.createElement("a");
            link.href = URL.createObjectURL(blob);
            link.download = `m5_forecast_${currentMode()}.csv`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(link.href);
        })
        .catch(err => {
            console.error(err);
            alert("Could not export forecast.");
        });
}

// ============================================================
// TABS
// ============================================================

function showTab(tabId, button) {
    document.querySelectorAll(".tab-content")
        .forEach(tab => tab.classList.remove("active-tab"));
    const tab = document.getElementById(tabId);
    if (tab) tab.classList.add("active-tab");
    document.querySelectorAll(".nav-item")
        .forEach(item => item.classList.remove("active"));
    if (button) button.classList.add("active");
}

// ============================================================
// HELPERS
// ============================================================

function formatNumber(value) {
    if (value === undefined || value === null || Number.isNaN(Number(value))) {
        return "—";
    }
    return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function getValue(id) {
    const el = document.getElementById(id);
    return el ? el.value : "";
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function escapeHTML(value) {
    return String(value)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

// ============================================================
// EVENTS
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
    ["state-filter", "store-filter", "category-filter",
     "department-filter", "item-filter"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener("change", applyFilters);
    });

    const modeFilter = document.getElementById("mode-filter");
    if (modeFilter) modeFilter.addEventListener("change", loadDashboard);

    const passwordInput = document.getElementById("password");
    if (passwordInput) {
        passwordInput.addEventListener("keydown", e => {
            if (e.key === "Enter") login();
        });
    }

    const signupConfirm = document.getElementById("signup-confirm-password");
    if (signupConfirm) {
        signupConfirm.addEventListener("keydown", e => {
            if (e.key === "Enter") register();
        });
    }

    const search = document.getElementById("series-search");
    if (search) {
        search.addEventListener("keydown", e => {
            if (e.key === "Enter") searchSeries();
        });
    }

    checkExistingLogin();
});
