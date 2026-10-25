# Cozy Web UI Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the inline-HTML web UI into a templated, cozy-themed app shell that later phases (dashboard, home page) plug pages into, while the analyze page keeps working the same way.

**Architecture:** `issuepilot/web.py` becomes a package `issuepilot/web/`. Routes live in `app.py`, input parsing in `targets.py`, and pages are Jinja2 templates that extend one `base.html`. CSS and JS are static files served by FastAPI's `StaticFiles`. The JSON API (`POST /api/analyze`) keeps its current response shape.

**Tech Stack:** FastAPI, Jinja2, Starlette StaticFiles, vanilla JS, pytest + FastAPI `TestClient`.

**Spec:** `docs/roadmap.md` — Phase 1.

## Global Constraints

- `uvicorn.run("issuepilot.web:app", ...)` in `cli.py` must keep working unchanged.
- No JS build step and no frontend framework. Plain JS in `static/`; fonts only from Google Fonts.
- Theme tokens on `:root`, light values: `--paper #faf6ef`, `--card #fffdf8`, `--ink #3b2f2a`, `--muted #8a7b70`, `--border #e8dfd2`, `--accent #c86b4a`, `--sage #7a9e7e`, `--amber #d9a441`, `--terracotta #c86b4a`.
- Dark values under `@media (prefers-color-scheme: dark)`: `--paper #1f1a17`, `--card #2a231f`, `--ink #efe6da`, `--muted #a89a8d`, `--border #3a312b`, `--accent #e08a68`.
- Fonts: "Fraunces" for headings, "Nunito" for body text.
- Loading copy is exactly: `Brewing your analysis… ☕`
- Layout works at 375px width with no horizontal scroll.
- All dynamic text is inserted with `textContent` or an escaping helper, never raw `innerHTML` from API data.

## Review Focus

1. Issue number in both the URL and the number field: the explicit field wins (current behavior). Test in Task 1.
2. GitHub 404 (typo in repo name or issue number) should return HTTP 404 with a readable message, not 502. Test in Task 1.
3. Missing LLM API key: the `ValueError` comes back as 400 with the message, and the page shows it in the error card. Test in Task 1.
4. A PR URL (`/pull/N`) is accepted as a target. Test in Task 1.
5. Packaged install: templates and static files must be found through paths relative to the package (`Path(__file__).parent`), not the working directory. Test in Task 2 (serving `/static/cozy.css` from a TestClient).

---

### Task 1: Split `web.py` into a package and test the API

**Files:**
- Delete: `issuepilot/web.py`
- Create: `issuepilot/web/__init__.py` (just `from issuepilot.web.app import app`)
- Create: `issuepilot/web/targets.py`
- Create: `issuepilot/web/app.py`
- Test: `tests/test_web.py`

**Interfaces:**
- Produces: `parse_target(repo: str, issue: int | None) -> tuple[str, str, int]` in `targets.py` (moved unchanged, still raises `HTTPException(400, ...)`).
- Produces: `app: FastAPI` in `issuepilot/web/app.py` with `POST /api/analyze` taking `AnalyzeRequest{repo: str, issue: int | None}` and returning `{title, number, repo, summary, stated_requirements, likely_relevant_paths, ambiguities, referenced_numbers, reasoning, html_url}`. `html_url` is new; Phase 2 stars issues by it.
- Produces: `app.py` imports `GitHubClient` and `investigate_issue` at module level, so tests can monkeypatch `issuepilot.web.app.GitHubClient` and `issuepilot.web.app.investigate_issue`.

- [ ] **Step 1: Write failing tests in `tests/test_web.py`**

```python
@pytest.mark.parametrize("repo,issue,expected", [
    ("octo/hello", 5, ("octo", "hello", 5)),
    ("https://github.com/octo/hello/issues/12", None, ("octo", "hello", 12)),
    ("https://github.com/octo/hello/pull/7", None, ("octo", "hello", 7)),
    ("https://github.com/octo/hello/issues/12", 3, ("octo", "hello", 3)),
    ("github.com/octo/hello.git", 9, ("octo", "hello", 9)),
])
def test_parse_target_accepts(repo, issue, expected): ...

def test_parse_target_rejects_garbage():       # "not a repo", 1 -> HTTPException 400
def test_parse_target_requires_number():       # "octo/hello", None -> HTTPException 400

def test_analyze_returns_analysis(client, fake_github, fake_investigate):
    r = client.post("/api/analyze", json={"repo": "octo/hello", "issue": 1})
    assert r.status_code == 200
    assert r.json()["summary"] == "Fix the thing"
    assert r.json()["html_url"] == "https://github.com/octo/hello/issues/1"

def test_analyze_github_not_found_is_404(client, monkeypatch): ...   # fetch_issue raises GitHubNotFoundError
def test_analyze_missing_llm_key_is_400(client, fake_github, monkeypatch):
    # investigate_issue raises ValueError("ANTHROPIC_API_KEY is required ...")
    # assert 400 and that message in r.json()["detail"]
```

Fixtures: `fake_github` monkeypatches `issuepilot.web.app.GitHubClient` with a context-manager stub whose `fetch_issue` returns an `Issue` built in the test. `fake_investigate` returns `IssueContext(analysis=IssueContextAnalysis(summary="Fix the thing", reasoning="r"))`. Also monkeypatch `get_settings` to return `Settings(github_token="x", trace_db_path=tmp_path / "t.db")`.

- [ ] **Step 2: Run** `uv run pytest tests/test_web.py -v`. Expected: FAIL (`ModuleNotFoundError: issuepilot.web.targets`).
- [ ] **Step 3: Create the package.** Move `parse_target` and `_REPO_RE` into `targets.py`. Move the routes into `app.py`. Catch `GitHubNotFoundError` before `GitHubAPIError` and map it to 404. Add `html_url` to the response. Keep the `GET /` page working for now (Task 2 replaces it).
- [ ] **Step 4: Run** `uv run pytest -q`. Expected: all tests pass (33 existing + new).
- [ ] **Step 5: Commit** `refactor(web): split web UI into a package and add API tests`

### Task 2: Jinja2 templates, cozy theme, and static assets

**Files:**
- Modify: `pyproject.toml` (add `jinja2`), `uv.lock` (via `uv add jinja2`)
- Create: `issuepilot/web/templates/base.html`, `issuepilot/web/templates/analyze.html`
- Create: `issuepilot/web/static/cozy.css`, `issuepilot/web/static/analyze.js`
- Modify: `issuepilot/web/app.py` (mount static, render template on `GET /`)
- Modify: `README.md` (usage: `uv run issuepilot serve`)
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `app`, `POST /api/analyze` from Task 1.
- Produces: `templates: Jinja2Templates` in `app.py`, rooted at `Path(__file__).parent / "templates"`; static mounted at `/static` with `name="static"`.
- Produces: `base.html` blocks `title` and `content`, a `<header>` nav containing `<a href="/">Analyze</a>` (Phases 2 and 3 add Dashboard and Home links here), and an `active` variable that highlights the current nav item.
- Produces: CSS classes later pages reuse: `.card`, `.muted`, `.badge`, `.badge--easy` (sage), `.badge--medium` (amber), `.badge--hard` (terracotta), `.btn`, `.btn--ghost`, `.error-card`.

- [ ] **Step 1: Add failing tests**

```python
def test_index_renders_cozy_shell(client):
    r = client.get("/")
    assert r.status_code == 200
    assert '<link rel="stylesheet" href="/static/cozy.css"' in r.text
    assert 'id="analyze-form"' in r.text

def test_static_css_served(client):
    r = client.get("/static/cozy.css")
    assert r.status_code == 200
    assert "--paper: #faf6ef" in r.text
```

- [ ] **Step 2: Run** `uv run pytest tests/test_web.py -v`. Expected: the 2 new tests FAIL.
- [ ] **Step 3: Implement.** Run `uv add jinja2`. In `base.html`: Google Fonts link for Fraunces and Nunito, the nav, and a soft footer ("made with care for first-time contributors"). In `analyze.html`: the form (`#analyze-form`, `#repo`, `#issue`, `#go`) and an `#out` container. Move the current page script into `analyze.js`: show the exact loading copy, render the result as a `.card` with sections (Summary, Stated requirements, Likely relevant paths, Ambiguities, Referenced issues/PRs linked to GitHub, Reasoning in `.muted`), and show errors in `.error-card`. Use the theme tokens from Global Constraints, 12px card radius, and a max content width of 760px.
- [ ] **Step 4: Run** `uv run pytest -q`. Expected: all pass.
- [ ] **Step 5: Manual check.** Run `uv run issuepilot serve`, analyze a real issue (e.g. `https://github.com/pallets/flask/issues/<open issue>`), and check light mode, dark mode, the 375px width, and the error card (bad repo name).
- [ ] **Step 6: Commit** `feat(web): cozy themed UI shell with Jinja2 templates`, then push.
