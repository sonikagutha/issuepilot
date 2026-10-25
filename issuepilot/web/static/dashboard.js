// Dashboard: inline edits on tracked issues. Status/PR changes reload the
// page so cards regroup and counts stay correct; note edits save quietly.

const apiPath = (card) => `/api/tracked/${card.dataset.repo}/${card.dataset.number}`;

async function call(card, method, suffix = "", body) {
  const msg = card.querySelector(".js-msg");
  msg.textContent = "Saving…";
  const r = await fetch(apiPath(card) + suffix, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    msg.textContent = typeof d.detail === "string" ? d.detail : "Couldn't save, please try again.";
    return false;
  }
  msg.textContent = "Saved ✓";
  return true;
}

document.querySelectorAll(".tracked").forEach((card) => {
  card.querySelector(".js-status").addEventListener("change", async (e) => {
    if (await call(card, "PATCH", "", { status: e.target.value })) location.reload();
  });

  card.querySelector(".js-note").addEventListener("change", (e) => {
    call(card, "PATCH", "", { note: e.target.value });
  });

  card.querySelector(".js-pr-url").addEventListener("change", (e) => {
    call(card, "PATCH", "", { pr_url: e.target.value.trim() });
  });

  card.querySelector(".js-sync").addEventListener("click", async () => {
    const prUrl = card.querySelector(".js-pr-url").value.trim();
    if (!(await call(card, "PATCH", "", { pr_url: prUrl }))) return;
    if (await call(card, "POST", "/sync-pr")) location.reload();
  });

  card.querySelector(".js-remove").addEventListener("click", async () => {
    if (await call(card, "DELETE")) card.remove();
  });
});
