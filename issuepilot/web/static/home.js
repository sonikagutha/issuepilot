// Home: remember the contributor's level/languages in this browser and
// restore them on the next visit. Storage can be unavailable (private
// mode, blocked site data), so every access is guarded.

const KEY = "issuepilot.profile";
const params = new URLSearchParams(location.search);

if (params.has("level")) {
  try {
    localStorage.setItem(KEY, JSON.stringify({ level: params.get("level"), lang: params.getAll("lang") }));
  } catch {}
} else {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(KEY)); } catch {}
  if (saved && saved.level) {
    const next = new URLSearchParams({ level: saved.level });
    (saved.lang || []).forEach((code) => next.append("lang", code));
    location.replace(`/?${next}`);
  }
}

// Suggestions are fetched server-side and can take a few seconds:
// show shimmering placeholders instead of a frozen page.
document.getElementById("profile-form").addEventListener("submit", () => {
  const btn = document.getElementById("profile-submit");
  btn.disabled = true;
  btn.textContent = "Finding friendly repos…";
  const grid = document.createElement("div");
  grid.className = "repo-grid";
  for (let i = 0; i < 6; i++) {
    const s = document.createElement("div");
    s.className = "skeleton";
    grid.append(s);
  }
  document.getElementById("suggestions").replaceChildren(grid);
});
