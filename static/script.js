// EduTrack Client Scripts

document.addEventListener("DOMContentLoaded", function () {
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
                if (matches) {
                    visibleCount++;
                }
            });

            if (noResults) {
                noResults.hidden = (visibleCount !== 0);
            }
        });
    }

    // Auto-dismiss alert notices after 5 seconds
    const notices = document.querySelectorAll(".notice");
    notices.forEach(function (notice) {
        setTimeout(function () {
            notice.style.transition = "opacity 0.5s ease";
            notice.style.opacity = "0";
            setTimeout(function () {
                if (notice.parentNode) {
                    notice.parentNode.removeChild(notice);
                }
            }, 500);
        }, 5000);
    });
});
