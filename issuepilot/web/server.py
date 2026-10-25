"""Local web UI for IssuePilot: Jinja2 pages plus a small JSON API."""

import re
from collections.abc import Iterator
from itertools import islice
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from issuepilot.config import get_settings
from issuepilot.discovery.suggestions import ISSUE_LABEL, LANGUAGES, LEVELS, Level, suggest_repos
from issuepilot.github.client import GitHubAPIError, GitHubClient, GitHubNotFoundError
from issuepilot.graph.nodes.issue_investigation import investigate_issue
from issuepilot.observability.trace_store import TraceStore
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


class StarRequest(BaseModel):
    title: str
    html_url: str


class TrackedUpdate(BaseModel):
    status: Status | None = None
    note: str | None = None
    pr_url: str | None = None


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
    try:
        with GitHubClient(settings) as client:
            gh_issue = client.fetch_issue(owner, repo_name, issue_number)
    except GitHubNotFoundError as exc:
        raise HTTPException(404, f"not found on GitHub: {owner}/{repo_name}#{issue_number}") from exc
    except GitHubAPIError as exc:
        raise HTTPException(502, f"GitHub error: {exc}") from exc

    trace_store = TraceStore(settings.trace_db_path)
    try:
        context = investigate_issue(gh_issue, settings=settings, trace_store=trace_store)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        trace_store.close()

    with _tracker() as tracker:
        starred = tracker.get(f"{owner}/{repo_name}", issue_number) is not None

    analysis = context.analysis
    return {
        "starred": starred,
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
    }


@app.get("/api/tracked")
def list_tracked() -> dict:
    with _tracker() as tracker:
        return {"items": tracker.list(), "counts": tracker.counts()}


@app.post("/api/tracked/{owner}/{repo}/{number}")
def star(owner: str, repo: str, number: int, req: StarRequest) -> TrackedIssue:
    with _tracker() as tracker:
        return tracker.star(f"{owner}/{repo}", number, req.title, req.html_url)


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
        status: Status | None = None
        if pr_state == "merged":
            status = "merged"
        elif pr_state == "open" and item.status in ("starred", "working"):
            status = "pr_opened"
        return tracker.update(f"{owner}/{repo}", number, pr_state=pr_state, status=status)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    with _tracker() as tracker:
        items = tracker.list()
        counts = tracker.counts()
    groups = {status: [i for i in items if i.status == status] for status in STATUS_LABELS}
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"active": "dashboard", "groups": groups, "counts": counts, "labels": STATUS_LABELS, "total": len(items)},
    )


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
            "labels": [lbl["name"] for lbl in raw.get("labels", [])],
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
    return templates.TemplateResponse(request, "analyze.html", {"active": "analyze"})
