const API_URL = "http://127.0.0.1:8000";

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

    const username =
        document.getElementById("username").value.trim();

    const password =
        document.getElementById("password").value;

    const message =
        document.getElementById("login-message");


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


        message.textContent = "";

        showDashboard(data.username);


    } catch (error) {

        console.error("Login error:", error);

        message.textContent =
            "Cannot connect to FastAPI server.";
    }
}


// ============================================================
// SHOW DASHBOARD
// ============================================================

function showDashboard(username) {

    document.getElementById(
        "login-section"
    ).style.display = "none";


    document.getElementById(
        "dashboard-section"
    ).style.display = "flex";


    const loggedUser =
        document.getElementById("logged-user");

    if (loggedUser) {
        loggedUser.textContent = username;
    }


    const sidebarUsername =
        document.getElementById("sidebar-username");

    if (sidebarUsername) {
        sidebarUsername.textContent = username;
    }


    loadDashboard();
}


// ============================================================
// LOGOUT
// ============================================================

function logout() {

    localStorage.removeItem("m5_token");

    token = null;

    forecastData = [];


    document.getElementById(
        "dashboard-section"
    ).style.display = "none";


    document.getElementById(
        "login-section"
    ).style.display = "flex";
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

    if (!token) return;


    const modeElement =
        document.getElementById("mode-filter");


    const mode =
        modeElement
            ? modeElement.value
            : "future";


    try {

        const response = await fetch(
            `${API_URL}/forecast?mode=${mode}`,
            {
                headers: authHeaders()
            }
        );


        const data = await response.json();


        if (!response.ok) {

            console.error(
                "Forecast error:",
                data
            );

            return;
        }


        forecastData =
            data.data || [];


        document.getElementById(
            "total-units"
        ).textContent =
            formatNumber(
                data.total_units
            );


        document.getElementById(
            "average-units"
        ).textContent =
            formatNumber(
                data.avg_units_per_day
            );


        document.getElementById(
            "series-count"
        ).textContent =
            formatNumber(
                data.series
            );


        populateFilters(
            forecastData
        );


        applyFilters();


    } catch (error) {

        console.error(
            "Forecast request failed:",
            error
        );
    }
}


// ============================================================
// SUMMARY
// ============================================================

async function loadSummary() {

    if (!token) return;


    const modeElement =
        document.getElementById("mode-filter");


    const mode =
        modeElement
            ? modeElement.value
            : "future";


    try {

        const response = await fetch(
            `${API_URL}/forecast/summary?mode=${mode}`,
            {
                headers: authHeaders()
            }
        );


        const data =
            await response.json();


        if (!response.ok) {

            console.error(
                "Summary error:",
                data
            );

            return;
        }


        const peakElement =
            document.getElementById("peak-day");


        if (peakElement) {

            peakElement.textContent =
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

    if (!token) return;


    const modeElement =
        document.getElementById("mode-filter");


    const mode =
        modeElement
            ? modeElement.value
            : "validation";


    try {

        const response = await fetch(
            `${API_URL}/metrics?mode=validation`,
            {
                headers: authHeaders()
            }
        );


        const data =
            await response.json();


        if (!response.ok) {

            console.error(
                "Metrics error:",
                data
            );

            return;
        }


        const metrics =
            data.metrics || {};


        setText(
            "wrmsse",
            formatNumber(metrics.wrmsse)
        );


        setText(
            "rmse",
            formatNumber(metrics.rmse)
        );


        setText(
            "mae",
            formatNumber(metrics.mae)
        );


        setText(
            "mape",
            formatNumber(metrics.mape)
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

    if (!token) return;


    try {

        const response =
            await fetch(
                `${API_URL}/hierarchy`,
                {
                    headers: authHeaders()
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            console.error(
                "Hierarchy error:",
                data
            );

            return;
        }


        createHierarchyCards(data);

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


    if (!container) return;


    const cards = [

        {
            icon: "🇺🇸",
            title: "States",
            values: data.states || []
        },

        {
            icon: "🏪",
            title: "Stores",
            values: data.stores || []
        },

        {
            icon: "🛒",
            title: "Categories",
            values: data.categories || []
        },

        {
            icon: "🏷️",
            title: "Departments",
            values: data.departments || []
        },

        {
            icon: "📦",
            title: "Items",
            values: data.items || []
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
                        ${card.title}
                    </h3>

                    <p>
                        ${
                            card.values.length
                            ? card.values
                                .slice(0, 12)
                                .join(" · ")
                            : "No data available"
                        }
                    </p>

                    <strong>
                        ${card.values.length}
                        ${
                            card.values.length === 1
                            ? " value"
                            : " values"
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

    if (!token) return;


    try {

        const response =
            await fetch(
                `${API_URL}/hierarchy/summary`,
                {
                    headers: authHeaders()
                }
            );


        const data =
            await response.json();


        if (!response.ok) return;


        const container =
            document.getElementById(
                "hierarchy-table"
            );


        if (!container) return;


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


        (data.levels || []).forEach(
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
                                ${level.level}
                            </strong>
                        </td>

                        <td>
                            ${
                                level.columns &&
                                level.columns.length
                                ? level.columns.join(" × ")
                                : "All"
                            }
                        </td>

                        <td>
                            ${level.count}
                        </td>

                        <td>
                            ${
                                top !== undefined
                                ? formatNumber(top)
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


        container.innerHTML = html;


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

    if (!token) return;


    try {

        const response =
            await fetch(
                `${API_URL}/data-profile`,
                {
                    headers: authHeaders()
                }
            );


        const data =
            await response.json();


        if (!response.ok) return;


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
// POPULATE FILTERS
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


// ============================================================
// POPULATE SELECT
// ============================================================

function populateSelect(id, values) {

    const select =
        document.getElementById(id);


    if (!select) return;


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


    select.innerHTML = "";


    const firstOption =
        document.createElement("option");


    firstOption.value = "";

    firstOption.textContent =
        id === "state-filter"
        ? "All States"
        : id === "store-filter"
        ? "All Stores"
        : id === "category-filter"
        ? "All Categories"
        : id === "department-filter"
        ? "All Departments"
        : "All Items";


    select.appendChild(
        firstOption
    );


    unique.forEach(
        value => {

            const option =
                document.createElement("option");


            option.value = value;

            option.textContent = value;


            select.appendChild(
                option
            );
        }
    );


    if (
        unique.includes(current)
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
                    row.state_id === state
            );
    }


    if (store) {

        filtered =
            filtered.filter(
                row =>
                    row.store_id === store
            );
    }


    if (category) {

        filtered =
            filtered.filter(
                row =>
                    row.cat_id === category
            );
    }


    if (department) {

        filtered =
            filtered.filter(
                row =>
                    row.dept_id === department
            );
    }


    if (item) {

        filtered =
            filtered.filter(
                row =>
                    row.id === item
            );
    }


    const total =
        filtered.reduce(
            (sum, row) =>
                sum +
                (
                    Number(row.forecast) || 0
                ),
            0
        );


    const daily =
        aggregateByDate(filtered);


    const days =
        Object.keys(daily);


    setText(
        "total-units",
        formatNumber(total)
    );


    setText(
        "average-units",
        formatNumber(
            days.length
            ? total / days.length
            : 0
        )
    );


    const series =
        new Set(
            filtered.map(
                row => row.id
            )
        ).size;


    setText(
        "series-count",
        formatNumber(series)
    );


    const peak =
        days.length
        ? Math.max(
            ...Object.values(daily)
        )
        : 0;


    setText(
        "peak-day",
        formatNumber(peak)
    );


    createForecastChart(filtered);

    createCategoryChart(filtered);

    createStoreChart(filtered);

    createTopItemsTable(filtered);
}


// ============================================================
// AGGREGATE BY DATE
// ============================================================

function aggregateByDate(rows) {

    const result = {};


    rows.forEach(
        row => {

            if (!row.date) return;


            const date =
                String(row.date)
                    .substring(0, 10);


            const value =
                Number(row.forecast) || 0;


            result[date] =
                (
                    result[date] || 0
                ) + value;
        }
    );


    return result;
}


// ============================================================
// INTERACTIVE FORECAST LINE CHART
// ============================================================

function createForecastChart(rows) {

    const container =
        document.getElementById(
            "forecast-chart"
        );


    if (!container) return;


    const daily =
        aggregateByDate(rows);


    const dates =
        Object.keys(daily).sort();


    if (!dates.length) {

        container.innerHTML = `

            <div class="chart-placeholder">

                <span>
                    📈
                </span>

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


    // --------------------------------------------------------
    // CHART SIZE
    // --------------------------------------------------------

    const width = 1100;

    const height = 450;

    const left = 90;

    const right = 35;

    const top = 35;

    const bottom = 85;


    const chartWidth =
        width - left - right;


    const chartHeight =
        height - top - bottom;


    // --------------------------------------------------------
    // Y SCALE
    // --------------------------------------------------------

    const maxValue =
        Math.max(...values);


    const minValue =
        Math.min(...values);


    const range =
        Math.max(
            maxValue - minValue,
            1
        );


    const yMin =
        Math.max(
            0,
            minValue - range * 0.15
        );


    const yMax =
        maxValue +
        range * 0.15;


    function getX(index) {

        return left +
            (
                index /
                Math.max(
                    dates.length - 1,
                    1
                )
            ) *
            chartWidth;
    }


    function getY(value) {

        return top +
            chartHeight -
            (
                (
                    value - yMin
                ) /
                (
                    yMax - yMin
                )
            ) *
            chartHeight;
    }


    // --------------------------------------------------------
    // POINTS
    // --------------------------------------------------------

    const points =
        values.map(
            (value, index) => {

                return {

                    x: getX(index),

                    y: getY(value),

                    value: value,

                    date: dates[index]
                };
            }
        );


    // --------------------------------------------------------
    // FORECAST LINE
    // --------------------------------------------------------

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

    const gridCount = 5;

    let gridLines = "";


    for (
        let i = 0;
        i <= gridCount;
        i++
    ) {

        const value =
            yMin +
            (
                (
                    yMax - yMin
                ) *
                i /
                gridCount
            );


        const y =
            getY(value);


        gridLines += `

            <line
                x1="${left}"
                y1="${y}"
                x2="${width - right}"
                y2="${y}"
                stroke="#dfe5ef"
                stroke-width="1"
            />

            <text
                x="${left - 12}"
                y="${y + 5}"
                text-anchor="end"
                font-size="13"
                fill="#667085"
            >
                ${formatNumber(value)}
            </text>

        `;
    }


    // --------------------------------------------------------
    // X AXIS DATE LABELS
    // --------------------------------------------------------

    let xLabels = "";


    points.forEach(
        (point, index) => {

            const showEvery =
                Math.max(
                    1,
                    Math.floor(
                        dates.length / 6
                    )
                );


            if (
                index % showEvery !== 0 &&
                index !== dates.length - 1
            ) {

                return;
            }


            const date =
                dates[index];


            const formattedDate =
                formatChartDate(date);


            xLabels += `

                <text
                    x="${point.x}"
                    y="${height - 45}"
                    text-anchor="middle"
                    font-size="13"
                    fill="#667085"
                >
                    ${formattedDate}
                </text>

            `;
        }
    );


    // --------------------------------------------------------
    // DATA POINTS
    // --------------------------------------------------------

    let circles = "";


    points.forEach(
        (point, index) => {

            circles += `

                <circle
                    cx="${point.x}"
                    cy="${point.y}"
                    r="6"
                    fill="#3264d6"
                    stroke="#ffffff"
                    stroke-width="2"
                    class="forecast-point"
                    data-index="${index}"
                    data-date="${point.date}"
                    data-value="${point.value}"
                />

            `;
        }
    );


    // --------------------------------------------------------
    // BUILD CHART
    // --------------------------------------------------------

    container.innerHTML = `

        <div
            class="forecast-chart-wrapper"
            style="
                position:relative;
                width:100%;
                overflow-x:auto;
            "
        >

            <svg
                id="forecast-svg"
                viewBox="
                    0
                    0
                    ${width}
                    ${height}
                "
                width="100%"
                height="${height}"
                style="
                    min-width:850px;
                    display:block;
                "
            >

                <!-- GRID -->

                ${gridLines}


                <!-- Y AXIS -->

                <line
                    x1="${left}"
                    y1="${top}"
                    x2="${left}"
                    y2="${height - bottom}"
                    stroke="#98a2b3"
                    stroke-width="2"
                />


                <!-- X AXIS -->

                <line
                    x1="${left}"
                    y1="${height - bottom}"
                    x2="${width - right}"
                    y2="${height - bottom}"
                    stroke="#98a2b3"
                    stroke-width="2"
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


                <!-- DATA POINTS -->

                ${circles}


                <!-- X AXIS LABELS -->

                ${xLabels}


                <!-- X AXIS TITLE -->

                <text
                    x="${width / 2}"
                    y="${height - 10}"
                    text-anchor="middle"
                    font-size="16"
                    font-weight="600"
                    fill="#344054"
                >
                    Date
                </text>


                <!-- Y AXIS TITLE -->

                <text
                    x="22"
                    y="${height / 2}"
                    text-anchor="middle"
                    font-size="16"
                    font-weight="600"
                    fill="#344054"
                    transform="
                        rotate(-90 22 ${height / 2})
                    "
                >
                    Units
                </text>

            </svg>


            <!-- TOOLTIP -->

            <div
                id="forecast-tooltip"
                style="
                    display:none;
                    position:absolute;
                    background:#111827;
                    color:#ffffff;
                    padding:10px 14px;
                    border-radius:8px;
                    font-size:13px;
                    line-height:1.5;
                    pointer-events:none;
                    box-shadow:
                        0 5px 18px
                        rgba(0,0,0,0.25);
                    z-index:100;
                    white-space:nowrap;
                "
            ></div>

        </div>

    `;


    // --------------------------------------------------------
    // HOVER
    // --------------------------------------------------------

    const tooltip =
        document.getElementById(
            "forecast-tooltip"
        );


    const svg =
        document.getElementById(
            "forecast-svg"
        );


    const wrapper =
        svg.parentElement;


    const pointElements =
        svg.querySelectorAll(
            ".forecast-point"
        );


    pointElements.forEach(
        point => {

            point.addEventListener(
                "mouseenter",
                function () {

                    const date =
                        this.dataset.date;


                    const value =
                        Number(
                            this.dataset.value
                        );


                    tooltip.innerHTML = `

                        <strong>
                            ${date}
                        </strong>

                        <br>

                        Units:
                        ${formatNumber(value)}

                    `;


                    tooltip.style.display =
                        "block";


                    this.setAttribute(
                        "r",
                        "9"
                    );
                }
            );


            point.addEventListener(
                "mousemove",
                function (event) {

                    const rect =
                        wrapper.getBoundingClientRect();


                    tooltip.style.left =
                        (
                            event.clientX -
                            rect.left +
                            12
                        ) + "px";


                    tooltip.style.top =
                        (
                            event.clientY -
                            rect.top -
                            60
                        ) + "px";
                }
            );


            point.addEventListener(
                "mouseleave",
                function () {

                    tooltip.style.display =
                        "none";


                    this.setAttribute(
                        "r",
                        "6"
                    );
                }
            );

        }
    );
}


// ============================================================
// FORMAT CHART DATE
// ============================================================

function formatChartDate(dateString) {

    const parts =
        String(dateString)
            .substring(0, 10)
            .split("-");


    if (parts.length !== 3) {
        return dateString;
    }


    return `${parts[1]}-${parts[2]}`;
}


// ============================================================
// CATEGORY CHART
// ============================================================

function createCategoryChart(rows) {

    const container =
        document.getElementById(
            "category-chart"
        );


    if (!container) return;


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


    if (!container) return;


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
// BAR CHART
// ============================================================

function renderBars(
    container,
    groups
) {

    const entries =
        Object.entries(groups)
            .sort(
                (a, b) =>
                    b[1] - a[1]
            )
            .slice(0, 10);


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
                        margin-bottom:18px;
                    "
                >

                    <div
                        style="
                            display:flex;
                            justify-content:
                                space-between;
                            align-items:center;
                            margin-bottom:7px;
                            font-size:13px;
                        "
                    >

                        <span>
                            ${name}
                        </span>

                        <strong>
                            ${formatNumber(value)}
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
// TOP 20 ITEMS
// ============================================================

function createTopItemsTable(rows) {

    const container =
        document.getElementById(
            "top-items"
        );


    if (!container) return;


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
        Object.entries(groups)
            .sort(
                (a, b) =>
                    b[1] - a[1]
            )
            .slice(0, 20);


    if (!top.length) {

        container.innerHTML =
            "<p>No item data available.</p>";

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
        (item, index) => {

            html += `

                <tr>

                    <td>
                        ${index + 1}
                    </td>

                    <td>
                        ${item[0]}
                    </td>

                    <td>
                        ${formatNumber(item[1])}
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
// TAB SWITCHING
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
            tab => {

                tab.classList.remove(
                    "active-tab"
                );
            }
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
            item => {

                item.classList.remove(
                    "active"
                );
            }
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


    if (!input || !container) return;


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


                    return (
                        id.includes(query) ||
                        store.includes(query)
                    );
                }
            )
            .slice(0, 100);


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
                        ${row.id || "—"}
                    </td>

                    <td>
                        ${row.store_id || "—"}
                    </td>

                    <td>
                        ${
                            String(
                                row.date || "—"
                            ).substring(0, 10)
                        }
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
// EXPORT CSV
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


    const csvRows = [];

    csvRows.push(
        headers.join(",")
    );


    forecastData.forEach(
        row => {

            const values =
                headers.map(
                    header => {

                        const value =
                            row[header] ?? "";


                        return `"${String(
                            value
                        ).replace(
                            /"/g,
                            '""'
                        )}"`;
                    }
                );


            csvRows.push(
                values.join(",")
            );
        }
    );


    const blob =
        new Blob(
            [
                csvRows.join("\n")
            ],
            {
                type:
                    "text/csv;charset=utf-8;"
            }
        );


    const url =
        URL.createObjectURL(blob);


    const link =
        document.createElement("a");


    link.href = url;

    link.download =
        "m5_forecast.csv";


    document.body.appendChild(
        link
    );


    link.click();


    document.body.removeChild(
        link
    );


    URL.revokeObjectURL(url);
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
            document.getElementById(id);


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

            await loadMetrics();
        }
    );
}


// ============================================================
// SEARCH ENTER KEY
// ============================================================

const seriesSearch =
    document.getElementById(
        "series-search"
    );


if (seriesSearch) {

    seriesSearch.addEventListener(
        "keydown",
        event => {

            if (event.key === "Enter") {

                searchSeries();
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
// HELPER: SET TEXT
// ============================================================

function setText(
    id,
    value
) {

    const element =
        document.getElementById(id);


    if (element) {

        element.textContent =
            value;
    }
}


// ============================================================
// HELPER: GET VALUE
// ============================================================

function getValue(id) {

    const element =
        document.getElementById(id);


    if (!element) {
        return "";
    }


    return element.value;
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

checkExistingLogin();