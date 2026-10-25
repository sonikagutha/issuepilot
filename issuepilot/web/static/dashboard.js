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

// GitHub profile link/unlink.
const linkForm = document.getElementById("profile-link-form");
if (linkForm) {
  linkForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = linkForm.querySelector(".js-profile-msg");
    msg.textContent = "Looking you up on GitHub…";
    const r = await fetch("/api/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: document.getElementById("profile-username").value.trim() }),
    });
    if (r.ok) { location.reload(); return; }
    const d = await r.json().catch(() => ({}));
    msg.textContent = r.status === 422
      ? "That doesn't look like a GitHub username."
      : typeof d.detail === "string" ? d.detail : "Couldn't connect, please try again.";
  });
}

const unlink = document.getElementById("profile-unlink");
if (unlink) {
  unlink.addEventListener("click", async () => {
    if ((await fetch("/api/profile", { method: "DELETE" })).ok) location.reload();
  });
}

// Recent pull requests: the status dropdown tracks the PR on the shelf, or
// updates the tracked issue it fixes. Reload so cards and counts regroup.
document.querySelectorAll(".pr-list__item").forEach((row) => {
  const select = row.querySelector(".js-pr-status");
  const path = `/api/tracked/${row.dataset.repo}/${row.dataset.number}`;
  const json = (method, body) =>
    fetch(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

  select.addEventListener("change", async () => {
    const value = select.value;
    if (!value) return;
    select.disabled = true;

    let ok;
    if (value === "__remove") {
      ok = (await fetch(path, { method: "DELETE" })).ok;
    } else if (row.dataset.tracked === "true") {
      ok = (await json("PATCH", { status: value })).ok;
    } else {
      ok = (await json("POST", { title: row.dataset.title, html_url: row.dataset.url })).ok
        && (await json("PATCH", { status: value, pr_url: row.dataset.url })).ok;
    }

    if (ok) location.reload();
    else select.disabled = false;
  });
});
