# GitHub Profile on the Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Link a GitHub username to the dashboard and show the profile, the past year's contribution graph (green dots), and recent pull requests.

**Architecture:** `ProfileStore` (in `issuepilot/storage/profile.py`, same `app.db`) remembers the linked username. `issuepilot/github/profile.py` builds a `ProfileOverview` from three calls: REST `/users/{login}`, GraphQL `contributionsCollection.contributionCalendar`, and REST search `is:pr author:{login}`. `GitHubClient` gains `get_user`, `graphql` (POST, not cached) and `search_issues`. The dashboard renders the overview server-side. A GitHub failure shows a note and the rest of the dashboard still works.

**Tech Stack:** GitHub REST + GraphQL, sqlite3, FastAPI, Jinja2.

**Spec:** user request (2026-10-25): "link our github profile … linked to our dashboard … show the green dots".

## Global Constraints

- Contribution levels map from GraphQL `contributionLevel`: NONE→0, FIRST_QUARTILE→1, SECOND_QUARTILE→2, THIRD_QUARTILE→3, FOURTH_QUARTILE→4.
- Dot colors (light): 0 `--paper-2`, 1 `#c6e48b`, 2 `#7bc96f`, 3 `#449e48`, 4 `#196127`. Dots are circles.
- Recent PRs: 8 most recently updated, state `merged` when `pull_request.merged_at` is set, else `open`/`closed`.
- Username validation: `^[A-Za-z0-9-]{1,39}$`; an unknown user returns 404 and is not saved.

## Review Focus

1. Unknown username → 404 and nothing saved. `test_link_unknown_user_is_404`.
2. GitHub down or rate-limited while rendering → dashboard 200 with a note. `test_dashboard_profile_failure_still_renders`.
3. Invalid username characters → 422 before any GitHub call. `test_link_invalid_username_is_422`.
4. Unlinking clears the profile. `test_unlink_profile`.
5. A GraphQL `errors` payload raises `GitHubAPIError`, not a KeyError. `test_graphql_errors_raise`.

---

### Task 1: Profile store + GitHub profile data
**Files:** create `issuepilot/storage/profile.py`, `issuepilot/github/profile.py`, `tests/test_profile.py`; modify `issuepilot/github/client.py`.
**Produces:** `ProfileStore(db_path).get_username() -> str | None`, `.set_username(str)`, `.clear()`, `.close()`; `GitHubClient.get_user(login) -> dict`, `.graphql(query, variables) -> dict` (the `data` object), `.search_issues(query, sort="updated", per_page=10) -> list[dict]`; `load_profile_overview(client, login) -> ProfileOverview(profile, calendar, pull_requests)`.

### Task 2: Dashboard wiring
**Files:** modify `issuepilot/web/server.py`, `templates/dashboard.html`, `static/dashboard.js`, `static/cozy.css`, `tests/test_web.py`.
**Produces:** `POST /api/profile {username}` → profile JSON; `DELETE /api/profile` → 204; dashboard profile section.
