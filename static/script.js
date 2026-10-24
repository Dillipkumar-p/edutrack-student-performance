
const searchInput = document.getElementById("searchInput");
const studentTable = document.getElementById("studentTable");
const noResults = document.getElementById("noResults");

searchInput.addEventListener("input", function () {
    const searchText = this.value.toLowerCase().trim();
    const rows = studentTable.querySelectorAll("tr");
    let visibleCount = 0;

    rows.forEach(function (row) {
        const rowText = row.textContent.toLowerCase();
        const matches = rowText.includes(searchText);

        row.hidden = !matches;

        if (matches) {
            visibleCount++;
        }
    });

    noResults.hidden = visibleCount !== 0;
});

const navLinks = document.querySelectorAll(".nav-link");

navLinks.forEach(function (link) {
    link.addEventListener("click", function () {
        navLinks.forEach(function (item) {
            item.classList.remove("active");
        });

        this.classList.add("active");
    });
});
