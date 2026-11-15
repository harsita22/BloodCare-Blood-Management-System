(function () {
    "use strict";

    const storageKey = "bloodcare-theme";
    const validPreferences = ["dark", "light", "system"];
    const root = document.documentElement;
    const systemQuery = typeof window.matchMedia === "function"
        ? window.matchMedia("(prefers-color-scheme: light)")
        : null;
    let preference = "dark";

    function readPreference() {
        try {
            const stored = window.localStorage.getItem(storageKey);
            return validPreferences.includes(stored) ? stored : "dark";
        } catch (error) {
            return "dark";
        }
    }

    function effectiveTheme(value) {
        if (value === "light") return "light";
        if (value === "system" && systemQuery) {
            return systemQuery.matches ? "light" : "dark";
        }
        return "dark";
    }

    function applyTheme(value, persist) {
        preference = validPreferences.includes(value) ? value : "dark";
        const resolved = effectiveTheme(preference);

        root.dataset.theme = resolved;
        root.dataset.themePreference = preference;
        root.style.colorScheme = resolved;

        if (persist) {
            try {
                window.localStorage.setItem(storageKey, preference);
            } catch (error) {
                // Storage may be disabled; keep the in-page selection active.
            }
        }

        window.dispatchEvent(new CustomEvent("bloodcare:themechange", {
            detail: {
                preference: preference,
                effectiveTheme: resolved
            }
        }));
    }

    function handleSystemChange() {
        if (preference === "system") {
            applyTheme("system", false);
        }
    }

    preference = readPreference();
    applyTheme(preference, false);

    if (systemQuery) {
        if (typeof systemQuery.addEventListener === "function") {
            systemQuery.addEventListener("change", handleSystemChange);
        } else if (typeof systemQuery.addListener === "function") {
            systemQuery.addListener(handleSystemChange);
        }
    }

    window.addEventListener("storage", function (event) {
        if (event.key === storageKey || event.key === null) {
            applyTheme(readPreference(), false);
        }
    });

    window.BloodCareTheme = {
        getPreference: function () {
            return preference;
        },
        getEffectiveTheme: function () {
            return effectiveTheme(preference);
        },
        setPreference: function (value) {
            if (validPreferences.includes(value)) {
                applyTheme(value, true);
            }
        }
    };
})();
