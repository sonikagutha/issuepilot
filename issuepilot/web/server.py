"""Local web UI for IssuePilot: Jinja2 pages plus a small JSON API."""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from issuepilot.config import get_settings
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
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "analyze.html", {"active": "analyze"})
