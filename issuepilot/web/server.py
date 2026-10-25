"""Local web UI for IssuePilot: Jinja2 pages plus a small JSON API."""

import re
from collections.abc import Iterator
from datetime import UTC, datetime
from itertools import islice
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from issuepilot.config import Provider, get_settings
from issuepilot.discovery.suggestions import ISSUE_LABEL, LANGUAGES, LEVELS, Level, suggest_repos
from issuepilot.github.client import GitHubAPIError, GitHubClient, GitHubNotFoundError
from issuepilot.github.profile import ProfileOverview, PullRequestSummary, load_profile_overview
from issuepilot.graph.pipeline import run_pipeline
from issuepilot.llm.factory import PROVIDER_NAMES, available_providers, model_label
from issuepilot.observability.trace_store import TraceStore
from issuepilot.rubric.scoring import Difficulty
from issuepilot.storage.profile import ProfileStore
from issuepilot.storage.tracker import STATUS_LABELS, Status, TrackedIssue, Tracker
from issuepilot.web.targets import parse_target

_WEB_DIR = Path(__file__).parent

app = FastAPI(title="IssuePilot")
app.mount("/static", StaticFiles(directory=_WEB_DIR / "static"), name="static")
templates = Jinja2Templates(directory=_WEB_DIR / "templates")


_PR_URL_RE = re.compile(r"^https?://(?:www\.)?github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)/pull/(?P<number>\d+)/?$")


class AnalyzeRequest(BaseModel):
    repo: str
    issue: int | None = None
    provider: Provider | None = None


class StarRequest(BaseModel):
    title: str
    html_url: str
    difficulty: Difficulty | None = None


class TrackedUpdate(BaseModel):
    status: Status | None = None
    note: str | None = None
    pr_url: str | None = None


class ProfileLink(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9-]{1,39}$")


@contextmanager
def _profile_store() -> Iterator[ProfileStore]:
    store = ProfileStore(get_settings().app_db_path)
    try:
        yield store
    finally:
        store.close()


@contextmanager
def _tracker() -> Iterator[Tracker]:
    tracker = Tracker(get_settings().app_db_path)
    try:
        yield tracker
    finally:
        tracker.close()


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest) -> dict:
    owner, repo_name, issue_number = parse_target(req.repo, req.issue)

    settings = get_settings()
    if req.provider and req.provider != settings.llm_provider:
        if req.provider not in available_providers(settings):
            raise HTTPException(400, f"{PROVIDER_NAMES[req.provider]} is not configured: add its API key to .env")
        # A copy, so one request's choice never changes the process-wide default.
        settings = settings.model_copy(update={"llm_provider": req.provider})
    try:
        with GitHubClient(settings) as client:
            gh_issue = client.fetch_issue(owner, repo_name, issue_number)
    except GitHubNotFoundError as exc:
        raise HTTPException(404, f"not found on GitHub: {owner}/{repo_name}#{issue_number}") from exc
    except GitHubAPIError as exc:
        raise HTTPException(502, f"GitHub error: {exc}") from exc

    trace_store = TraceStore(settings.trace_db_path)
    try:
        result = run_pipeline(gh_issue, settings=settings, trace_store=trace_store)
    except ValueError as exc:  # misconfiguration, e.g. a missing API key
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # provider/LLM failure: report it rather than a bare 500
        raise HTTPException(502, f"analysis failed: {exc}") from exc
    finally:
        trace_store.close()

    with _tracker() as tracker:
        starred = tracker.get(f"{owner}/{repo_name}", issue_number) is not None

    context, complexity = result.context, result.complexity
    analysis = context.analysis
    return {
        "starred": starred,
        "model": model_label(settings),
        "title": gh_issue.title,
        "number": gh_issue.number,
        "html_url": gh_issue.html_url,
        "repo": f"{owner}/{repo_name}",
        "summary": analysis.summary,
        "stated_requirements": analysis.stated_requirements,
        "likely_relevant_paths": analysis.likely_relevant_paths,
        "ambiguities": analysis.ambiguities,
        "referenced_numbers": context.referenced_numbers,
        "reasoning": analysis.reasoning,
        "complexity": {
            "difficulty": complexity.result.difficulty,
            "overall_score": complexity.result.overall_score,
            "scores": complexity.result.scores.model_dump(),
            "effort_estimate": complexity.effort_estimate,
            "required_skills": complexity.required_skills,
            "rationale": complexity.rationale,
        },
    }


@app.get("/api/tracked")
def list_tracked() -> dict:
    with _tracker() as tracker:
        return {"items": tracker.list(), "counts": tracker.counts()}


@app.post("/api/tracked/{owner}/{repo}/{number}")
def star(owner: str, repo: str, number: int, req: StarRequest) -> TrackedIssue:
    with _tracker() as tracker:
        return tracker.star(f"{owner}/{repo}", number, req.title, req.html_url, req.difficulty)


@app.patch("/api/tracked/{owner}/{repo}/{number}")
def update_tracked(owner: str, repo: str, number: int, req: TrackedUpdate) -> TrackedIssue:
    with _tracker() as tracker:
        try:
            return tracker.update(f"{owner}/{repo}", number, **req.model_dump(exclude_none=True))
        except KeyError as exc:
            raise HTTPException(404, f"{owner}/{repo}#{number} is not tracked") from exc


@app.delete("/api/tracked/{owner}/{repo}/{number}", status_code=204)
def unstar(owner: str, repo: str, number: int) -> Response:
    with _tracker() as tracker:
        if not tracker.remove(f"{owner}/{repo}", number):
            raise HTTPException(404, f"{owner}/{repo}#{number} is not tracked")
    return Response(status_code=204)


@app.post("/api/tracked/{owner}/{repo}/{number}/sync-pr")
def sync_pr(owner: str, repo: str, number: int) -> TrackedIssue:
    """Refresh the linked PR's state from GitHub and advance the status to match."""
    with _tracker() as tracker:
        item = tracker.get(f"{owner}/{repo}", number)
        if item is None:
            raise HTTPException(404, f"{owner}/{repo}#{number} is not tracked")
        m = _PR_URL_RE.match((item.pr_url or "").strip())
        if not m:
            raise HTTPException(400, "add a pull request URL like https://github.com/owner/repo/pull/123 first")

        try:
            with GitHubClient(get_settings()) as client:
                pull = client.get_pull(m["owner"], m["repo"], int(m["number"]))
        except GitHubNotFoundError as exc:
            raise HTTPException(404, f"pull request not found: {item.pr_url}") from exc
        except GitHubAPIError as exc:
            raise HTTPException(502, f"GitHub error: {exc}") from exc

        pr_state = "merged" if pull.get("merged") else pull["state"]
        return tracker.update(
            f"{owner}/{repo}", number, pr_state=pr_state, status=_status_for_pr(pr_state, item.status)
        )


def _status_for_pr(pr_state: str, current: Status) -> Status | None:
    """The status a tracked issue should move to given its PR's state, or None to leave it.

    A closed-but-unmerged PR doesn't decide anything on its own (the
    contributor may reopen it or try again), so only merged/open advance.
    """
    if pr_state == "merged":
        return "merged" if current != "merged" else None
    if pr_state == "open" and current in ("starred", "working"):
        return "pr_opened"
    return None


# Where an untracked GitHub PR of yours belongs on the dashboard.
_UNTRACKED_PR_STATUS: dict[str, Status] = {"merged": "merged", "open": "pr_opened", "closed": "dropped"}


@app.post("/api/profile")
def link_profile(req: ProfileLink) -> dict:
    """Link a GitHub username to the dashboard after checking it exists."""
    try:
        with GitHubClient(get_settings()) as client:
            user = client.get_user(req.username)
    except GitHubNotFoundError as exc:
        raise HTTPException(404, f"no GitHub user named {req.username}") from exc
    except GitHubAPIError as exc:
        raise HTTPException(502, f"GitHub error: {exc}") from exc
    with _profile_store() as store:
        store.set_username(user["login"])
    return {"login": user["login"], "avatar_url": user["avatar_url"]}


@app.delete("/api/profile", status_code=204)
def unlink_profile() -> Response:
    with _profile_store() as store:
        store.clear()
    return Response(status_code=204)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    with _profile_store() as store:
        username = store.get_username()

    overview: ProfileOverview | None = None
    profile_error = False
    if username:
        try:
            with GitHubClient(get_settings()) as client:
                overview = load_profile_overview(client, username)
        except GitHubAPIError:
            profile_error = True  # the rest of the dashboard is local and still useful

    with _tracker() as tracker:
        github_prs = _sync_with_pull_requests(tracker, overview) if overview else []
        items = tracker.list()

    # Every section holds tracked issues plus your untracked GitHub PRs,
    # sorted automatically by PR state.
    groups = {status: [i for i in items if i.status == status] for status in STATUS_LABELS}
    pr_groups = {status: [pr for pr in github_prs if _UNTRACKED_PR_STATUS[pr.state] == status] for status in STATUS_LABELS}
    counts = {status: len(groups[status]) + len(pr_groups[status]) for status in STATUS_LABELS}
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "active": "dashboard",
            "groups": groups,
            "pr_groups": pr_groups,
            "counts": counts,
            "labels": STATUS_LABELS,
            "total": sum(counts.values()),
            "username": username,
            "overview": overview,
            "profile_error": profile_error,
        },
    )


def _sync_with_pull_requests(tracker: Tracker, overview: ProfileOverview) -> list[PullRequestSummary]:
    """Advance tracked issues whose PR state changed; return PRs not tracked at all.

    A tracked issue whose pr_url is one of your PRs (or a PR tracked under
    its own number) follows that PR: merged → Merged, open → PR opened.
    """
    items = tracker.list()
    by_pr_url = {item.pr_url.rstrip("/"): item for item in items if item.pr_url}
    by_key = {(item.repo, item.number): item for item in items}

    untracked: list[PullRequestSummary] = []
    for pr in overview.pull_requests:
        item = by_pr_url.get(pr.html_url.rstrip("/")) or by_key.get((pr.repo, pr.number))
        if item is None:
            untracked.append(pr)
            continue
        status = _status_for_pr(pr.state, item.status)
        if status is not None or item.pr_state != pr.state:
            tracker.update(item.repo, item.number, pr_state=pr.state, status=status, pr_url=item.pr_url or pr.html_url)
    return untracked


@app.get("/", response_class=HTMLResponse)
def home(request: Request, level: str | None = None, lang: list[str] = Query(default=[])) -> HTMLResponse:
    """Profile picker; once a level is chosen, suggested repos for it."""
    chosen: Level = level if level in LEVELS else "beginner"
    languages = [code for code in lang if code in LANGUAGES]
    suggestions, fallback = [], False
    if level is not None:
        with GitHubClient(get_settings()) as client:
            suggestions, fallback = suggest_repos(client, chosen, languages)
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "active": "home",
            "has_profile": level is not None,
            "level": chosen,
            "levels": LEVELS,
            "languages": languages,
            "all_languages": LANGUAGES,
            "suggestions": suggestions,
            "fallback": fallback,
        },
    )


@app.get("/repo/{owner}/{repo}", response_class=HTMLResponse)
def repo_page(request: Request, owner: str, repo: str, level: str | None = None) -> HTMLResponse:
    """Open issues on one repo carrying the level's friendly label."""
    chosen: Level = level if level in LEVELS else "beginner"
    label = ISSUE_LABEL[chosen]
    try:
        with GitHubClient(get_settings()) as client:
            raw_issues = list(islice(client.list_issues(owner, repo, labels=label), 30))
            # Nothing carries the friendly label: show other open issues rather than a dead end.
            showing_other = not raw_issues
            if showing_other:
                raw_issues = list(islice(client.list_issues(owner, repo), 30))
    except GitHubNotFoundError as exc:
        raise HTTPException(404, f"repository not found: {owner}/{repo}") from exc
    except GitHubAPIError as exc:
        raise HTTPException(502, f"GitHub error: {exc}") from exc

    with _tracker() as tracker:
        starred = {item.number for item in tracker.list() if item.repo == f"{owner}/{repo}"}
    issues = [
        {
            "number": raw["number"],
            "title": raw["title"],
            "labels": [
                {"name": lbl["name"], "color": lbl.get("color") or "8a7b70"} for lbl in raw.get("labels", [])
            ],
            "age": _ago(raw.get("created_at")),
            "comments": raw.get("comments", 0),
            "html_url": raw["html_url"],
            "starred": raw["number"] in starred,
        }
        for raw in raw_issues
    ]
    return templates.TemplateResponse(
        request,
        "repo.html",
        {
            "active": "home",
            "repo": f"{owner}/{repo}",
            "label": label,
            "level": chosen,
            "issues": issues,
            "showing_other": showing_other,
        },
    )


@app.get("/analyze", response_class=HTMLResponse)
def analyze_page(request: Request) -> HTMLResponse:
    settings = get_settings()
    providers = [(p, PROVIDER_NAMES[p]) for p in available_providers(settings)]
    return templates.TemplateResponse(
        request,
        "analyze.html",
        {"active": "analyze", "providers": providers, "default_provider": settings.llm_provider},
    )


def _ago(timestamp: str | None) -> str | None:
    """'3 days ago'-style age for a GitHub ISO timestamp."""
    if not timestamp:
        return None
    seconds = (datetime.now(UTC) - datetime.fromisoformat(timestamp.replace("Z", "+00:00"))).total_seconds()
    for unit, size in (("year", 31_536_000), ("month", 2_592_000), ("day", 86_400), ("hour", 3_600)):
        if seconds >= size:
            count = int(seconds // size)
            return f"{count} {unit}{'s' if count != 1 else ''} ago"
    return "just now"
