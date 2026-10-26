// EduTrack High-Speed Instant Navigation & Client Scripts

(function () {
    const pageCache = new Map();
    let progressBar = null;

    function getProgressBar() {
        if (!progressBar) {
            progressBar = document.createElement("div");
            progressBar.id = "edutrack-progress";
            progressBar.style.position = "fixed";
            progressBar.style.top = "0";
            progressBar.style.left = "0";
            progressBar.style.height = "3px";
            progressBar.style.width = "0%";
            progressBar.style.backgroundColor = "#2563eb";
            progressBar.style.zIndex = "99999";
            progressBar.style.transition = "width 0.2s ease, opacity 0.3s ease";
            progressBar.style.boxShadow = "0 0 8px rgba(37, 99, 235, 0.6)";
            document.body.appendChild(progressBar);
        }
        return progressBar;
    }

    function showProgress() {
        const bar = getProgressBar();
        bar.style.opacity = "1";
        bar.style.width = "40%";
        setTimeout(() => {
            if (bar.style.width === "40%") bar.style.width = "75%";
        }, 150);
    }

    function completeProgress() {
        const bar = getProgressBar();
        bar.style.width = "100%";
        setTimeout(() => {
            bar.style.opacity = "0";
            setTimeout(() => {
                bar.style.width = "0%";
            }, 300);
        }, 150);
    }

    // Prefetch link HTML into memory on mouse hover or touchstart
    function prefetchLink(url) {
        if (!url || pageCache.has(url)) return;
        const parsed = new URL(url, window.location.origin);
        if (parsed.origin !== window.location.origin) return;
        if (parsed.pathname.includes("/delete") || parsed.pathname.includes("/add") || parsed.pathname.includes("/seed")) return;

        fetch(url, { headers: { "X-Requested-With": "EduTrackInstant" } })
            .then(res => res.ok ? res.text() : null)
            .then(html => {
                if (html) pageCache.set(url, html);
            })
            .catch(() => {});
    }

    // Instant seamless page swap
    function instantNavigate(url, push = true) {
        if (pageCache.has(url)) {
            renderPage(pageCache.get(url), url, push);
            return;
        }

        showProgress();
        fetch(url, { headers: { "X-Requested-With": "EduTrackInstant" } })
            .then(res => {
                if (!res.ok) throw new Error("HTTP error " + res.status);
                return res.text();
            })
            .then(html => {
                completeProgress();
                pageCache.set(url, html);
                renderPage(html, url, push);
            })
            .catch(() => {
                completeProgress();
                window.location.href = url; // Graceful fallback to regular browser navigation
            });
    }

    function renderPage(html, url, push) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, "text/html");
        const newMain = doc.querySelector(".main-content");
        const currentMain = document.querySelector(".main-content");

        if (newMain && currentMain) {
            currentMain.innerHTML = newMain.innerHTML;
            document.title = doc.title;

            if (push) {
                window.history.pushState({ url: url }, doc.title, url);
            }

            // Update active sidebar nav link
            const targetPath = new URL(url, window.location.origin).pathname;
            document.querySelectorAll(".sidebar .nav-link").forEach(link => {
                const linkPath = new URL(link.href, window.location.origin).pathname;
                if (linkPath === targetPath) {
                    link.classList.add("active");
                } else {
                    link.classList.remove("active");
                }
            });

            window.scrollTo({ top: 0, behavior: "instant" });
            initPageComponents();
        } else {
            window.location.href = url;
        }
    }

    // Intercept clicks on links for instant PJAX transitions
    function setupInstantLinks() {
        document.addEventListener("mouseover", function (e) {
            const link = e.target.closest("a");
            if (link && link.href) {
                prefetchLink(link.href);
            }
        });

        document.addEventListener("touchstart", function (e) {
            const link = e.target.closest("a");
            if (link && link.href) {
                prefetchLink(link.href);
            }
        }, { passive: true });

        document.addEventListener("click", function (e) {
            const link = e.target.closest("a");
            if (!link || !link.href) return;
            if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return; // Keep standard behavior for new tabs
            if (link.target && link.target !== "_self") return;

            const url = new URL(link.href, window.location.origin);
            if (url.origin !== window.location.origin) return;

            // Don't intercept delete or seed links
            if (url.pathname.includes("/delete") || url.pathname.includes("/seed")) {
                pageCache.clear();
                return;
            }

            e.preventDefault();
            instantNavigate(link.href, true);
        });

        // Clear cache on form submit (mutations)
        document.addEventListener("submit", function () {
            pageCache.clear();
        });

        // Handle browser Back / Forward buttons instantly
        window.addEventListener("popstate", function (e) {
            const url = (e.state && e.state.url) || window.location.href;
            instantNavigate(url, false);
        });
    }

    // Component event binders
    function initPageComponents() {
        // 1. Client search filter if present
        const searchInput = document.getElementById("searchInput");
        const studentTable = document.getElementById("studentTable");
        const noResults = document.getElementById("noResults");

        if (searchInput && studentTable) {
            searchInput.addEventListener("input", function () {
                const searchText = this.value.toLowerCase().trim();
                const rows = studentTable.querySelectorAll("tbody tr");
                let visibleCount = 0;

                rows.forEach(function (row) {
                    const rowText = row.textContent.toLowerCase();
                    const matches = rowText.includes(searchText);
                    row.hidden = !matches;
                    if (matches) visibleCount++;
                });

                if (noResults) noResults.hidden = (visibleCount !== 0);
            });
        }

        // 2. Marks page assessment selector dynamic max marks
        const assessmentSelect = document.getElementById("assessment");
        const marksInput = document.getElementById("marks_obtained");
        const marksHelp = document.getElementById("marks-help");

        if (assessmentSelect && marksInput && marksHelp) {
            assessmentSelect.addEventListener("change", function () {
                if (this.value === "Internal 1" || this.value === "Internal 2") {
                    marksInput.max = 50;
                    marksHelp.textContent = "Enter marks between 0 and 50.";
                } else if (this.value === "Semester Exam") {
                    marksInput.max = 100;
                    marksHelp.textContent = "Enter marks between 0 and 100.";
                } else {
                    marksInput.max = 100;
                    marksHelp.textContent = "Select an assessment first.";
                }
                marksInput.value = "";
            });
        }

        // 3. Auto-dismiss flash notifications after 5 seconds
        const notices = document.querySelectorAll(".notice");
        notices.forEach(function (notice) {
            setTimeout(function () {
                notice.style.transition = "opacity 0.4s ease";
                notice.style.opacity = "0";
                setTimeout(function () {
                    if (notice.parentNode) notice.parentNode.removeChild(notice);
                }, 400);
            }, 5000);
        });
    }

    // Boot
    document.addEventListener("DOMContentLoaded", function () {
        setupInstantLinks();
        initPageComponents();
    });
})();
