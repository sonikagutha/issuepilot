from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import issuepilot.web.server as web_app
from issuepilot.config import Settings
from issuepilot.github.client import GitHubNotFoundError
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


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> TestClient:
    settings = Settings(github_token="x", trace_db_path=tmp_path / "t.db", cache_db_path=tmp_path / "c.db")
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
