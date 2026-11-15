const messageBox = document.getElementById("matchingMessage");

function showMatchingMessage(message) {
    messageBox.textContent = message;
}

async function fetchJSON(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok || data.success === false) {
        throw new Error(data.error || data.message || `Request failed: ${response.status}`);
    }
    return data;
}

function cell(value) {
    const td = document.createElement("td");
    td.textContent = value ?? "?";
    return td;
}

function addRow(tbody, values) {
    const tr = document.createElement("tr");
    values.forEach(value => tr.appendChild(cell(value)));
    tbody.appendChild(tr);
}

function emptyRow(tbody, columns, text) {
    tbody.replaceChildren();
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = columns;
    td.textContent = text;
    tr.appendChild(td);
    tbody.appendChild(tr);
}

async function loadMatchingPage() {
    showMatchingMessage("Loading matching data...");

    try {
        const [requestData, unitData, historyData] = await Promise.all([
            fetchJSON("/api/hospital-requests"),
            fetchJSON("/api/blood-units"),
            fetchJSON("/api/matching-history")
        ]);

        const requests = (requestData.requests || [])
            .filter(r => r.request_status === "Pending");
        const units = (unitData.blood_units || [])
            .filter(u => u.status === "Available" &&
                         u.expiry_date >= new Date().toISOString().slice(0, 10));
        const matches = historyData.matches || [];

        document.getElementById("pendingCount").textContent = requests.length;
        document.getElementById("availableCount").textContent = units.length;
        document.getElementById("matchCount").textContent = matches.length;

        const requestBody = document.getElementById("pendingRequestsBody");
        requestBody.replaceChildren();

        if (!requests.length) {
            emptyRow(requestBody, 7, "No pending requests.");
        } else {
            requests.forEach(r => {
                const tr = document.createElement("tr");
                [
                    r.request_id, r.hospital_name, r.blood_group,
                    r.component_name, `${r.quantity_ml} mL`, r.emergency_level
                ].forEach(v => tr.appendChild(cell(v)));

                const actionCell = document.createElement("td");
                const button = document.createElement("button");
                button.className = "matching-action";
                button.textContent = "Find matches";
                button.addEventListener("click", () => showCandidates(r));
                actionCell.appendChild(button);
                tr.appendChild(actionCell);
                requestBody.appendChild(tr);
            });
        }

        const historyBody = document.getElementById("matchingHistoryBody");
        historyBody.replaceChildren();

        if (!matches.length) {
            emptyRow(historyBody, 7, "No matching records found.");
        } else {
            matches.forEach(m => {
                const tr = document.createElement("tr");
                [
                    m.matching_id, m.request_id, m.unit_id,
                    `${m.matched_quantity_ml} mL`, m.matching_date,
                    m.matching_status
                ].forEach(value => tr.appendChild(cell(value)));

                const actionCell = document.createElement("td");

                if (m.matching_status === "Proposed") {
                    const approveButton = document.createElement("button");
                    approveButton.className = "matching-action";
                    approveButton.textContent = "Approve & Reserve";

                    approveButton.addEventListener("click", async () => {
                        if (!confirm(
                            `Approve match #${m.matching_id} and reserve ${m.matched_quantity_ml} mL for request #${m.request_id}?`
                        )) return;

                        approveButton.disabled = true;
                        try {
                            const result = await fetchJSON(
                                `/api/matching-approval/${encodeURIComponent(m.matching_id)}`,
                                { method: "POST" }
                            );
                            showMatchingMessage(result.message);
                            await loadMatchingPage();
                        } catch (error) {
                            showMatchingMessage(`Approval failed: ${error.message}`);
                            approveButton.disabled = false;
                        }
                    });

                    actionCell.appendChild(approveButton);
                } else {
                    actionCell.textContent = "—";
                }

                tr.appendChild(actionCell);
                historyBody.appendChild(tr);
            });
        }

        showMatchingMessage("Matching data loaded from MySQL.");
    } catch (error) {
        showMatchingMessage(`Unable to load matching data: ${error.message}`);
    }
}

async function showCandidates(request) {
    const body = document.getElementById("candidateUnitsBody");
    document.getElementById("candidateIntro").textContent =
        `Candidates for request #${request.request_id}: ${request.blood_group} ${request.component_name}.`;

    body.replaceChildren();
    showMatchingMessage(`Searching eligible units for request #${request.request_id}...`);

    try {
        const data = await fetchJSON(
            `/api/matching-candidates/${encodeURIComponent(request.request_id)}`
        );
        const candidates = data.candidates || [];

        if (!candidates.length) {
            emptyRow(body, 7, "No eligible candidate units found for this request.");
            showMatchingMessage("Search completed. No eligible candidates were found.");
            return;
        }

        candidates.forEach(unit => {
            const tr = document.createElement("tr");
            [
                unit.unit_id,
                unit.blood_group,
                unit.component_name,
                `${unit.quantity_ml} mL`,
                unit.expiry_date,
                unit.location_name || "Location not recorded"
            ].forEach(value => tr.appendChild(cell(value)));

            const actionCell = document.createElement("td");
            const quantityInput = document.createElement("input");
            quantityInput.type = "number";
            quantityInput.min = "1";
            quantityInput.max = String(Math.min(
                Number(unit.quantity_ml),
                Number(data.requested_quantity_ml)
            ));
            quantityInput.value = quantityInput.max;
            quantityInput.style.width = "90px";
            quantityInput.setAttribute("aria-label", `Quantity in mL for unit ${unit.unit_id}`);

            const recordButton = document.createElement("button");
            recordButton.className = "matching-action";
            recordButton.textContent = "Record proposed match";

            recordButton.addEventListener("click", async () => {
                const quantity = Number(quantityInput.value);
                if (!Number.isInteger(quantity) || quantity <= 0) {
                    showMatchingMessage("Enter a valid positive quantity in mL.");
                    return;
                }

                recordButton.disabled = true;
                try {
                    const result = await fetchJSON("/api/matching", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            request_id: Number(request.request_id),
                            unit_id: Number(unit.unit_id),
                            matched_quantity_ml: quantity
                        })
                    });

                    showMatchingMessage(
                        `Proposed match #${result.matching_id} recorded for request #${result.request_id}, unit #${result.unit_id}. Stock has not been reserved or distributed.`
                    );

                    await loadMatchingPage();
                    await showCandidates(request);
                } catch (error) {
                    showMatchingMessage(`Could not record proposed match: ${error.message}`);
                    recordButton.disabled = false;
                }
            });

            actionCell.appendChild(quantityInput);
            actionCell.appendChild(document.createTextNode(" mL "));
            actionCell.appendChild(recordButton);
            tr.appendChild(actionCell);
            body.appendChild(tr);
        });

        showMatchingMessage(
            `Found ${candidates.length} eligible candidate unit(s). Review the quantity before recording a proposal.`
        );
    } catch (error) {
        emptyRow(body, 7, "Could not load candidates.");
        showMatchingMessage(`Candidate search failed: ${error.message}`);
    }
}

document.getElementById("refreshMatching")
    .addEventListener("click", loadMatchingPage);

loadMatchingPage();

