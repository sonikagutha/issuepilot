# IssuePilot

A cozy companion for open-source contributors: it suggests friendly
repositories for your level, explains GitHub issues with a multi-agent
LangGraph pipeline (what's asked, what's unclear, how hard it really is),
and tracks the issues you pick up alongside your GitHub contributions.

Runs on Gemini or Google's open **Gemma 4** models (also Claude / OpenAI).

## Features

- **Beginner home page**: pick your level and languages, get suggested repos
  with active `good first issue` / `help wanted` issues (curated fallback when
  GitHub search is unavailable). Repo pages fall back to other open issues.
- **Two-agent analysis** (LangGraph): the Issue Investigation Agent summarizes
  requirements, mentioned paths and open questions; the Complexity Analysis
  Agent scores six rubric dimensions. The Easy / Medium / Difficult label comes
  from a fixed weighted rubric (`config/rubric.yaml`), never from the LLM.
- **Model picker**: run any analysis on Gemma 4 or Gemini (or any provider
  with a key); every result says which model produced it.
- **Contribution dashboard**: star issues, move them through Starred → Working
  on it → PR opened → Merged, keep notes, sync PR status from GitHub.
- **GitHub profile**: link your username to see your contribution graph
  (green dots) and recent pull requests on the dashboard.
- Cozy light/dark UI; ETag-cached, rate-limit-aware GitHub client; SQLite
  trace log of every LLM call; versioned prompts in `config/prompts/`.

## Setup

```bash
uv sync
cp .env.example .env   # GITHUB_TOKEN plus at least one LLM key
```

For Gemma, set `GOOGLE_API_KEY` (free at https://aistudio.google.com/apikey)
and `LLM_PROVIDER=gemma`. `GEMMA_MODEL` picks `gemma-4-26b-a4b-it` (default)
or `gemma-4-31b-it`.

## Usage

```bash
uv run issuepilot serve                          # web UI at http://127.0.0.1:8000
uv run issuepilot serve --port 8001              # if 8000 is taken
uv run issuepilot analyze owner/repo --issue 123 # CLI analysis
uv run pytest                                    # tests
```

## Architecture

```
GitHub issue ──► Issue Investigation Agent ──► Complexity Analysis Agent ──► rubric score
                 (structured output)            (six 1-5 dimension scores)     Easy/Medium/Difficult
```

Orchestrated as a compiled LangGraph `StateGraph` (`issuepilot/graph/pipeline.py`);
every node has typed Pydantic input/output and uses structured outputs. The LLM
factory (`issuepilot/llm/factory.py`) is the only place that knows about
providers. See [docs/roadmap.md](docs/roadmap.md) for the phase plan and what's next.
