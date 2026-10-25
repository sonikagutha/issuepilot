# IssuePilot demo script (≈3 minutes)

## Before you present

```bash
uv sync
uv run pytest -q                      # all green
uv run issuepilot serve --port 8001   # http://127.0.0.1:8001
```

- `.env` has `GITHUB_TOKEN`, `GOOGLE_API_KEY`, `LLM_PROVIDER=google`.
- Warm the cache once: open the home page with Beginner + Python, open one repo,
  analyze one issue. GitHub responses are ETag-cached, so the live run is faster.
- Link your GitHub on the Dashboard before the demo so the green dots are there.
- Gemini is the safe default for live demos. Show Gemma via the Model dropdown on
  an issue you've already timed.

## The story

1. **Problem (20s).** "First-time contributors open a 'good first issue' and
   find it isn't one. They can't tell what's being asked or how hard it is."

2. **Home (30s).** Pick 🌱 Beginner + Python → suggested repos (live GitHub
   search, curated fallback if search is rate-limited). Open a repo → its
   good-first-issues with real label colours. If a repo has none, it shows
   other open issues instead of a dead end.

3. **Analyze (60s).** Click ✨ Analyze. Two LangGraph agents run:
   - Issue Investigation Agent: summary, requirements, paths, open questions.
   - Complexity Analysis Agent: six 1-5 rubric scores, effort, skills.
   - Key point: **the Easy/Medium/Difficult label is computed by a fixed
     weighted rubric (`config/rubric.yaml`), not guessed by the LLM.** It's
     explainable and tunable.
   - Switch the Model dropdown to **Gemma 4** to show it runs on Google's open
     models. Every result says which model produced it.

4. **Track (40s).** ⭐ Star for later → Dashboard: Starred → Working on it →
   PR opened → Merged, notes, "Check PR status" syncs from GitHub. Your GitHub
   profile shows the contribution graph (green dots) and recent PRs, each with
   a status dropdown linked to the shelf.

5. **Engineering (20s).** Typed Pydantic I/O on every node, structured
   outputs, versioned prompts, SQLite trace log of every LLM call, ETag-cached
   rate-limit-aware GitHub client, 100+ offline tests.

## If something goes wrong

- Analysis is slow: LLM calls take 20-60s on busy days; keep a pre-analyzed tab open.
- "GitHub search is taking a nap": that's the curated fallback working as designed.
- Dashboard profile note: GitHub rate limit; the local shelf still works.
