"""Local web UI for IssuePilot: Jinja2 pages plus a small JSON API."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from issuepilot.config import get_settings
from issuepilot.github.client import GitHubAPIError, GitHubClient, GitHubNotFoundError
from issuepilot.graph.nodes.issue_investigation import investigate_issue
from issuepilot.observability.trace_store import TraceStore
from issuepilot.web.targets import parse_target

_WEB_DIR = Path(__file__).parent

app = FastAPI(title="IssuePilot")
app.mount("/static", StaticFiles(directory=_WEB_DIR / "static"), name="static")
templates = Jinja2Templates(directory=_WEB_DIR / "templates")


class AnalyzeRequest(BaseModel):
    repo: str
    issue: int | None = None


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

    analysis = context.analysis
    return {
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


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "analyze.html", {"active": "analyze"})
