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

// Sections start collapsed; remember which ones you opened so a status
// change (which reloads the page) doesn't fold everything back up.
const OPEN_KEY = "issuepilot.openSections";
let openSections = [];
try { openSections = JSON.parse(sessionStorage.getItem(OPEN_KEY)) || []; } catch {}
document.querySelectorAll("details.group").forEach((section) => {
  const status = [...section.classList].find((c) => c.startsWith("group--"));
  if (openSections.includes(status)) section.open = true;
  section.addEventListener("toggle", () => {
    openSections = openSections.filter((s) => s !== status);
    if (section.open) openSections.push(status);
    try { sessionStorage.setItem(OPEN_KEY, JSON.stringify(openSections)); } catch {}
  });
});
