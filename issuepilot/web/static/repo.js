// Repo page: star/unstar each listed issue via the tracking API.

document.querySelectorAll(".issue-row").forEach((row) => {
  const btn = row.querySelector(".js-star");
  const path = `/api/tracked/${row.dataset.repo}/${row.dataset.number}`;
  let starred = row.dataset.starred === "true";

  const paint = () => {
    btn.textContent = starred ? "★ Starred" : "⭐ Star";
    btn.classList.toggle("is-starred", starred);
  };
  paint();

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    const r = starred
      ? await fetch(path, { method: "DELETE" })
      : await fetch(path, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: row.dataset.title, html_url: row.dataset.url }),
        });
    if (r.ok) starred = !starred;
    paint();
    btn.disabled = false;
  });
});
