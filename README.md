# IssuePilot

Agentic GitHub issue triage: analyzes issues in a repository and estimates
difficulty, effort, required skills, and contribution suitability using a
controlled multi-agent LangGraph pipeline (not a single autonomous agent).

## Status

Milestone 1 in progress — single-issue vertical slice. See
[docs/roadmap.md](docs/roadmap.md) for the phase-by-phase plan (cozy UI,
starred issues + contribution dashboard, beginner repo suggestions,
difficulty scoring, Gemma support).

## Setup

```bash
uv sync
cp .env.example .env   # fill in GITHUB_TOKEN and an LLM provider key
```

## Usage (target, not all implemented yet)

```bash
uv run issuepilot analyze owner/repo --issue 123
uv run issuepilot serve          # local web UI at http://127.0.0.1:8000
```

## Architecture

See project docs / conversation history for the full design. Short version:
GitHub Collector → Filter → Issue Investigation Agent → Repository
Investigation Agent → History Investigation Agent → Complexity Analysis
Agent (explicit weighted rubric, not LLM vibes) → Recommendation Engine →
Report. Orchestrated with LangGraph; every node has typed Pydantic
input/output; LLM calls use structured outputs throughout.
