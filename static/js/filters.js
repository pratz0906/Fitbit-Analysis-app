(function () {
    "use strict";

    // ── Gather filter elements ──────────────────────────────────────────
    const startDate = document.getElementById("start-date");
    const endDate = document.getElementById("end-date");
    const dataSources = document.getElementById("data-sources");
    const viewRadios = document.querySelectorAll('input[name="view_mode"]');
    const metricRadios = document.querySelectorAll('input[name="activity_metric"]');
    const distUnitRadios = document.querySelectorAll('input[name="dist_unit"]');
    const weightUnitRadios = document.querySelectorAll('input[name="weight_unit"]');
    const distUnitGroup = document.getElementById("dist-unit-group");
    const filterAlert = document.getElementById("filter-alert");
    const applyBtn = document.getElementById("apply-filters-btn");

    // Target tracker elements
    const targetSteps = document.getElementById("target-steps");
    const targetStart = document.getElementById("target-start");
    const targetEnd = document.getElementById("target-end");
    const targetSources = document.getElementById("target-sources");
    const targetCalcBtn = document.getElementById("target-calc-btn");
    const targetResult = document.getElementById("target-result");

    // ── Helper: render a Plotly chart from JSON ─────────────────────────
    function renderChart(containerId, chartJson) {
        const container = document.getElementById(containerId);
        if (!container || !chartJson) return;
        let parsed = typeof chartJson === "string" ? JSON.parse(chartJson) : chartJson;
        Plotly.newPlot(container, parsed.data, parsed.layout, { responsive: true });
    }

    // ── Render initial charts on page load ──────────────────────────────
    if (typeof INITIAL_CHART !== "undefined" && INITIAL_CHART) {
        renderChart("activity-chart", INITIAL_CHART);
    }
    if (typeof INITIAL_WEIGHT_CHART !== "undefined" && INITIAL_WEIGHT_CHART) {
        renderChart("weight-chart", INITIAL_WEIGHT_CHART);
    }

    // ── Helper: get selected radio value ────────────────────────────────
    function radioVal(radios) {
        for (const r of radios) {
            if (r.checked) return r.value;
        }
        return null;
    }

    // ── Show/hide distance unit selector ────────────────────────────────
    function toggleDistUnit() {
        if (!distUnitGroup) return;
        const metric = radioVal(metricRadios);
        distUnitGroup.style.display = metric === "Distance" ? "" : "none";
    }

    metricRadios.forEach(r => r.addEventListener("change", toggleDistUnit));
    toggleDistUnit();

    // ── Gather current filter state ─────────────────────────────────────
    function getFilterState() {
        const selectedSources = Array.from(dataSources.selectedOptions).map(o => o.value);
        return {
            start_date: startDate.value,
            end_date: endDate.value,
            sources: selectedSources,
            view_mode: radioVal(viewRadios),
            activity_metric: radioVal(metricRadios),
            dist_unit: radioVal(distUnitRadios) || "miles",
            weight_unit: radioVal(weightUnitRadios) || "lbs",
        };
    }

    // ── Update dashboard via AJAX ───────────────────────────────────────
    async function updateDashboard() {
        const state = getFilterState();
        filterAlert.style.display = "none";
        applyBtn.disabled = true;
        applyBtn.textContent = "Applying…";

        let resp;
        try {
            resp = await fetch("/api/update", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(state),
            });
        } catch (e) {
            filterAlert.textContent = "Network error. Please try again.";
            filterAlert.style.display = "";
            applyBtn.disabled = false;
            applyBtn.textContent = "Apply Filters";
            return;
        }

        const data = await resp.json();
        applyBtn.disabled = false;
        applyBtn.textContent = "Apply Filters";

        if (data.error) {
            filterAlert.textContent = data.error;
            filterAlert.style.display = "";
            return;
        }

        // Update activity metric cards
        const m = data.metrics;
        document.getElementById("metric-total").textContent = m.total;
        document.getElementById("metric-avg").textContent = m.avg;
        document.getElementById("metric-best").textContent = m.best_value;
        document.getElementById("metric-best-day").textContent = m.best_day;
        document.getElementById("metric-days").textContent = m.days;
        document.getElementById("card-label-total").textContent = "Total " + m.label;

        // Update activity chart via Plotly
        renderChart("activity-chart", data.activity_chart_json);

        // Update weight section if present
        if (HAS_WEIGHT && data.weight_metrics) {
            const wm = data.weight_metrics;
            const wd = document.getElementById("wmetric-latest");
            if (wd) {
                wd.textContent = wm.latest;
                document.getElementById("wmetric-avg").textContent = wm.avg;
                document.getElementById("wmetric-change").textContent = wm.change_value;
                document.getElementById("wmetric-change-delta").textContent = wm.change_delta;
                document.getElementById("wmetric-measurements").textContent = wm.measurements;
            }
            if (data.weight_chart_json) {
                renderChart("weight-chart", data.weight_chart_json);
            }
            const emptyMsg = document.getElementById("weight-empty-msg");
            if (emptyMsg) emptyMsg.style.display = "none";
        } else if (HAS_WEIGHT && !data.weight_metrics) {
            const emptyMsg = document.getElementById("weight-empty-msg");
            if (emptyMsg) {
                emptyMsg.style.display = "";
                emptyMsg.textContent = "No weight data in the selected date range.";
            }
        }
    }

    // Apply Filters button triggers the update
    applyBtn.addEventListener("click", updateDashboard);

    // Radio/select changes still auto-update (these are instant choices, not partial like dates)
    [dataSources].forEach(el => {
        el.addEventListener("change", updateDashboard);
    });
    viewRadios.forEach(r => r.addEventListener("change", updateDashboard));
    metricRadios.forEach(r => r.addEventListener("change", () => {
        toggleDistUnit();
        updateDashboard();
    }));
    distUnitRadios.forEach(r => r.addEventListener("change", updateDashboard));
    weightUnitRadios.forEach(r => r.addEventListener("change", updateDashboard));

    // ── Steps Target Tracker ────────────────────────────────────────────
    async function calculateTarget() {
        const steps = targetSteps.value;
        const tStart = targetStart.value;
        const tEnd = targetEnd.value;

        if (!steps || !tStart || !tEnd) {
            alert("Please fill in all target fields.");
            return;
        }

        targetCalcBtn.disabled = true;
        targetCalcBtn.textContent = "Calculating…";

        let resp;
        try {
            resp = await fetch("/api/target", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    target_steps: parseInt(steps, 10),
                    target_start: tStart,
                    target_end: tEnd,
                    sources: Array.from(targetSources.selectedOptions).map(o => o.value),
                }),
            });
        } catch (e) {
            alert("Network error. Please try again.");
            targetCalcBtn.disabled = false;
            targetCalcBtn.textContent = "Calculate";
            return;
        }

        const data = await resp.json();
        targetCalcBtn.disabled = false;
        targetCalcBtn.textContent = "Calculate";

        if (data.error) {
            alert(data.error);
            return;
        }

        // Show results
        targetResult.style.display = "";

        document.getElementById("target-progress-bar").style.width = data.progress_pct + "%";
        document.getElementById("target-progress-label").textContent =
            data.steps_completed + " / " + data.target_steps + " steps (" + data.progress_pct + "%)";

        document.getElementById("target-completed").textContent = data.steps_completed;
        document.getElementById("target-remaining").textContent = data.remaining;
        document.getElementById("target-days-left").textContent = data.days_left;
        document.getElementById("target-daily-needed").textContent = data.daily_needed;

        const statusEl = document.getElementById("target-status");
        statusEl.textContent = data.status_label;
        statusEl.className = "target-status " + data.status;
    }

    targetCalcBtn.addEventListener("click", calculateTarget);

    // Also allow Enter key in the target steps input
    targetSteps.addEventListener("keypress", (e) => {
        if (e.key === "Enter") calculateTarget();
    });
})();
