"""Minimal local web UI for the Issue Investigation Agent."""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from issuepilot.config import get_settings
from issuepilot.github.client import GitHubAPIError, GitHubClient, GitHubNotFoundError
from issuepilot.graph.nodes.issue_investigation import investigate_issue
from issuepilot.observability.trace_store import TraceStore
from issuepilot.web.targets import parse_target

app = FastAPI(title="IssuePilot")


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


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>IssuePilot</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 760px; margin: 40px auto; padding: 0 16px; color: #1f2328; }
  form { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 24px; }
  input { padding: 8px 10px; border: 1px solid #ccc; border-radius: 6px; font-size: 15px; }
  #repo { flex: 1; min-width: 200px; } #issue { width: 110px; }
  button { padding: 8px 16px; border: 0; border-radius: 6px; background: #1f6feb; color: #fff; font-size: 15px; cursor: pointer; }
  button:disabled { opacity: .6; }
  .card { border: 1px solid #ddd; border-radius: 8px; padding: 16px 20px; }
  .muted { color: #666; font-size: 14px; } .err { color: #c00; }
  h3 { margin-bottom: 4px; }
</style></head><body>
<h1>IssuePilot</h1>
<p class="muted">Analyze a GitHub issue with the Issue Investigation Agent.</p>
<form id="f">
  <input id="repo" placeholder="owner/repo or GitHub issue URL" required>
  <input id="issue" type="number" placeholder="Issue #">
  <button id="go">Analyze</button>
</form>
<div id="out"></div>
<script>
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const list = (title, items) => items && items.length
  ? `<h3>${title}</h3><ul>${items.map(i => `<li>${esc(i)}</li>`).join('')}</ul>` : '';
document.getElementById('f').onsubmit = async e => {
  e.preventDefault();
  const out = document.getElementById('out'), btn = document.getElementById('go');
  btn.disabled = true; out.innerHTML = '<p class="muted">Analyzing… this can take up to a minute.</p>';
  try {
    const r = await fetch('/api/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo: document.getElementById('repo').value, issue: +document.getElementById('issue').value || null }) });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || r.statusText);
    out.innerHTML = `<div class="card">
      <h2>${esc(d.title)}</h2><p class="muted">#${d.number} · ${esc(d.repo)}</p>
      <h3>Summary</h3><p>${esc(d.summary)}</p>
      ${list('Stated requirements', d.stated_requirements)}
      ${list('Likely relevant paths', d.likely_relevant_paths)}
      ${list('Ambiguities', d.ambiguities)}
      ${d.referenced_numbers.length ? `<h3>Referenced issues/PRs</h3><p>${d.referenced_numbers.map(n => '#' + n).join(', ')}</p>` : ''}
      <h3>Reasoning</h3><p class="muted">${esc(d.reasoning)}</p></div>`;
  } catch (err) { out.innerHTML = `<p class="err">Error: ${esc(err.message)}</p>`; }
  finally { btn.disabled = false; }
};
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return PAGE
