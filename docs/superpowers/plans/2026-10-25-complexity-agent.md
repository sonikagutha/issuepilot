# Complexity Analysis Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every analysis shows an Easy / Medium / Difficult badge, six rubric score bars, an effort estimate and the required skills. Starred issues keep their difficulty on the dashboard.

**Architecture:** A new LangGraph node `analyze_complexity` asks the LLM for six 1-5 dimension scores (structured output, with bounds in the schema). The difficulty label comes from the existing deterministic `rubric/scoring.py`, never from the LLM. `graph/pipeline.py` wires investigate → complexity as a compiled `StateGraph`. The web API and CLI call `run_pipeline`.

**Tech Stack:** LangGraph, LangChain structured output, Pydantic, FastAPI, sqlite3.

**Spec:** `docs/roadmap.md` — Phase 4.

## Global Constraints

- The LLM never outputs the difficulty label; `score()` with `config/rubric.yaml` does.
- Effort buckets: `"under 2 hours"`, `"half a day"`, `"1-2 days"`, `"several days"`.
- Rubric dimension descriptions from `config/rubric.yaml` are included in the system prompt.
- Badge classes: Easy → `badge--easy`, Medium → `badge--medium`, Difficult → `badge--hard`.
- Tracker gets a nullable `difficulty` column, added with `ALTER TABLE` for existing databases.

## Review Focus

1. Old `app.db` without a `difficulty` column must still open. `test_tracker_migrates_old_db`.
2. The LLM returns scores outside 1-5: schema bounds reject them (Pydantic `ge`/`le`). `test_assessment_rejects_out_of_range`.
3. The complexity step fails (e.g. a provider error): `/api/analyze` returns 502 with the message, not 500.
4. Starring from the analysis keeps the difficulty; starring from a repo page without analysis leaves it null and doesn't erase an existing one. `test_star_keeps_existing_difficulty`.
5. All scores at the threshold boundaries map exactly as `score()` says (2.0 → Easy, 3.5 → Medium). Already covered by `tests/test_rubric_scoring.py`.

---

### Task 1: Complexity node + pipeline
**Files:** create `issuepilot/models/complexity.py`, `config/prompts/v1/complexity_analysis.yaml`, `issuepilot/graph/nodes/complexity_analysis.py`, `issuepilot/graph/pipeline.py`, `tests/test_complexity_analysis.py`; modify `issuepilot/rubric/scoring.py` (`RUBRIC_PATH`, `RubricConfig.descriptions`).
**Produces:** `ComplexityAssessment` (LLM schema: six `int` fields 1-5, `effort_estimate`, `required_skills: list[str]`, `rationale`); `ComplexityReport(result: ComplexityResult, effort_estimate, required_skills, rationale)`; `analyze_complexity(issue, context, *, chat_model=None, settings=None, trace_store=None, rubric=None) -> ComplexityReport`; `run_pipeline(issue, *, chat_model=None, settings=None, trace_store=None) -> PipelineResult(context, complexity)`.

### Task 2: Wire into web, CLI, tracker, UI
**Files:** modify `issuepilot/web/server.py`, `issuepilot/cli.py`, `issuepilot/storage/tracker.py`, `static/analyze.js`, `static/repo.js` (unchanged API), `templates/dashboard.html`, `static/cozy.css`, tests.
**Produces:** `/api/analyze` response key `complexity: {difficulty, overall_score, scores: {dim: n}, effort_estimate, required_skills, rationale}`; `StarRequest.difficulty: str | None`; `TrackedIssue.difficulty: str | None`.
