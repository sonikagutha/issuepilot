# IssuePilot Roadmap

IssuePilot helps contributors find GitHub issues that are worth their time,
understand them, and keep track of the ones they are working on.

**Rule: one feature at a time.** Each phase ships with tests, gets tried
by hand in the browser, and is committed and pushed before the next phase
starts. Each phase gets its own detailed plan in `docs/superpowers/plans/`,
written once the phase before it is done, so it builds on code that exists.

## Done

- GitHub client with ETag cache, retry/backoff and rate-limit handling
- Issue Investigation Agent (summary, requirements, paths, ambiguities)
- Provider-agnostic LLM factory (Anthropic, OpenAI, Google Gemini)
- Versioned prompts, SQLite trace store, weighted complexity rubric (not wired yet)
- CLI (`analyze`, `serve`) and a minimal single-page web UI

## Phases

### Phase 1 — Cozy web UI shell
Replace the inline HTML string with Jinja2 templates and a static stylesheet.
Warm "cozy" theme (paper/cream, serif headings, earthy badges) with a matching
dark mode. Shared layout with a top nav, so later phases add pages without
redoing the design. Same analyze behavior as today, plus web tests.
**Done when:** `issuepilot serve` shows the themed analyze page, it works on a
real issue, and `tests/test_web.py` passes.
Plan: `docs/superpowers/plans/2026-10-25-cozy-web-ui-shell.md`

### Phase 2 — Star issues + contribution dashboard
A ⭐ button on every analyzed issue saves it to a local SQLite store
(`.issuepilot/app.db`). A `/dashboard` page lists saved issues grouped by status:
**Starred → Working on it → PR opened → Merged** (or Dropped), with a status
dropdown, a personal note, and counts at the top. "Check PR status" fills in the
GitHub PR state (open/merged/closed) automatically.
**Done when:** you can star an issue, move it through every status, and the
dashboard is still correct after restarting the server.

### Phase 3 — Beginner home page with repo suggestions
A home page asks for experience level (beginner / intermediate / advanced) and
preferred languages (remembered locally). For beginners it suggests repositories
using the GitHub search qualifier `good-first-issues:>N` filtered by language and
activity, with a curated YAML list as a fallback when search fails or is
rate-limited. Clicking a repo shows its open `good first issue` / `help wanted`
issues, each one analyzable and starrable.
**Done when:** picking "Beginner + Python" shows active repos, and you can go
repo → issue → analysis → ⭐ without typing a URL.

### Phase 4 — Complexity Analysis Agent (difficulty badge)
New LangGraph node that scores the 6 rubric dimensions (structured output),
fed through the existing `rubric/scoring.py` to get Easy / Medium / Difficult.
Shown as a badge and score bars on the analysis page and on dashboard cards.
**Done when:** every analysis shows a difficulty badge and its per-dimension scores.

### Phase 5 — Gemma provider
`LLM_PROVIDER=gemma`, using the Gemma models served through the Gemini API (same
`GOOGLE_API_KEY`). Because those endpoints don't reliably support system prompts,
JSON mode or tool calling, the factory wraps Gemma in an adapter: system prompt
folded into the user turn, JSON parsed with `PydanticOutputParser`, one retry on a
parse failure. Nodes don't change. Optional: local Gemma through Ollama.
**Done when:** the whole pipeline runs end to end on Gemma.

### Later (not scheduled)
- Repository Investigation Agent (file tree + code search → likely files to change)
- History Agent (is someone already on it? stale PRs? maintainer response time)
- "Getting started" plan for a chosen issue
- Live per-agent progress in the UI
