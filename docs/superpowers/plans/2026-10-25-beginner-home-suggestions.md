# Beginner Home Page + Repo Suggestions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A home page where a contributor picks a level and languages and gets suggested repos. Each repo opens a page of its beginner-friendly issues, and each issue can be analyzed or starred without typing a URL.

**Architecture:** `issuepilot/discovery/suggestions.py` builds GitHub repository-search queries per level/language and falls back to a curated `config/starter_repos.yaml` when search fails. `GitHubClient` gains `search_repositories` and a `labels` filter on `list_issues`. Pages: `/` (home), `/analyze` (moved from `/`), `/repo/{owner}/{repo}`.

**Tech Stack:** GitHub REST search API, FastAPI, Jinja2, vanilla JS, pytest + respx.

**Spec:** `docs/roadmap.md` — Phase 3.

## Global Constraints

- Levels: `beginner`, `intermediate`, `advanced`. Search qualifiers per level: beginner `good-first-issues:>=5 stars:50..50000`; intermediate `help-wanted-issues:>=5 stars:>=500`; advanced `help-wanted-issues:>=10 stars:>=2000`. Always add `archived:false is:public pushed:>=<today-90d> language:<lang>`.
- Languages offered: python, javascript, typescript, go, rust, java.
- At most 6 suggestions, de-duplicated by `full_name`, ordered by stars, highest first.
- Repo page labels: beginner `good first issue`; intermediate and advanced `help wanted`. At most 30 open issues.
- The profile (level + languages) is remembered in browser `localStorage` (a per-viewer convenience) and passed to the server as query params `?level=…&lang=…&lang=…`.
- `/analyze?repo=owner/repo&issue=N` prefills the form and starts the analysis automatically.

## Review Focus

1. GitHub search fails (rate limit, network): the home page still shows curated repos with a note, not an error. `test_suggest_falls_back_to_curated`.
2. No language chosen: default to all languages, not an empty page. `test_home_without_profile_shows_picker`.
3. A repo with no labeled issues: friendly empty state with a link to analyze any issue there. `test_repo_page_empty_state`.
4. An unknown level in the query string is ignored and treated as beginner, not a 500. `test_home_unknown_level_defaults_to_beginner`.
5. The same repo returned for two languages appears once. `test_suggest_dedupes`.

---

### Task 1: Discovery module + client search/labels
**Files:** create `issuepilot/discovery/__init__.py`, `issuepilot/discovery/suggestions.py`, `config/starter_repos.yaml`, `tests/test_suggestions.py`; modify `issuepilot/github/client.py`, `tests/test_github_client.py`.
**Produces:** `Level = Literal["beginner","intermediate","advanced"]`, `LANGUAGES: tuple[str, ...]`, `ISSUE_LABEL: dict[Level, str]`; `RepoSuggestion(full_name, description, language, stars, html_url)`; `build_search_query(level, language, today: date) -> str`; `suggest_repos(client, level, languages, *, today=None, limit=6) -> tuple[list[RepoSuggestion], bool]` (bool = came from the curated fallback); `load_curated(languages) -> list[RepoSuggestion]`; `GitHubClient.search_repositories(query, sort="stars", per_page=10) -> list[dict]`; `GitHubClient.list_issues(..., labels: str | None = None)`.

### Task 2: Home, repo and analyze pages
**Files:** modify `issuepilot/web/server.py`, `templates/base.html` (nav: Home, Analyze, Dashboard), `static/analyze.js` (query prefill + autorun), `static/cozy.css`, `tests/test_web.py`; create `templates/home.html`, `templates/repo.html`, `static/home.js`, `static/repo.js`.
**Consumes:** Task 1. Phase 2's `/api/tracked` for the star buttons on the repo page.
