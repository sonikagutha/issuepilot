from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import issuepilot.web.server as web_app
from issuepilot.config import Settings
from issuepilot.github.client import GitHubAPIError, GitHubNotFoundError
from issuepilot.github.models import Issue
from issuepilot.models.issue_context import IssueContext, IssueContextAnalysis
from issuepilot.web.targets import parse_target


def _issue() -> Issue:
    return Issue(
        number=1,
        title="Fix the thing",
        body="It is broken.",
        state="open",
        labels=["bug"],
        author="octocat",
        comment_count=0,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        html_url="https://github.com/octo/hello/issues/1",
    )


class _FakeGitHubClient:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def __enter__(self) -> "_FakeGitHubClient":
        return self

    def __exit__(self, *exc: object) -> None:
        pass

    def fetch_issue(self, owner: str, repo: str, number: int) -> Issue:
        return _issue()

    def get_pull(self, owner: str, repo: str, number: int) -> dict:
        return {"number": number, "state": "closed", "merged": True}

    def search_repositories(self, query: str, sort: str = "stars", per_page: int = 10) -> list[dict]:
        return [
            {
                "full_name": "octo/hello",
                "description": "A friendly repo",
                "language": "Python",
                "stargazers_count": 1234,
                "html_url": "https://github.com/octo/hello",
            }
        ]

    def list_issues(self, owner: str, repo: str, state: str = "open", per_page: int = 100, labels=None):
        yield {
            "number": 1,
            "title": "Fix the thing",
            "labels": [{"name": "good first issue"}],
            "comments": 2,
            "html_url": "https://github.com/octo/hello/issues/1",
        }


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> TestClient:
    settings = Settings(
        github_token="x",
        trace_db_path=tmp_path / "t.db",
        cache_db_path=tmp_path / "c.db",
        app_db_path=tmp_path / "app.db",
    )
    monkeypatch.setattr(web_app, "get_settings", lambda: settings)
    return TestClient(web_app.app)


@pytest.fixture
def fake_github(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_app, "GitHubClient", _FakeGitHubClient)


@pytest.fixture
def fake_investigate(monkeypatch: pytest.MonkeyPatch) -> None:
    context = IssueContext(analysis=IssueContextAnalysis(summary="Fix the thing", reasoning="r"))
    monkeypatch.setattr(web_app, "investigate_issue", lambda *a, **kw: context)


@pytest.mark.parametrize(
    "repo,issue,expected",
    [
        ("octo/hello", 5, ("octo", "hello", 5)),
        ("https://github.com/octo/hello/issues/12", None, ("octo", "hello", 12)),
        ("https://github.com/octo/hello/pull/7", None, ("octo", "hello", 7)),
        ("https://github.com/octo/hello/issues/12", 3, ("octo", "hello", 3)),
        ("github.com/octo/hello.git", 9, ("octo", "hello", 9)),
    ],
)
def test_parse_target_accepts(repo: str, issue: int | None, expected: tuple[str, str, int]) -> None:
    assert parse_target(repo, issue) == expected


def test_parse_target_rejects_garbage() -> None:
    with pytest.raises(HTTPException) as exc:
        parse_target("not a repo", 1)
    assert exc.value.status_code == 400


def test_parse_target_requires_number() -> None:
    with pytest.raises(HTTPException) as exc:
        parse_target("octo/hello", None)
    assert exc.value.status_code == 400


def test_analyze_returns_analysis(client: TestClient, fake_github: None, fake_investigate: None) -> None:
    r = client.post("/api/analyze", json={"repo": "octo/hello", "issue": 1})

    assert r.status_code == 200
    assert r.json()["summary"] == "Fix the thing"
    assert r.json()["html_url"] == "https://github.com/octo/hello/issues/1"


def test_analyze_github_not_found_is_404(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class _NotFoundClient(_FakeGitHubClient):
        def fetch_issue(self, owner: str, repo: str, number: int) -> Issue:
            raise GitHubNotFoundError(404, "not found")

    monkeypatch.setattr(web_app, "GitHubClient", _NotFoundClient)

    r = client.post("/api/analyze", json={"repo": "octo/nope", "issue": 1})

    assert r.status_code == 404


def test_analyze_missing_llm_key_is_400(
    client: TestClient, fake_github: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise(*args: object, **kwargs: object) -> IssueContext:
        raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")

    monkeypatch.setattr(web_app, "investigate_issue", _raise)

    r = client.post("/api/analyze", json={"repo": "octo/hello", "issue": 1})

    assert r.status_code == 400
    assert "ANTHROPIC_API_KEY is required" in r.json()["detail"]


def test_analyze_page_renders_cozy_shell(client: TestClient) -> None:
    r = client.get("/analyze")

    assert r.status_code == 200
    assert '<link rel="stylesheet" href="/static/cozy.css"' in r.text
    assert 'id="analyze-form"' in r.text


def test_static_css_served(client: TestClient) -> None:
    r = client.get("/static/cozy.css")

    assert r.status_code == 200
    assert "--paper: #faf6ef" in r.text


ISSUE_PATH = "/api/tracked/octo/hello/1"
STAR_BODY = {"title": "Fix the thing", "html_url": "https://github.com/octo/hello/issues/1"}


def test_star_then_list(client: TestClient) -> None:
    r = client.post(ISSUE_PATH, json=STAR_BODY)
    assert r.status_code == 200
    assert r.json()["status"] == "starred"

    listing = client.get("/api/tracked").json()

    assert [i["number"] for i in listing["items"]] == [1]
    assert listing["counts"]["starred"] == 1


def test_analyze_reports_starred(client: TestClient, fake_github: None, fake_investigate: None) -> None:
    client.post(ISSUE_PATH, json=STAR_BODY)

    r = client.post("/api/analyze", json={"repo": "octo/hello", "issue": 1})

    assert r.json()["starred"] is True


def test_patch_status_and_note(client: TestClient) -> None:
    client.post(ISSUE_PATH, json=STAR_BODY)

    r = client.patch(ISSUE_PATH, json={"status": "working", "note": "on it"})

    assert r.status_code == 200
    assert r.json()["status"] == "working"
    assert r.json()["note"] == "on it"


def test_patch_invalid_status_is_422(client: TestClient) -> None:
    client.post(ISSUE_PATH, json=STAR_BODY)

    assert client.patch(ISSUE_PATH, json={"status": "done-ish"}).status_code == 422


def test_patch_untracked_is_404(client: TestClient) -> None:
    assert client.patch(ISSUE_PATH, json={"status": "working"}).status_code == 404
    assert client.delete(ISSUE_PATH).status_code == 404


def test_delete_unstars(client: TestClient) -> None:
    client.post(ISSUE_PATH, json=STAR_BODY)

    assert client.delete(ISSUE_PATH).status_code == 204
    assert client.get("/api/tracked").json()["items"] == []


def test_sync_pr_merged_sets_status(client: TestClient, fake_github: None) -> None:
    client.post(ISSUE_PATH, json=STAR_BODY)
    client.patch(ISSUE_PATH, json={"pr_url": "https://github.com/octo/hello/pull/5"})

    r = client.post(f"{ISSUE_PATH}/sync-pr")

    assert r.status_code == 200
    assert r.json()["pr_state"] == "merged"
    assert r.json()["status"] == "merged"


def test_sync_pr_rejects_non_pr_url(client: TestClient, fake_github: None) -> None:
    client.post(ISSUE_PATH, json=STAR_BODY)
    client.patch(ISSUE_PATH, json={"pr_url": "https://github.com/octo/hello/issues/5"})

    assert client.post(f"{ISSUE_PATH}/sync-pr").status_code == 400


def test_dashboard_renders_tracked_issue(client: TestClient) -> None:
    client.post(ISSUE_PATH, json=STAR_BODY)

    r = client.get("/dashboard")

    assert r.status_code == 200
    assert "Fix the thing" in r.text
    assert "Working on it" in r.text
    assert 'href="/dashboard"' in r.text


def test_home_without_profile_shows_picker(client: TestClient, fake_github: None) -> None:
    r = client.get("/")

    assert r.status_code == 200
    assert 'id="profile-form"' in r.text
    assert "repo-card" not in r.text
    assert 'href="/analyze"' in r.text


def test_home_shows_suggestions(client: TestClient, fake_github: None) -> None:
    r = client.get("/?level=beginner&lang=python")

    assert r.status_code == 200
    assert "octo/hello" in r.text
    assert 'href="/repo/octo/hello?level=beginner"' in r.text


def test_home_unknown_level_defaults_to_beginner(client: TestClient, fake_github: None) -> None:
    r = client.get("/?level=wizard&lang=python")

    assert r.status_code == 200
    assert 'href="/repo/octo/hello?level=beginner"' in r.text


def test_home_fallback_note(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class _RateLimited(_FakeGitHubClient):
        def search_repositories(self, query: str, sort: str = "stars", per_page: int = 10) -> list[dict]:
            raise GitHubAPIError(403, "rate limited")

    monkeypatch.setattr(web_app, "GitHubClient", _RateLimited)

    r = client.get("/?level=beginner&lang=rust")

    assert r.status_code == 200
    assert "rust-lang/rustlings" in r.text
    assert "hand-picked" in r.text


def test_repo_page_lists_issues(client: TestClient, fake_github: None) -> None:
    client.post(ISSUE_PATH, json=STAR_BODY)

    r = client.get("/repo/octo/hello?level=beginner")

    assert r.status_code == 200
    assert "Fix the thing" in r.text
    assert 'href="/analyze?repo=octo/hello&amp;issue=1"' in r.text
    assert "good first issue" in r.text
    assert 'data-starred="true"' in r.text


def test_repo_page_empty_state(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class _NoIssues(_FakeGitHubClient):
        def list_issues(self, *args, **kwargs):
            return iter(())

    monkeypatch.setattr(web_app, "GitHubClient", _NoIssues)

    r = client.get("/repo/octo/hello?level=beginner")

    assert r.status_code == 200
    assert "No open" in r.text


def test_repo_page_not_found(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class _Missing(_FakeGitHubClient):
        def list_issues(self, *args, **kwargs):
            raise GitHubNotFoundError(404, "not found")

    monkeypatch.setattr(web_app, "GitHubClient", _Missing)

    assert client.get("/repo/octo/nope").status_code == 404
