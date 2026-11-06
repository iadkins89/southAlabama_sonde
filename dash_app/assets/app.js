/* Small page behaviors that do not need the server. */
(function () {
    "use strict";

    // ----- Theme -----
    function setTheme(theme) {
        document.documentElement.setAttribute("data-bs-theme", theme);
        try { localStorage.setItem("sat-theme", theme); } catch (e) {}
        var icon = document.querySelector("#theme-toggle i");
        if (icon) icon.className = theme === "dark" ? "bi bi-sun" : "bi bi-moon-stars";
    }

    // ----- Relative times: any element with data-time shows "5 min ago" -----
    function timeAgo(iso) {
        var seconds = (Date.now() - new Date(iso).getTime()) / 1000;
        if (seconds < 90) return "just now";
        var minutes = Math.round(seconds / 60);
        if (minutes < 60) return minutes + " min ago";
        var hours = Math.round(minutes / 60);
        if (hours < 48) return hours + (hours === 1 ? " hour ago" : " hours ago");
        return Math.round(hours / 24) + " days ago";
    }

    function refreshTimes() {
        document.querySelectorAll("[data-time]").forEach(function (el) {
            var text = timeAgo(el.getAttribute("data-time"));
            if (el.textContent !== text) el.textContent = text;
        });
        // Dash resets the tab title after navigation, so it is set once the name appears
        var heading = document.getElementById("card-title");
        if (heading && heading.textContent) {
            var title = heading.textContent + " | South Alabama Telemetry";
            if (document.title !== title) document.title = title;
        }
        var themeIcon = document.querySelector("#theme-toggle i");
        var dark = document.documentElement.getAttribute("data-bs-theme") === "dark";
        if (themeIcon) themeIcon.className = dark ? "bi bi-sun" : "bi bi-moon-stars";
    }

    // ----- Sensor search -----
    var overlay = null, sensors = [], matches = [], chosen = 0;

    function goTo(url) {
        window.history.pushState({}, "", url);
        window.dispatchEvent(new CustomEvent("_dashprivate_pushstate"));
        window.dispatchEvent(new CustomEvent("onpopstate"));
        window.dispatchEvent(new PopStateEvent("popstate"));
        window.scrollTo(0, 0);
    }

    function label(name) {
        return name.replace(/_/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); });
    }

    function renderMatches(query) {
        var list = overlay.querySelector(".search-results");
        var q = query.trim().toLowerCase();
        matches = sensors.filter(function (s) {
            return (s.name + " " + (s.device_type || "")).replace(/_/g, " ").toLowerCase().indexOf(q.replace(/_/g, " ")) !== -1;
        }).slice(0, 8);
        chosen = Math.min(chosen, Math.max(matches.length - 1, 0));
        list.innerHTML = "";
        if (!matches.length) {
            var none = document.createElement("div");
            none.className = "search-empty";
            none.textContent = "No sensors match that search.";
            list.appendChild(none);
            return;
        }
        matches.forEach(function (s, i) {
            var row = document.createElement("button");
            row.type = "button";
            row.className = "search-row" + (i === chosen ? " is-chosen" : "");
            var state = !s.active ? "deactivated" : s.is_online ? "online" : "offline";
            var dot = document.createElement("span");
            dot.className = "status-dot status-" + state;
            var name = document.createElement("span");
            name.className = "search-name";
            name.textContent = label(s.name);
            var type = document.createElement("span");
            type.className = "search-type";
            type.textContent = (s.device_type || "sensor").replace(/_/g, " ") + " · " + state;
            row.append(dot, name, type);
            row.addEventListener("click", function () { open(s.name); });
            list.appendChild(row);
        });
    }

    function open(name) {
        closeSearch();
        goTo("/dashboard?sensor=" + encodeURIComponent(name));
    }

    function openSearch() {
        if (overlay) return;
        overlay = document.createElement("div");
        overlay.className = "search-overlay";
        overlay.innerHTML =
            '<div class="search-panel" role="dialog" aria-label="Find a sensor">' +
            '<div class="search-input-row"><i class="bi bi-search"></i>' +
            '<input class="search-input" placeholder="Find a sensor by name or type" aria-label="Find a sensor"></div>' +
            '<div class="search-results"></div></div>';
        document.body.appendChild(overlay);
        var input = overlay.querySelector(".search-input");
        input.focus();
        overlay.addEventListener("mousedown", function (e) { if (e.target === overlay) closeSearch(); });
        input.addEventListener("input", function () { chosen = 0; renderMatches(input.value); });
        input.addEventListener("keydown", function (e) {
            if (e.key === "ArrowDown") { chosen = Math.min(chosen + 1, matches.length - 1); }
            else if (e.key === "ArrowUp") { chosen = Math.max(chosen - 1, 0); }
            else if (e.key === "Enter" && matches[chosen]) { open(matches[chosen].name); return; }
            else { return; }
            e.preventDefault();
            renderMatches(input.value);
        });
        renderMatches("");
        fetch("/api/sensors").then(function (r) { return r.json(); }).then(function (data) {
            sensors = data.sort(function (a, b) { return b.active - a.active || a.name.localeCompare(b.name); });
            if (overlay) renderMatches(input.value);
        });
    }

    function closeSearch() {
        if (overlay) { overlay.remove(); overlay = null; }
    }

    // ----- Home page list filter -----
    function filterSensorList(query) {
        var q = query.trim().toLowerCase();
        // Matches can't be seen inside a closed section
        if (q) {
            document.querySelectorAll(".sensor-accordion .accordion-button.collapsed").forEach(function (section) {
                section.click();
            });
        }
        document.querySelectorAll("[data-search]").forEach(function (row) {
            var text = row.getAttribute("data-search") || "";
            row.style.display = text.indexOf(q) !== -1 ? "" : "none";
        });
    }

    // ----- Wiring -----
    document.addEventListener("click", function (e) {
        if (e.target.closest("#theme-toggle")) {
            var dark = document.documentElement.getAttribute("data-bs-theme") === "dark";
            setTheme(dark ? "light" : "dark");
        }
        if (e.target.closest("#sensor-search-open")) openSearch();

        var photoButton = e.target.closest("#photo-toggle");
        if (photoButton) {
            var opened = photoButton.parentElement.classList.toggle("photo-open");
            photoButton.setAttribute("aria-expanded", String(opened));
            photoButton.querySelector("#photo-toggle-label").textContent =
                opened ? "Hide sensor photo" : "Show sensor photo";
        }
    });

    document.addEventListener("input", function (e) {
        if (e.target.id === "sensor-filter") filterSensorList(e.target.value);
    });

    document.addEventListener("keydown", function (e) {
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
            e.preventDefault();
            overlay ? closeSearch() : openSearch();
        } else if (e.key === "Escape") {
            closeSearch();
        }
    });

    // ----- Home page list: step through each sensor's readings -----
    setInterval(function () {
        document.querySelectorAll(".sensor-row-value").forEach(function (list) {
            var readings = Array.prototype.slice.call(list.children);
            if (readings.length < 2) return;
            var shown = readings.findIndex(function (reading) { return reading.style.display !== "none"; });
            readings.forEach(function (reading, i) {
                reading.style.display = i === (shown + 1) % readings.length ? "" : "none";
            });
        });
    }, 3500);

    new MutationObserver(function () {
        clearTimeout(window.__satTimes);
        window.__satTimes = setTimeout(refreshTimes, 50);
    }).observe(document.documentElement, { childList: true, subtree: true });
    setInterval(refreshTimes, 30000);
})();
