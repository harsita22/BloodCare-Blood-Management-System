
document.addEventListener("DOMContentLoaded", function () {
    loadDashboardData();
});

// ==========================================
// LOAD DASHBOARD DATA FROM FLASK + MYSQL
// ==========================================

async function loadDashboardData() {
    try {
        const response = await fetch("/api/dashboard");
        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.error || "Unable to load dashboard data.");
        }

        // Update summary cards
        updateElement("totalUnits", data.total_units);
        updateElement("totalDonors", data.total_donors);
        updateElement("totalRequests", data.total_requests);

        if (data.total_matches !== undefined) {
            updateElement("totalMatches", data.total_matches);
        }

        // Update blood group cards if the API supplies them
        if (Array.isArray(data.blood_groups)) {
            data.blood_groups.forEach(function (group) {
                const groupName = String(group.blood_group)
                    .replace("+", "plus")
                    .replace("-", "minus");

                updateElement("blood-" + groupName, group.units + " units");
            });
        }

        console.log("BloodCare dashboard loaded successfully.");
    } catch (error) {
        console.error("Could not load dashboard data:", error);
        showDashboardMessage("Dashboard data could not be loaded. Please refresh the page.");
    }
}

// ==========================================
// UPDATE HTML ELEMENTS
// ==========================================

function updateElement(id, value) {
    const element = document.getElementById(id);

    if (element && value !== undefined && value !== null) {
        element.innerText = value;
    }
}

// ==========================================
// SHOW DASHBOARD MESSAGE
// ==========================================

function showDashboardMessage(message) {
    const element = document.getElementById("message");

    if (element) {
        element.textContent = message;
        element.style.display = "block";
    }
}

// ==========================================
// EMERGENCY MATCHING BUTTON
// ==========================================

function showEmergencyMessage() {
    window.location.href = "/emergency-matching";
}

// ==========================================
// START MATCHING BUTTON
// ==========================================

function startMatching() {
    window.location.href = "/hospital-requests";
}

// ==========================================
// DASHBOARD QUICK ACTIONS
// ==========================================

function openModule(module) {
    switch (module) {
        case "donor":
            window.location.href = "/donors";
            break;

        case "request":
            window.location.href = "/hospital-requests";
            break;

        case "inventory":
            window.location.href = "/inventory";
            break;

        case "reports":
            window.location.href = "/reports";
            break;

        default:
            showDashboardMessage("This module is not available yet.");
    }
}


// BLOODCARE NEON GLASS INTERACTIONS
(function () {
    "use strict";

    if (window.__bloodCareReferenceUI) return;
    window.__bloodCareReferenceUI = true;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const finePointer = window.matchMedia("(hover:hover) and (pointer:fine)").matches;

    function install() {
        const dashboard = document.querySelector(".dashboard");
        const hero = document.querySelector(".welcome-section");
        const main = document.querySelector(".main-content");
        if (!dashboard) return;

        // Add decorative 3D cube without changing existing hero content or buttons.
        if (hero && !hero.querySelector(".bc-cube-scene")) {
            const scene = document.createElement("div");
            scene.className = "bc-cube-scene";
            scene.setAttribute("aria-hidden", "true");
            scene.innerHTML =
                '<div class="bc-cube-orbit"></div>' +
                '<div class="bc-cube-orbit orbit-two"></div>' +
                '<div class="bc-cube">' +
                '<div class="bc-cube-face">BLOOD</div>' +
                '<div class="bc-cube-face">RBC</div>' +
                '<div class="bc-cube-face">PLASMA</div>' +
                '<div class="bc-cube-face">O+</div>' +
                '<div class="bc-cube-face">A+</div>' +
                '<div class="bc-cube-face">PLT</div>' +
                '</div>';
            hero.appendChild(scene);
        }

        if (main && finePointer) {
            main.addEventListener("pointermove", function (event) {
                const r = main.getBoundingClientRect();
                if (!r.width || !r.height) return;
                main.style.setProperty("--bc-light-x",
                    ((event.clientX - r.left) / r.width * 100) + "%");
                main.style.setProperty("--bc-light-y",
                    ((event.clientY - r.top) / r.height * 100) + "%");
            }, { passive: true });
        }

        const cards = dashboard.querySelectorAll(
            ".stats-grid .stat-card, .content-grid > .panel, .lower-grid > .panel"
        );

        cards.forEach(function (card) {
            if (card.dataset.bcReferenceReady === "true") return;
            card.dataset.bcReferenceReady = "true";
            card.classList.add("bc-tilt-card");

            // Remove only duplicate glare elements from earlier installations.
            const oldGlares = card.querySelectorAll(":scope > .bc-card-glare");
            oldGlares.forEach(function (g, index) {
                if (index > 0) g.remove();
            });

            if (!card.querySelector(":scope > .bc-card-glare")) {
                const glare = document.createElement("span");
                glare.className = "bc-card-glare";
                glare.setAttribute("aria-hidden", "true");
                card.appendChild(glare);
            }

            if (reduced || !finePointer) return;

            card.addEventListener("pointermove", function (event) {
                const r = card.getBoundingClientRect();
                if (!r.width || !r.height) return;
                const px = (event.clientX - r.left) / r.width;
                const py = (event.clientY - r.top) / r.height;

                card.style.setProperty("--bc-gx", (px * 100) + "%");
                card.style.setProperty("--bc-gy", (py * 100) + "%");

                const x = (0.5 - py) * 11;
                const y = (px - 0.5) * 13;
                card.style.transform =
                    "perspective(850px) translateY(-3px) rotateX(" +
                    x.toFixed(2) + "deg) rotateY(" + y.toFixed(2) + "deg)";
            }, { passive: true });

            card.addEventListener("pointerleave", function () {
                card.style.transform = "";
                card.style.removeProperty("--bc-gx");
                card.style.removeProperty("--bc-gy");
            }, { passive: true });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", install, { once: true });
    } else {
        install();
    }
})();