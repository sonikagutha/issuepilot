// Analyze page: posts the target to /api/analyze and renders the result.
// API data is only ever inserted via textContent, never as raw HTML.

const el = (tag, opts = {}, ...children) => {
  const node = document.createElement(tag);
  if (opts.className) node.className = opts.className;
  if (opts.text !== undefined) node.textContent = opts.text;
  if (opts.href) node.href = opts.href;
  if (opts.href) { node.target = "_blank"; node.rel = "noopener"; }
  node.append(...children);
  return node;
};

const section = (title, items) => {
  if (!items || !items.length) return [];
  return [el("h3", { text: title }), el("ul", {}, ...items.map((i) => el("li", { text: i })))];
};

function renderResult(d) {
  const repoUrl = `https://github.com/${d.repo}`;
  const refs = d.referenced_numbers.length
    ? [
        el("h3", { text: "Referenced issues/PRs" }),
        el("p", {}, ...d.referenced_numbers.flatMap((n, idx) => [
          idx ? ", " : "",
          el("a", { text: `#${n}`, href: `${repoUrl}/issues/${n}` }),
        ])),
      ]
    : [];

  return el("article", { className: "card" },
    el("h2", { text: d.title }),
    el("p", { className: "muted result-meta" },
      el("a", { text: `#${d.number} · ${d.repo}`, href: d.html_url })),
    el("h3", { text: "Summary" }),
    el("p", { text: d.summary }),
    ...section("Stated requirements", d.stated_requirements),
    ...section("Likely relevant paths", d.likely_relevant_paths),
    ...section("Ambiguities", d.ambiguities),
    ...refs,
    el("h3", { text: "Reasoning" }),
    el("p", { className: "muted reasoning", text: d.reasoning }),
  );
}

function renderError(message) {
  return el("div", { className: "card error-card" },
    el("strong", { text: "Something went wrong. " }),
    el("span", { text: message }));
}

document.getElementById("analyze-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const out = document.getElementById("out");
  const btn = document.getElementById("go");
  btn.disabled = true;
  out.replaceChildren(el("p", { className: "loading", text: "Brewing your analysis… ☕" }));

  try {
    const r = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repo: document.getElementById("repo").value,
        issue: Number(document.getElementById("issue").value) || null,
      }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) {
      const detail = typeof d.detail === "string" ? d.detail : r.statusText || "request failed";
      throw new Error(detail);
    }
    out.replaceChildren(renderResult(d));
  } catch (err) {
    out.replaceChildren(renderError(err.message));
  } finally {
    btn.disabled = false;
  }
});
