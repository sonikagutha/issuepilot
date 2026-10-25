# Starred Issues + Contribution Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a contributor ⭐ an analyzed issue and track it on a `/dashboard` through Starred → Working on it → PR opened → Merged (or Dropped), with notes and an automatic PR status check.

**Architecture:** A small SQLite-backed `Tracker` in `issuepilot/storage/tracker.py` (same style as `TraceStore`), keyed by `(repo, number)`. A JSON API under `/api/tracked/{owner}/{repo}/{number}` in `issuepilot/web/server.py`. A server-rendered `dashboard.html` plus `dashboard.js` for in-place edits. PR status comes from a new `GitHubClient.get_pull`.

**Tech Stack:** sqlite3, FastAPI, Jinja2, vanilla JS, pytest + respx.

**Spec:** `docs/roadmap.md` — Phase 2.

## Global Constraints

- Statuses, in this order: `starred`, `working`, `pr_opened`, `merged`, `dropped`. Labels: Starred, Working on it, PR opened, Merged, Dropped.
- Settings field `app_db_path: Path = Path(".issuepilot/app.db")`.
- Starring an already-tracked issue is idempotent and keeps its status and note.
- PR sync: merged → status `merged`; open and the status is `starred`/`working` → `pr_opened`; closed and unmerged → status unchanged, `pr_state="closed"`.
- API data is rendered with `textContent` or Jinja autoescaping only.

## Review Focus

1. Starring the same issue twice must not reset its status. Covered by `test_star_is_idempotent`.
2. The PR URL is in another repo (a fork PR still lives on upstream, but users paste anything): accept any `github.com/o/r/pull/N`; reject non-PR URLs with 400. Covered by `test_sync_pr_rejects_non_pr_url`.
3. PATCH/DELETE/sync on an untracked issue returns 404, not 500. Covered by `test_patch_untracked_is_404`.
4. An invalid status value returns 422 from Pydantic. Covered by the `Status` Literal on the request model.
5. The dashboard survives a server restart, because state lives in SQLite. Covered by `test_tracker_persists_across_instances`.

---

### Task 1: Tracker store + GitHub `get_pull`
**Files:** create `issuepilot/storage/tracker.py`, `tests/test_tracker.py`; modify `issuepilot/config.py`, `issuepilot/github/client.py`, `tests/test_github_client.py`.
**Produces:** `Status` Literal and `STATUS_LABELS: dict[Status, str]`; `TrackedIssue(repo, number, title, html_url, status, note, pr_url, pr_state, starred_at, updated_at)`; `Tracker(db_path)` with `star(repo, number, title, html_url) -> TrackedIssue`, `get(repo, number) -> TrackedIssue | None`, `list() -> list[TrackedIssue]` (most recently updated first), `update(repo, number, *, status=None, note=None, pr_url=None, pr_state=None) -> TrackedIssue` (raises `KeyError` if untracked), `remove(repo, number) -> bool`, `counts() -> dict[Status, int]` (every status present), `close()`. `GitHubClient.get_pull(owner, repo, number) -> dict`.
- [ ] Tests: star/get, idempotent star, update + KeyError, remove, counts with zeros, list order, persistence across instances, `get_pull` via respx. Watch them fail, implement, watch them pass, commit.

### Task 2: Tracking API + star button + dashboard page
**Files:** modify `issuepilot/web/server.py`, `templates/base.html` (Dashboard nav link), `static/analyze.js` (⭐ button), `static/cozy.css`; create `templates/dashboard.html`, `static/dashboard.js`; extend `tests/test_web.py`.
**Consumes:** Task 1 `Tracker`, `get_pull`.
**Produces:** `POST /api/tracked/{owner}/{repo}/{number}` (body `{title, html_url}`) → TrackedIssue; `PATCH` same (body `{status?, note?, pr_url?}`); `DELETE` same → 204; `POST .../sync-pr` → TrackedIssue; `GET /api/tracked` → `{items, counts}`; `GET /dashboard` HTML. `/api/analyze` adds `starred: bool`.
- [ ] Tests: star via API then GET lists it; PATCH status; PATCH untracked → 404; sync-pr merged → status merged (fake GitHub); sync-pr with non-PR URL → 400; dashboard renders a starred title and the counts. Fail → implement → pass → manual browser check → commit → push.
