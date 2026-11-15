"use strict";

(function () {
    const numberFormatter = new Intl.NumberFormat(undefined, {
        maximumFractionDigits: 0
    });
    let latestReport = null;

    document.addEventListener("DOMContentLoaded", function () {
        document.getElementById("refreshReports")
            .addEventListener("click", loadReport);
        document.getElementById("exportReports")
            .addEventListener("click", exportCsv);
        document.getElementById("printReports")
            .addEventListener("click", function () {
                window.print();
            });
        loadReport();
    });

    function formatCount(value) {
        const numericValue = Number(value);
        return Number.isFinite(numericValue)
            ? numberFormatter.format(numericValue)
            : "0";
    }

    function formatVolume(value) {
        return formatCount(value) + " mL";
    }

    function setMessage(message, state) {
        const element = document.getElementById("reportsMessage");
        element.textContent = message;
        element.classList.remove("is-error", "is-success");
        if (state) {
            element.classList.add("is-" + state);
        }
    }

    async function loadReport() {
        const refreshButton = document.getElementById("refreshReports");
        refreshButton.disabled = true;
        document.getElementById("exportReports").disabled = true;
        setMessage("Loading report data...", "");

        try {
            const response = await fetch("/api/reports/summary", {
                headers: { Accept: "application/json" }
            });
            const data = await response.json();

            if (!response.ok || !data || data.success !== true || !data.overview) {
                throw new Error(
                    data && data.error
                        ? data.error
                        : "The Reports API returned an invalid response."
                );
            }

            latestReport = data;
            renderOverview(data.overview);
            renderBarChart("bloodGroupChart", data.blood_group_breakdown, {
                labelKey: "blood_group",
                valueKey: "total_units",
                format: formatCount,
                ariaLabel: "Blood group unit counts"
            });
            renderBarChart("componentChart", data.component_breakdown, {
                labelKey: "component_name",
                valueKey: "available_quantity_ml",
                format: formatVolume,
                ariaLabel: "Available inventory volume by component"
            });
            renderBarChart(
                "emergencyChart",
                data.request_breakdown && data.request_breakdown.by_emergency_level,
                {
                    labelKey: "emergency_level",
                    valueKey: "request_count",
                    format: formatCount,
                    ariaLabel: "Hospital request counts by emergency level"
                }
            );
            renderBarChart(
                "requestStatusChart",
                data.request_breakdown && data.request_breakdown.by_status,
                {
                    labelKey: "request_status",
                    valueKey: "request_count",
                    format: formatCount,
                    ariaLabel: "Hospital request counts by status"
                }
            );
            renderBarChart("matchingChart", data.matching_breakdown, {
                labelKey: "matching_status",
                valueKey: "matching_count",
                format: formatCount,
                ariaLabel: "Matching record counts by status"
            });
            renderBarChart("reservationChart", data.reservation_breakdown, {
                labelKey: "reservation_status",
                valueKey: "reservation_count",
                format: formatCount,
                ariaLabel: "Reservation counts by status"
            });
            renderHospitalTable(data.distribution_breakdown);

            document.getElementById("exportReports").disabled = false;
            setMessage("Report data is up to date.", "success");
        } catch (error) {
            latestReport = null;
            setMessage(
                "Unable to load reports. " + error.message + " Use Refresh to try again.",
                "error"
            );
            renderOverview({});
            [
                "bloodGroupChart",
                "componentChart",
                "emergencyChart",
                "requestStatusChart",
                "matchingChart",
                "reservationChart"
            ].forEach(function (id) {
                renderEmpty(id, "Report data is unavailable.");
            });
            renderHospitalTable([]);
        } finally {
            refreshButton.disabled = false;
        }
    }

    function renderOverview(overview) {
        document.querySelectorAll("[data-report-metric]").forEach(function (element) {
            const key = element.dataset.reportMetric;
            const value = overview[key];
            element.textContent = value === null || value === undefined
                ? "0"
                : element.dataset.format === "volume"
                    ? formatVolume(value)
                    : formatCount(value);
        });
    }

    function renderEmpty(containerId, message) {
        const container = document.getElementById(containerId);
        container.replaceChildren();
        const empty = document.createElement("p");
        empty.className = "chart-empty";
        empty.textContent = message;
        container.appendChild(empty);
    }

    function renderBarChart(containerId, rows, options) {
        const container = document.getElementById(containerId);
        container.replaceChildren();

        if (!Array.isArray(rows) || rows.length === 0) {
            renderEmpty(containerId, "No records available.");
            return;
        }

        const list = document.createElement("ol");
        list.className = "report-chart-list";
        list.setAttribute("aria-label", options.ariaLabel);
        const maximum = Math.max.apply(null, rows.map(function (row) {
            return Math.max(0, Number(row[options.valueKey]) || 0);
        }));

        rows.forEach(function (row) {
            const value = Math.max(0, Number(row[options.valueKey]) || 0);
            const item = document.createElement("li");
            item.className = "report-chart-row";

            const labels = document.createElement("div");
            labels.className = "report-chart-labels";
            const label = document.createElement("span");
            label.textContent = row[options.labelKey] || "Unspecified";
            const valueLabel = document.createElement("span");
            valueLabel.className = "report-chart-value";
            valueLabel.textContent = options.format(value);
            labels.append(label, valueLabel);

            const track = document.createElement("div");
            track.className = "report-bar-track";
            track.setAttribute("aria-hidden", "true");
            const fill = document.createElement("span");
            fill.className = "report-bar-fill";
            fill.style.width = maximum > 0
                ? Math.min(100, (value / maximum) * 100) + "%"
                : "0%";
            track.appendChild(fill);

            item.append(labels, track);
            list.appendChild(item);
        });

        container.appendChild(list);
    }

    function renderHospitalTable(rows) {
        const body = document.getElementById("hospitalDistributionBody");
        body.replaceChildren();

        if (!Array.isArray(rows) || rows.length === 0) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = 3;
            cell.className = "chart-empty";
            cell.textContent = "No hospital distribution records available.";
            row.appendChild(cell);
            body.appendChild(row);
            return;
        }

        const orderedRows = rows.slice().sort(function (left, right) {
            const volumeDifference =
                (Number(right.distributed_volume_ml) || 0)
                - (Number(left.distributed_volume_ml) || 0);
            return volumeDifference || String(left.hospital_name || "")
                .localeCompare(String(right.hospital_name || ""));
        });
        const maximum = Math.max.apply(null, orderedRows.map(function (row) {
            return Math.max(0, Number(row.distributed_volume_ml) || 0);
        }));

        orderedRows.forEach(function (hospital) {
            const row = document.createElement("tr");
            const nameCell = document.createElement("td");
            nameCell.textContent = hospital.hospital_name || "Unspecified";
            const countCell = document.createElement("td");
            countCell.textContent = formatCount(hospital.distribution_count);
            const volumeCell = document.createElement("td");
            volumeCell.className = "report-volume-cell";
            volumeCell.textContent = formatVolume(hospital.distributed_volume_ml);

            const track = document.createElement("div");
            track.className = "report-bar-track";
            track.setAttribute("aria-hidden", "true");
            const fill = document.createElement("span");
            fill.className = "report-bar-fill";
            const volume = Math.max(0, Number(hospital.distributed_volume_ml) || 0);
            fill.style.width = maximum > 0
                ? Math.min(100, (volume / maximum) * 100) + "%"
                : "0%";
            track.appendChild(fill);
            volumeCell.appendChild(track);

            row.append(nameCell, countCell, volumeCell);
            body.appendChild(row);
        });
    }

    function csvCell(value) {
        const text = value === null || value === undefined ? "" : String(value);
        return '"' + text.replace(/"/g, '""') + '"';
    }

    function exportCsv() {
        if (!latestReport) return;

        const rows = [["Dataset", "Category", "Metric", "Value", "Unit"]];
        const unitForMetric = function (metric) {
            return metric.toLowerCase().includes("ml") || metric.toLowerCase().includes("volume")
                ? "mL"
                : "count";
        };
        const addMetrics = function (dataset, category, record, fields) {
            fields.forEach(function (field) {
                rows.push([
                    dataset,
                    category,
                    field,
                    record[field],
                    unitForMetric(field)
                ]);
            });
        };
        const addBreakdown = function (dataset, records, categoryKey, fields) {
            if (!Array.isArray(records) || records.length === 0) {
                rows.push([dataset, "", "No records", "", ""]);
                return;
            }
            records.forEach(function (record) {
                addMetrics(dataset, record[categoryKey] || "Unspecified", record, fields);
            });
        };

        addMetrics("Overview", "All-time", latestReport.overview, [
            "total_donors",
            "total_donations",
            "total_donated_volume_ml",
            "total_blood_units",
            "available_units",
            "reserved_units",
            "distributed_units",
            "expired_units",
            "total_hospital_requests",
            "pending_requests",
            "total_matching_records",
            "total_reservations",
            "total_distribution_records",
            "total_distributed_volume_ml"
        ]);
        addBreakdown("Blood group", latestReport.blood_group_breakdown, "blood_group", [
            "total_units", "available_units", "reserved_units",
            "distributed_units", "expired_units"
        ]);
        addBreakdown("Component", latestReport.component_breakdown, "component_name", [
            "total_units", "available_quantity_ml"
        ]);

        const requestBreakdown = latestReport.request_breakdown || {};
        addBreakdown("Request emergency level", requestBreakdown.by_emergency_level,
            "emergency_level", ["request_count"]);
        addBreakdown("Request status", requestBreakdown.by_status,
            "request_status", ["request_count"]);
        addBreakdown("Matching status", latestReport.matching_breakdown,
            "matching_status", ["matching_count"]);
        addBreakdown("Reservation status", latestReport.reservation_breakdown,
            "reservation_status", ["reservation_count"]);
        addBreakdown("Hospital distribution", latestReport.distribution_breakdown,
            "hospital_name", ["distribution_count", "distributed_volume_ml"]);

        const csv = "\uFEFF" + rows.map(function (row) {
            return row.map(csvCell).join(",");
        }).join("\r\n");
        const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "bloodcare-reports-all-time.csv";
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    }
})();
