// ============================================================
// M5 RETAIL DEMAND FORECASTING
// FRONTEND JAVASCRIPT
// ============================================================

// Use the same server for both frontend and FastAPI.
// Local: http://127.0.0.1:8000
// Render: https://your-render-url.onrender.com
const API_URL = "https://m5-demand-forecasting-api-2.onrender.com";

let token = localStorage.getItem("m5_token");

let forecastData = [];


// ============================================================
// AUTH HEADERS
// ============================================================

function authHeaders() {
    return {
        "Authorization": `Bearer ${token}`
    };
}


// ============================================================
// LOGIN
// ============================================================

async function login() {

    const usernameElement =
        document.getElementById("username");

    const passwordElement =
        document.getElementById("password");

    const message =
        document.getElementById("login-message");

    const username =
        usernameElement.value.trim();

    const password =
        passwordElement.value;

    message.textContent = "";

    if (!username || !password) {
        message.textContent =
            "Please enter username and password.";
        return;
    }

    try {

        const response = await fetch(
            `${API_URL}/auth/login`,
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    username: username,
                    password: password
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {

            message.textContent =
                data.detail ||
                "Invalid username or password.";

            return;
        }

        token = data.token;

        localStorage.setItem(
            "m5_token",
            token
        );

        showDashboard(
            data.username
        );

    } catch (error) {

        console.error(
            "Login error:",
            error
        );

        message.textContent =
            "Cannot connect to the server.";
    }
}


// ============================================================
// SHOW DASHBOARD
// ============================================================

function showDashboard(username) {

    const loginSection =
        document.getElementById(
            "login-section"
        );

    const dashboardSection =
        document.getElementById(
            "dashboard-section"
        );

    if (loginSection) {
        loginSection.style.display = "none";
    }

    if (dashboardSection) {
        dashboardSection.style.display = "flex";
    }

    const loggedUser =
        document.getElementById(
            "logged-user"
        );

    if (loggedUser) {
        loggedUser.textContent =
            username;
    }

    const sidebarUsername =
        document.getElementById(
            "sidebar-username"
        );

    if (sidebarUsername) {
        sidebarUsername.textContent =
            username;
    }

    loadDashboard();
}


// ============================================================
// LOGOUT
// ============================================================

function logout() {

    localStorage.removeItem(
        "m5_token"
    );

    token = null;

    forecastData = [];

    const dashboardSection =
        document.getElementById(
            "dashboard-section"
        );

    const loginSection =
        document.getElementById(
            "login-section"
        );

    if (dashboardSection) {
        dashboardSection.style.display =
            "none";
    }

    if (loginSection) {
        loginSection.style.display =
            "flex";
    }
}


// ============================================================
// LOAD COMPLETE DASHBOARD
// ============================================================

async function loadDashboard() {

    await loadForecast();

    await loadSummary();

    await loadMetrics();

    await loadHierarchy();

    await loadProfile();
}


// ============================================================
// FORECAST
// ============================================================

async function loadForecast() {

    if (!token) {
        return;
    }

    const modeElement =
        document.getElementById(
            "mode-filter"
        );

    const mode =
        modeElement
            ? modeElement.value
            : "future";

    try {

        const response =
            await fetch(
                `${API_URL}/forecast?mode=${encodeURIComponent(mode)}`,
                {
                    headers:
                        authHeaders()
                }
            );

        const data =
            await response.json();

        if (!response.ok) {

            console.error(
                "Forecast API error:",
                data
            );

            return;
        }

        forecastData =
            data.data || [];

        updateGlobalForecastCards(
            data
        );

        populateFilters(
            forecastData
        );

        applyFilters();

    } catch (error) {

        console.error(
            "Forecast error:",
            error
        );
    }
}


// ============================================================
// GLOBAL FORECAST CARDS
// ============================================================

function updateGlobalForecastCards(data) {

    const total =
        document.getElementById(
            "total-units"
        );

    const average =
        document.getElementById(
            "average-units"
        );

    const series =
        document.getElementById(
            "series-count"
        );

    if (total) {

        total.textContent =
            formatNumber(
                data.total_units
            );
    }

    if (average) {

        average.textContent =
            formatNumber(
                data.avg_units_per_day
            );
    }

    if (series) {

        series.textContent =
            formatNumber(
                data.series
            );
    }
}


// ============================================================
// SUMMARY
// ============================================================

async function loadSummary() {

    if (!token) {
        return;
    }

    const modeElement =
        document.getElementById(
            "mode-filter"
        );

    const mode =
        modeElement
            ? modeElement.value
            : "future";

    try {

        const response =
            await fetch(
                `${API_URL}/forecast/summary?mode=${encodeURIComponent(mode)}`,
                {
                    headers:
                        authHeaders()
                }
            );

        const data =
            await response.json();

        if (!response.ok) {

            console.error(
                "Summary API error:",
                data
            );

            return;
        }

        const peak =
            document.getElementById(
                "peak-day"
            );

        if (peak) {

            peak.textContent =
                formatNumber(
                    data.peak_day_units
                );
        }

    } catch (error) {

        console.error(
            "Summary error:",
            error
        );
    }
}


// ============================================================
// METRICS
// ============================================================

async function loadMetrics() {

    if (!token) {
        return;
    }

    try {

        const response =
            await fetch(
                `${API_URL}/metrics?mode=validation`,
                {
                    headers:
                        authHeaders()
                }
            );

        const data =
            await response.json();

        if (!response.ok) {

            console.error(
                "Metrics API error:",
                data
            );

            return;
        }

        const metrics =
            data.metrics || {};

        setText(
            "wrmsse",
            formatNumber(
                metrics.wrmsse
            )
        );

        setText(
            "rmse",
            formatNumber(
                metrics.rmse
            )
        );

        setText(
            "mae",
            formatNumber(
                metrics.mae
            )
        );

        setText(
            "mape",
            formatNumber(
                metrics.mape
            )
        );

    } catch (error) {

        console.error(
            "Metrics error:",
            error
        );
    }
}


// ============================================================
// HIERARCHY
// ============================================================

async function loadHierarchy() {

    if (!token) {
        return;
    }

    try {

        const response =
            await fetch(
                `${API_URL}/hierarchy`,
                {
                    headers:
                        authHeaders()
                }
            );

        const data =
            await response.json();

        if (!response.ok) {

            console.error(
                "Hierarchy API error:",
                data
            );

            return;
        }

        createHierarchyCards(
            data
        );

        await loadHierarchySummary();

    } catch (error) {

        console.error(
            "Hierarchy error:",
            error
        );
    }
}


// ============================================================
// HIERARCHY CARDS
// ============================================================

function createHierarchyCards(data) {

    const container =
        document.getElementById(
            "hierarchy-cards"
        );

    if (!container) {
        return;
    }

    const cards = [

        {
            icon: "🇺🇸",
            title: "States",
            values:
                data.states || []
        },

        {
            icon: "🏪",
            title: "Stores",
            values:
                data.stores || []
        },

        {
            icon: "🛒",
            title: "Categories",
            values:
                data.categories || []
        },

        {
            icon: "🏷️",
            title: "Departments",
            values:
                data.departments || []
        }
    ];

    container.innerHTML =
        cards.map(
            card => `

                <div class="hierarchy-card">

                    <div class="icon">
                        ${card.icon}
                    </div>

                    <h3>
                        ${escapeHTML(
                            card.title
                        )}
                    </h3>

                    <p>
                        ${
                            card.values.length
                            ? card.values
                                .slice(0, 12)
                                .map(
                                    value =>
                                        escapeHTML(
                                            String(value)
                                        )
                                )
                                .join(" · ")
                            : "No data available"
                        }
                    </p>

                    <strong>
                        ${card.values.length}
                        ${
                            card.values.length === 1
                            ? "value"
                            : "values"
                        }
                    </strong>

                </div>

            `
        ).join("");
}


// ============================================================
// HIERARCHY SUMMARY
// ============================================================

async function loadHierarchySummary() {

    if (!token) {
        return;
    }

    try {

        const response =
            await fetch(
                `${API_URL}/hierarchy/summary`,
                {
                    headers:
                        authHeaders()
                }
            );

        const data =
            await response.json();

        if (!response.ok) {

            console.error(
                "Hierarchy summary error:",
                data
            );

            return;
        }

        const container =
            document.getElementById(
                "hierarchy-table"
            );

        if (!container) {
            return;
        }

        let html = `

            <table>

                <thead>

                    <tr>

                        <th>
                            Level
                        </th>

                        <th>
                            Dimensions
                        </th>

                        <th>
                            Series / Groups
                        </th>

                        <th>
                            Top Forecast
                        </th>

                    </tr>

                </thead>

                <tbody>
        `;

        (data.levels || [])
            .forEach(
                level => {

                    const top =
                        level.data &&
                        level.data.length
                        ? level.data[0].forecast
                        : undefined;

                    html += `

                        <tr>

                            <td>
                                <strong>
                                    ${escapeHTML(
                                        level.level
                                    )}
                                </strong>
                            </td>

                            <td>
                                ${
                                    level.columns &&
                                    level.columns.length
                                    ? level.columns
                                        .map(
                                            column =>
                                                escapeHTML(
                                                    String(column)
                                                )
                                        )
                                        .join(" × ")
                                    : "All"
                                }
                            </td>

                            <td>
                                ${formatNumber(
                                    level.count
                                )}
                            </td>

                            <td>
                                ${
                                    top !== undefined
                                    ? formatNumber(
                                        top
                                    )
                                    : "—"
                                }
                            </td>

                        </tr>
                    `;
                }
            );

        html += `

                </tbody>

            </table>
        `;

        container.innerHTML =
            html;

    } catch (error) {

        console.error(
            "Hierarchy summary error:",
            error
        );
    }
}


// ============================================================
// DATA PROFILE
// ============================================================

async function loadProfile() {

    if (!token) {
        return;
    }

    try {

        const response =
            await fetch(
                `${API_URL}/data-profile`,
                {
                    headers:
                        authHeaders()
                }
            );

        const data =
            await response.json();

        if (!response.ok) {

            console.error(
                "Profile API error:",
                data
            );

            return;
        }

        const features =
            data.profile &&
            data.profile.external_features
            ? data.profile.external_features
            : {};

        setText(
            "price-status",
            features.price
            ? "Price information is available in the forecast data."
            : "Price information is not available in the current forecast data."
        );

        setText(
            "promotion-status",
            features.promotion
            ? "Promotion information is available."
            : "Promotion information is not available in the current forecast data."
        );

        setText(
            "holiday-status",
            features.holiday
            ? "Holiday/event information is available."
            : "Holiday/event information is not available in the current forecast data."
        );

    } catch (error) {

        console.error(
            "Profile error:",
            error
        );
    }
}


// ============================================================
// FILTERS
// ============================================================

function populateFilters(rows) {

    populateSelect(
        "state-filter",
        rows.map(
            row => row.state_id
        )
    );

    populateSelect(
        "store-filter",
        rows.map(
            row => row.store_id
        )
    );

    populateSelect(
        "category-filter",
        rows.map(
            row => row.cat_id
        )
    );

    populateSelect(
        "department-filter",
        rows.map(
            row => row.dept_id
        )
    );

    populateSelect(
        "item-filter",
        rows.map(
            row => row.id
        )
    );
}


function populateSelect(
    id,
    values
) {

    const select =
        document.getElementById(id);

    if (!select) {
        return;
    }

    const current =
        select.value;

    const unique = [
        ...new Set(
            values.filter(
                value =>
                    value !== null &&
                    value !== undefined &&
                    value !== ""
            )
        )
    ].sort(
        (a, b) =>
            String(a).localeCompare(
                String(b)
            )
    );

    const first =
        select.options[0]
            ? select.options[0].outerHTML
            : "";

    select.innerHTML =
        first;

    unique.forEach(
        value => {

            const option =
                document.createElement(
                    "option"
                );

            option.value =
                value;

            option.textContent =
                value;

            select.appendChild(
                option
            );
        }
    );

    if (
        unique.some(
            value =>
                String(value) ===
                String(current)
        )
    ) {

        select.value =
            current;
    }
}


// ============================================================
// APPLY FILTERS
// ============================================================

function applyFilters() {

    let filtered =
        [...forecastData];

    const state =
        getValue("state-filter");

    const store =
        getValue("store-filter");

    const category =
        getValue("category-filter");

    const department =
        getValue("department-filter");

    const item =
        getValue("item-filter");


    if (state) {

        filtered =
            filtered.filter(
                row =>
                    String(
                        row.state_id
                    ) === String(state)
            );
    }


    if (store) {

        filtered =
            filtered.filter(
                row =>
                    String(
                        row.store_id
                    ) === String(store)
            );
    }


    if (category) {

        filtered =
            filtered.filter(
                row =>
                    String(
                        row.cat_id
                    ) === String(category)
            );
    }


    if (department) {

        filtered =
            filtered.filter(
                row =>
                    String(
                        row.dept_id
                    ) === String(department)
            );
    }


    if (item) {

        filtered =
            filtered.filter(
                row =>
                    String(
                        row.id
                    ) === String(item)
            );
    }


    const total =
        filtered.reduce(
            (
                sum,
                row
            ) =>
                sum +
                (
                    Number(
                        row.forecast
                    ) || 0
                ),
            0
        );


    const daily =
        aggregateByDate(
            filtered
        );

    const dates =
        Object.keys(
            daily
        ).sort();


    setText(
        "total-units",
        formatNumber(total)
    );


    setText(
        "average-units",
        formatNumber(
            dates.length
            ? total / dates.length
            : 0
        )
    );


    const seriesSet =
        new Set(
            filtered
                .map(
                    row => row.id
                )
                .filter(
                    value =>
                        value !== null &&
                        value !== undefined
                )
        );


    setText(
        "series-count",
        formatNumber(
            seriesSet.size
        )
    );


    const peak =
        dates.length
        ? Math.max(
            ...Object.values(
                daily
            )
        )
        : 0;


    setText(
        "peak-day",
        formatNumber(
            peak
        )
    );


    createForecastChart(
        filtered
    );


    createCategoryChart(
        filtered
    );


    createStoreChart(
        filtered
    );


    createTopItemsTable(
        filtered
    );
}


// ============================================================
// DAILY AGGREGATION
// ============================================================

function aggregateByDate(rows) {

    const result = {};

    rows.forEach(
        row => {

            if (!row.date) {
                return;
            }

            const date =
                String(
                    row.date
                ).substring(
                    0,
                    10
                );

            const value =
                Number(
                    row.forecast
                ) || 0;

            result[date] =
                (
                    result[date] || 0
                ) + value;
        }
    );

    return result;
}


// ============================================================
// FORECAST LINE CHART
// ============================================================

function createForecastChart(rows) {

    const container =
        document.getElementById(
            "forecast-chart"
        );

    if (!container) {
        return;
    }

    const daily =
        aggregateByDate(
            rows
        );

    const dates =
        Object.keys(
            daily
        ).sort();

    if (!dates.length) {

        container.innerHTML = `
            <div class="chart-placeholder">
                <span>📈</span>
                No forecast data available.
            </div>
        `;

        return;
    }

    const values =
        dates.map(
            date =>
                daily[date]
        );


    const width = 1100;
    const height = 420;

    const leftPad = 80;
    const rightPad = 35;
    const topPad = 35;
    const bottomPad = 70;


    const usableWidth =
        width -
        leftPad -
        rightPad;

    const usableHeight =
        height -
        topPad -
        bottomPad;


    const max =
        Math.max(
            ...values
        );

    const min =
        Math.min(
            ...values
        );


    const range =
        Math.max(
            max - min,
            1
        );


    const points =
        values.map(
            (
                value,
                index
            ) => {

                const x =
                    leftPad +
                    (
                        index /
                        Math.max(
                            dates.length - 1,
                            1
                        )
                    ) *
                    usableWidth;

                const y =
                    topPad +
                    usableHeight -
                    (
                        (
                            value - min
                        ) /
                        range
                    ) *
                    usableHeight;

                return {
                    x,
                    y
                };
            }
        );


    const polyline =
        points
            .map(
                point =>
                    `${point.x},${point.y}`
            )
            .join(" ");


    // --------------------------------------------------------
    // GRID LINES
    // --------------------------------------------------------

    let gridLines = "";

    const gridCount = 5;

    for (
        let i = 0;
        i <= gridCount;
        i++
    ) {

        const ratio =
            i / gridCount;

        const y =
            topPad +
            usableHeight -
            ratio *
            usableHeight;

        const value =
            min +
            ratio *
            range;

        gridLines += `

            <line
                x1="${leftPad}"
                y1="${y}"
                x2="${width - rightPad}"
                y2="${y}"
                stroke="#e5e7eb"
                stroke-width="1"
            />

            <text
                x="${leftPad - 10}"
                y="${y + 4}"
                text-anchor="end"
                font-size="12"
                fill="#667085"
            >
                ${formatNumber(value)}
            </text>
        `;
    }


    // --------------------------------------------------------
    // X AXIS LABELS
    // --------------------------------------------------------

    let xLabels = "";

    points.forEach(
        (
            point,
            index
        ) => {

            if (
                index !== 0 &&
                index !== points.length - 1 &&
                index % 4 !== 0
            ) {
                return;
            }

            xLabels += `

                <text
                    x="${point.x}"
                    y="${height - 30}"
                    text-anchor="middle"
                    font-size="12"
                    fill="#667085"
                >
                    ${dates[index]}
                </text>
            `;
        }
    );


    // --------------------------------------------------------
    // DATA POINTS
    // --------------------------------------------------------

    const circles =
        points
            .map(
                (
                    point,
                    index
                ) => `

                    <circle
                        cx="${point.x}"
                        cy="${point.y}"
                        r="5"
                        fill="#3264d6"
                        stroke="white"
                        stroke-width="2"
                    >

                        <title>
                            Date: ${dates[index]}
                            | Units: ${formatNumber(
                                values[index]
                            )}
                        </title>

                    </circle>
                `
            )
            .join("");


    // --------------------------------------------------------
    // SVG
    // --------------------------------------------------------

    container.innerHTML = `

        <svg
            viewBox="
                0 0
                ${width}
                ${height}
            "
            width="100%"
            height="420"
            role="img"
            aria-label="28-day demand forecast chart"
        >

            <!-- GRID -->

            ${gridLines}


            <!-- Y AXIS -->

            <line
                x1="${leftPad}"
                y1="${topPad}"
                x2="${leftPad}"
                y2="${height - bottomPad}"
                stroke="#98a2b3"
                stroke-width="1.5"
            />


            <!-- X AXIS -->

            <line
                x1="${leftPad}"
                y1="${height - bottomPad}"
                x2="${width - rightPad}"
                y2="${height - bottomPad}"
                stroke="#98a2b3"
                stroke-width="1.5"
            />


            <!-- FORECAST LINE -->

            <polyline
                points="${polyline}"
                fill="none"
                stroke="#3264d6"
                stroke-width="4"
                stroke-linecap="round"
                stroke-linejoin="round"
            />


            <!-- POINTS -->

            ${circles}


            <!-- X AXIS TITLE -->

            <text
                x="${width / 2}"
                y="${height - 5}"
                text-anchor="middle"
                font-size="14"
                font-weight="600"
                fill="#344054"
            >
                Date
            </text>


            <!-- Y AXIS TITLE -->

            <text
                x="18"
                y="${height / 2}"
                text-anchor="middle"
                font-size="14"
                font-weight="600"
                fill="#344054"
                transform="
                    rotate(
                        -90
                        18
                        ${height / 2}
                    )
                "
            >
                Forecasted Units
            </text>

        </svg>
    `;
}


// ============================================================
// CATEGORY CHART
// ============================================================

function createCategoryChart(rows) {

    const container =
        document.getElementById(
            "category-chart"
        );

    if (!container) {
        return;
    }

    const groups = {};

    rows.forEach(
        row => {

            const category =
                row.cat_id ||
                "Unknown";

            groups[category] =
                (
                    groups[category] || 0
                ) +
                (
                    Number(
                        row.forecast
                    ) || 0
                );
        }
    );

    renderBars(
        container,
        groups
    );
}


// ============================================================
// STORE CHART
// ============================================================

function createStoreChart(rows) {

    const container =
        document.getElementById(
            "store-chart"
        );

    if (!container) {
        return;
    }

    const groups = {};

    rows.forEach(
        row => {

            const store =
                row.store_id ||
                "Unknown";

            groups[store] =
                (
                    groups[store] || 0
                ) +
                (
                    Number(
                        row.forecast
                    ) || 0
                );
        }
    );

    renderBars(
        container,
        groups
    );
}


// ============================================================
// BAR RENDERER
// ============================================================

function renderBars(
    container,
    groups
) {

    const entries =
        Object.entries(
            groups
        )
        .sort(
            (
                a,
                b
            ) =>
                b[1] - a[1]
        )
        .slice(
            0,
            10
        );


    if (!entries.length) {

        container.innerHTML = `
            <div class="chart-placeholder">
                No data available.
            </div>
        `;

        return;
    }


    const max =
        entries[0][1];


    let html = "";


    entries.forEach(
        entry => {

            const name =
                entry[0];

            const value =
                entry[1];

            const width =
                max > 0
                ? (
                    value / max
                ) * 100
                : 0;


            html += `

                <div
                    style="
                        margin-bottom:16px;
                    "
                >

                    <div
                        style="
                            display:flex;
                            justify-content:space-between;
                            margin-bottom:6px;
                            font-size:13px;
                        "
                    >

                        <span>
                            ${escapeHTML(
                                String(name)
                            )}
                        </span>

                        <strong>
                            ${formatNumber(
                                value
                            )}
                        </strong>

                    </div>


                    <div
                        style="
                            height:10px;
                            background:#edf1f7;
                            border-radius:10px;
                            overflow:hidden;
                        "
                    >

                        <div
                            style="
                                width:${width}%;
                                height:100%;
                                background:#3264d6;
                                border-radius:10px;
                            "
                        ></div>

                    </div>

                </div>
            `;
        }
    );


    container.innerHTML =
        html;
}


// ============================================================
// TOP ITEMS
// ============================================================

function createTopItemsTable(rows) {

    const container =
        document.getElementById(
            "top-items"
        );

    if (!container) {
        return;
    }

    const groups = {};


    rows.forEach(
        row => {

            const id =
                row.id ||
                "Unknown";

            groups[id] =
                (
                    groups[id] || 0
                ) +
                (
                    Number(
                        row.forecast
                    ) || 0
                );
        }
    );


    const top =
        Object.entries(
            groups
        )
        .sort(
            (
                a,
                b
            ) =>
                b[1] - a[1]
        )
        .slice(
            0,
            20
        );


    if (!top.length) {

        container.innerHTML =
            "<p>No forecast items available.</p>";

        return;
    }


    let html = `

        <table>

            <thead>

                <tr>

                    <th>
                        #
                    </th>

                    <th>
                        Item
                    </th>

                    <th>
                        Forecast
                    </th>

                </tr>

            </thead>

            <tbody>
    `;


    top.forEach(
        (
            item,
            index
        ) => {

            html += `

                <tr>

                    <td>
                        ${index + 1}
                    </td>

                    <td>
                        ${escapeHTML(
                            String(
                                item[0]
                            )
                        )}
                    </td>

                    <td>
                        ${formatNumber(
                            item[1]
                        )}
                    </td>

                </tr>
            `;
        }
    );


    html += `

            </tbody>

        </table>
    `;


    container.innerHTML =
        html;
}


// ============================================================
// TAB SWITCH
// ============================================================

function showTab(
    tabId,
    button
) {

    document
        .querySelectorAll(
            ".tab-content"
        )
        .forEach(
            tab =>
                tab.classList.remove(
                    "active-tab"
                )
        );


    const tab =
        document.getElementById(
            tabId
        );


    if (tab) {

        tab.classList.add(
            "active-tab"
        );
    }


    document
        .querySelectorAll(
            ".nav-item"
        )
        .forEach(
            item =>
                item.classList.remove(
                    "active"
                )
        );


    if (button) {

        button.classList.add(
            "active"
        );
    }
}


// ============================================================
// SERIES SEARCH
// ============================================================

function searchSeries() {

    const input =
        document.getElementById(
            "series-search"
        );

    const container =
        document.getElementById(
            "series-results"
        );

    if (!input || !container) {
        return;
    }


    const query =
        input.value
            .trim()
            .toLowerCase();


    const results =
        forecastData
            .filter(
                row => {

                    const id =
                        String(
                            row.id || ""
                        )
                        .toLowerCase();


                    const store =
                        String(
                            row.store_id || ""
                        )
                        .toLowerCase();


                    const state =
                        String(
                            row.state_id || ""
                        )
                        .toLowerCase();


                    const category =
                        String(
                            row.cat_id || ""
                        )
                        .toLowerCase();


                    return (
                        id.includes(query) ||
                        store.includes(query) ||
                        state.includes(query) ||
                        category.includes(query)
                    );
                }
            )
            .slice(
                0,
                100
            );


    if (!results.length) {

        container.innerHTML =
            "<p>No matching series found.</p>";

        return;
    }


    let html = `

        <table>

            <thead>

                <tr>

                    <th>
                        Series
                    </th>

                    <th>
                        Store
                    </th>

                    <th>
                        Date
                    </th>

                    <th>
                        Forecast
                    </th>

                </tr>

            </thead>

            <tbody>
    `;


    results.forEach(
        row => {

            html += `

                <tr>

                    <td>
                        ${escapeHTML(
                            String(
                                row.id || "—"
                            )
                        )}
                    </td>

                    <td>
                        ${escapeHTML(
                            String(
                                row.store_id || "—"
                            )
                        )}
                    </td>

                    <td>
                        ${escapeHTML(
                            String(
                                row.date || "—"
                            )
                        ).substring(
                            0,
                            10
                        )}
                    </td>

                    <td>
                        ${formatNumber(
                            row.forecast
                        )}
                    </td>

                </tr>
            `;
        }
    );


    html += `

            </tbody>

        </table>
    `;


    container.innerHTML =
        html;
}


// ============================================================
// EXPORT FORECAST
// ============================================================

function exportForecast() {

    if (!forecastData.length) {

        alert(
            "No forecast data loaded."
        );

        return;
    }


    const headers =
        Object.keys(
            forecastData[0]
        );


    const rows = [
        headers.join(",")
    ];


    forecastData.forEach(
        row => {

            rows.push(

                headers
                    .map(
                        header => {

                            const value =
                                row[header] ??
                                "";

                            return `"${String(
                                value
                            ).replace(
                                /"/g,
                                '""'
                            )}"`;
                        }
                    )
                    .join(",")
            );
        }
    );


    const blob =
        new Blob(
            [
                rows.join("\n")
            ],
            {
                type:
                    "text/csv;charset=utf-8;"
            }
        );


    const url =
        URL.createObjectURL(
            blob
        );


    const link =
        document.createElement(
            "a"
        );


    link.href =
        url;

    link.download =
        "m5_forecast.csv";


    document.body.appendChild(
        link
    );

    link.click();

    document.body.removeChild(
        link
    );


    URL.revokeObjectURL(
        url
    );
}


// ============================================================
// FILTER EVENTS
// ============================================================

[
    "state-filter",
    "store-filter",
    "category-filter",
    "department-filter",
    "item-filter"
]
.forEach(
    id => {

        const element =
            document.getElementById(
                id
            );

        if (element) {

            element.addEventListener(
                "change",
                applyFilters
            );
        }
    }
);


// ============================================================
// MODE CHANGE
// ============================================================

const modeFilter =
    document.getElementById(
        "mode-filter"
    );


if (modeFilter) {

    modeFilter.addEventListener(
        "change",
        async () => {

            await loadForecast();

            await loadSummary();

        }
    );
}


// ============================================================
// ENTER KEY FOR LOGIN
// ============================================================

const passwordInput =
    document.getElementById(
        "password"
    );


if (passwordInput) {

    passwordInput.addEventListener(
        "keydown",
        event => {

            if (
                event.key === "Enter"
            ) {

                login();
            }
        }
    );
}


// ============================================================
// NUMBER FORMAT
// ============================================================

function formatNumber(value) {

    if (
        value === undefined ||
        value === null ||
        Number.isNaN(
            Number(value)
        )
    ) {

        return "—";
    }


    return Number(value)
        .toLocaleString(
            undefined,
            {
                maximumFractionDigits: 2
            }
        );
}


// ============================================================
// GET ELEMENT VALUE
// ============================================================

function getValue(id) {

    const element =
        document.getElementById(
            id
        );

    return element
        ? element.value
        : "";
}


// ============================================================
// SET TEXT
// ============================================================

function setText(
    id,
    value
) {

    const element =
        document.getElementById(
            id
        );

    if (element) {

        element.textContent =
            value;
    }
}


// ============================================================
// HTML ESCAPE
// ============================================================

function escapeHTML(value) {

    return String(value)
        .replace(
            /&/g,
            "&amp;"
        )
        .replace(
            /</g,
            "&lt;"
        )
        .replace(
            />/g,
            "&gt;"
        )
        .replace(
            /"/g,
            "&quot;"
        )
        .replace(
            /'/g,
            "&#039;"
        );
}


// ============================================================
// EXISTING SESSION
// ============================================================

async function checkExistingLogin() {

    if (!token) {

        return;
    }


    try {

        const response =
            await fetch(
                `${API_URL}/auth/me`,
                {
                    headers:
                        authHeaders()
                }
            );


        if (!response.ok) {

            localStorage.removeItem(
                "m5_token"
            );

            token = null;

            return;
        }


        const data =
            await response.json();


        showDashboard(
            data.username
        );


    } catch (error) {

        console.error(
            "Session check error:",
            error
        );
    }
}


// ============================================================
// START APPLICATION
// ============================================================

document.addEventListener(
    "DOMContentLoaded",
    () => {

        checkExistingLogin();

    }
);