// Header light/dark toggle. The choice is a per-browser convenience, so
// storage failures just mean it isn't remembered.

const root = document.documentElement;
const toggle = document.getElementById("theme-toggle");

const isDark = () =>
  root.dataset.theme === "dark" ||
  (!root.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);

const paintToggle = () => { toggle.textContent = isDark() ? "☀️" : "🌙"; };
paintToggle();

toggle.addEventListener("click", () => {
  root.dataset.theme = isDark() ? "light" : "dark";
  try { localStorage.setItem("issuepilot.theme", root.dataset.theme); } catch {}
  paintToggle();
});
