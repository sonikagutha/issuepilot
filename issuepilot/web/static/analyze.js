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
  return [
    el("section", { className: "result-section" },
      el("h3", { text: title }),
      el("ul", {}, ...items.map((i) => el("li", { text: i })))),
  ];
};

function renderResult(d) {
  const repoUrl = `https://github.com/${d.repo}`;
  const refs = d.referenced_numbers.length
    ? [
        el("h3", { text: "🔗 Referenced issues/PRs" }),
        el("p", {}, ...d.referenced_numbers.flatMap((n, idx) => [
          idx ? ", " : "",
          el("a", { text: `#${n}`, href: `${repoUrl}/issues/${n}` }),
        ])),
      ]
    : [];

  return el("article", { className: "card" },
    el("div", { className: "result-head" }, el("h2", { text: d.title }), starButton(d)),
    el("p", { className: "muted result-meta" },
      el("a", { text: `#${d.number} · ${d.repo}`, href: d.html_url })),
    complexityCard(d.complexity),
    el("h3", { text: "📝 Summary" }),
    el("p", { className: "summary", text: d.summary }),
    ...section("📋 Stated requirements", d.stated_requirements),
    ...section("📁 Likely relevant paths", d.likely_relevant_paths),
    ...section("❓ Open questions", d.ambiguities),
    ...refs,
    el("h3", { text: "🧠 Reasoning" }),
    el("p", { className: "muted reasoning", text: d.reasoning }),
  );
}

const BADGE = { Easy: "easy", Medium: "medium", Difficult: "hard" };
const DIMENSION_LABELS = {
  code_complexity: "Code complexity",
  components_affected: "Components affected",
  required_technical_knowledge: "Technical knowledge",
  testing_complexity: "Testing",
  dependencies: "Dependencies",
  requirement_ambiguity: "Ambiguity",
};

function complexityCard(c) {
  const bars = Object.entries(DIMENSION_LABELS).map(([key, label]) => {
    const value = c.scores[key];
    const fill = el("span", { className: "meter__fill" });
    fill.style.width = `${(value / 5) * 100}%`;
    fill.dataset.level = value <= 2 ? "low" : value <= 3 ? "mid" : "high";
    return el("div", { className: "meter" },
      el("span", { className: "meter__label", text: label }),
      el("span", { className: "meter__track" }, fill),
      el("span", { className: "meter__value", text: `${value}/5` }));
  });

  return el("section", { className: "complexity" },
    el("div", { className: "complexity__head" },
      el("span", { className: `badge badge--lg badge--${BADGE[c.difficulty]}`, text: c.difficulty }),
      el("span", { className: "complexity__score muted", text: `score ${c.overall_score.toFixed(2)} / 5` }),
      el("span", { className: "complexity__effort", text: `⏱ ${c.effort_estimate}` })),
    el("div", { className: "meters" }, ...bars),
    c.required_skills.length
      ? el("div", { className: "skills" },
          el("span", { className: "muted skills__label", text: "Skills you'll use:" }),
          ...c.required_skills.map((skill) => el("span", { className: "badge badge--label", text: skill })))
      : "",
    el("p", { className: "muted complexity__rationale", text: c.rationale }));
}

function starButton(d) {
  const btn = el("button", { className: "btn btn--ghost star-btn" });
  btn.type = "button";
  const path = `/api/tracked/${d.repo}/${d.number}`;
  let starred = d.starred;
  const paint = () => {
    btn.textContent = starred ? "★ Starred" : "⭐ Star for later";
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
          body: JSON.stringify({ title: d.title, html_url: d.html_url, difficulty: d.complexity.difficulty }),
        });
    if (r.ok) starred = !starred;
    paint();
    btn.disabled = false;
  });
  return btn;
}

function renderError(message) {
  return el("div", { className: "card error-card" },
    el("strong", { text: "Something went wrong. " }),
    el("span", { text: message }));
}

const form = document.getElementById("analyze-form");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const out = document.getElementById("out");
  const btn = document.getElementById("go");
  btn.disabled = true;
  out.replaceChildren(el("p", { className: "loading", text: "Brewing your analysis… ☕ (two agents: investigation, then complexity)" }));

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

// Coming from a repo page: /analyze?repo=owner/repo&issue=N prefills the
// form and runs the analysis straight away.
const params = new URLSearchParams(location.search);
if (params.get("repo")) {
  document.getElementById("repo").value = params.get("repo");
  if (params.get("issue")) {
    document.getElementById("issue").value = params.get("issue");
    form.requestSubmit();
  }
}
